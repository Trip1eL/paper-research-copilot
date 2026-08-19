"""Thread-safe in-memory execution service around the bounded Agent runtime."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Condition, Lock
from typing import Protocol
from uuid import uuid4

from paper_research_copilot.agent import AgentEvent, AgentResult
from paper_research_copilot.api.models import (
    ResearchEventType,
    ResearchStreamEvent,
    ResearchTaskStatus,
    ResearchTaskView,
)

TERMINAL_STATUSES = frozenset({"succeeded", "failed"})


class AgentRuntimeProtocol(Protocol):
    def run(
        self,
        question: str,
        *,
        event_callback: Callable[[AgentEvent], None] | None = None,
    ) -> AgentResult: ...

    def close(self) -> None: ...


@dataclass
class _TaskRecord:
    task_id: str
    question: str
    status: ResearchTaskStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: AgentResult | None = None
    error: str | None = None
    events: list[ResearchStreamEvent] = field(default_factory=list)


class ResearchTaskService:
    """Run one local Agent task at a time and expose observable task state."""

    def __init__(
        self,
        runtime_factory: Callable[[], AgentRuntimeProtocol],
        *,
        max_workers: int = 1,
    ) -> None:
        if max_workers < 1:
            raise ValueError("Research task service requires at least one worker")
        self._runtime_factory = runtime_factory
        self._runtime: AgentRuntimeProtocol | None = None
        self._runtime_lock = Lock()
        self._condition = Condition()
        self._records: dict[str, _TaskRecord] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="paper-research-task",
        )
        self._closed = False

    def submit(self, question: str) -> ResearchTaskView:
        now = _now()
        task_id = uuid4().hex
        record = _TaskRecord(
            task_id=task_id,
            question=question,
            status="queued",
            created_at=now,
        )
        with self._condition:
            if self._closed:
                raise RuntimeError("Research task service is closed")
            self._records[task_id] = record
            self._append_event_locked(record, "task_queued", message="Research task queued")
            accepted = _snapshot(record)
            self._executor.submit(self._execute, task_id)
            return accepted

    def get(self, task_id: str) -> ResearchTaskView:
        with self._condition:
            return _snapshot(self._require_record_locked(task_id))

    def wait_for_events(
        self,
        task_id: str,
        after_sequence: int,
        timeout: float,
    ) -> tuple[tuple[ResearchStreamEvent, ...], bool]:
        with self._condition:
            record = self._require_record_locked(task_id)
            self._condition.wait_for(
                lambda: (
                    any(event.sequence > after_sequence for event in record.events)
                    or record.status in TERMINAL_STATUSES
                ),
                timeout=timeout,
            )
            events = tuple(event for event in record.events if event.sequence > after_sequence)
            return events, record.status in TERMINAL_STATUSES

    def probe_runtime(self) -> tuple[bool, str | None]:
        try:
            self._get_runtime()
        except Exception as exc:
            return False, _public_error(exc)
        return True, None

    def task_counts(self) -> tuple[int, int, int]:
        with self._condition:
            statuses = tuple(record.status for record in self._records.values())
        return (
            statuses.count("queued"),
            statuses.count("running"),
            sum(status in TERMINAL_STATUSES for status in statuses),
        )

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=False)
        with self._runtime_lock:
            if self._runtime is not None:
                self._runtime.close()
                self._runtime = None

    def _execute(self, task_id: str) -> None:
        with self._condition:
            record = self._require_record_locked(task_id)
            record.status = "running"
            record.started_at = _now()
            self._append_event_locked(record, "task_started", message="Research task started")
        try:
            runtime = self._get_runtime()
            result = runtime.run(
                record.question,
                event_callback=lambda event: self._record_agent_event(task_id, event),
            )
        except Exception as exc:
            with self._condition:
                record = self._require_record_locked(task_id)
                record.status = "failed"
                record.error = _public_error(exc)
                record.completed_at = _now()
                self._append_event_locked(
                    record,
                    "task_failed",
                    message=record.error,
                )
            return
        with self._condition:
            record = self._require_record_locked(task_id)
            record.status = "succeeded"
            record.result = result
            record.completed_at = _now()
            self._append_event_locked(
                record,
                "task_succeeded",
                message="Research task completed",
            )

    def _record_agent_event(self, task_id: str, event: AgentEvent) -> None:
        with self._condition:
            record = self._require_record_locked(task_id)
            self._append_event_locked(record, "agent_node", agent_event=event)

    def _append_event_locked(
        self,
        record: _TaskRecord,
        event_type: ResearchEventType,
        *,
        agent_event: AgentEvent | None = None,
        message: str | None = None,
    ) -> None:
        record.events.append(
            ResearchStreamEvent(
                sequence=len(record.events) + 1,
                event_type=event_type,
                task_id=record.task_id,
                created_at=_now(),
                status=record.status,
                agent_event=agent_event,
                message=message,
            )
        )
        self._condition.notify_all()

    def _get_runtime(self) -> AgentRuntimeProtocol:
        with self._runtime_lock:
            if self._runtime is None:
                self._runtime = self._runtime_factory()
            return self._runtime

    def _require_record_locked(self, task_id: str) -> _TaskRecord:
        try:
            return self._records[task_id]
        except KeyError as exc:
            raise KeyError(f"Unknown research task: {task_id}") from exc


def _snapshot(record: _TaskRecord) -> ResearchTaskView:
    return ResearchTaskView(
        task_id=record.task_id,
        question=record.question,
        status=record.status,
        created_at=record.created_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
        event_count=len(record.events),
        result=record.result,
        error=record.error,
    )


def _public_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _now() -> datetime:
    return datetime.now(UTC)
