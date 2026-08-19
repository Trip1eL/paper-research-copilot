"""Durable task execution service around the bounded Agent runtime."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import UTC, datetime
from threading import Condition, Lock
from typing import Literal, Protocol, cast
from uuid import uuid4

from paper_research_copilot.agent import AgentEvent, AgentResult
from paper_research_copilot.api.models import ResearchStreamEvent, ResearchTaskView
from paper_research_copilot.storage import (
    InMemoryResearchRepository,
    ResearchEventRecord,
    ResearchRepository,
    ResearchTaskRecord,
    TaskStateConflictError,
)

STREAM_END_STATUSES = frozenset({"interrupted", "succeeded", "failed"})


class AgentRuntimeProtocol(Protocol):
    def run(
        self,
        question: str,
        *,
        event_callback: Callable[[AgentEvent], None] | None = None,
        task_id: str | None = None,
    ) -> AgentResult: ...

    def can_resume(self, task_id: str) -> bool: ...

    def resume(
        self,
        task_id: str,
        *,
        event_callback: Callable[[AgentEvent], None] | None = None,
    ) -> AgentResult: ...

    def close(self) -> None: ...


class CheckpointStoreProtocol(Protocol):
    storage_name: str

    def has_checkpoint(self, thread_id: str) -> bool: ...

    def probe(self) -> tuple[bool, str | None]: ...

    def close(self) -> None: ...


class TaskResumeError(RuntimeError):
    """Raised when an interrupted task cannot be resumed."""


class ResearchTaskService:
    """Run one local Agent task at a time with durable lifecycle state."""

    def __init__(
        self,
        runtime_factory: Callable[[], AgentRuntimeProtocol],
        *,
        repository: ResearchRepository | None = None,
        checkpoint_store: CheckpointStoreProtocol | None = None,
        max_workers: int = 1,
    ) -> None:
        if max_workers < 1:
            raise ValueError("Research task service requires at least one worker")
        self._runtime_factory = runtime_factory
        self._runtime: AgentRuntimeProtocol | None = None
        self._runtime_lock = Lock()
        self._condition = Condition()
        self._repository = repository or InMemoryResearchRepository()
        self._checkpoint_store = checkpoint_store
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="paper-research-task",
        )
        self._closed = False
        self._repository.interrupt_running_tasks(interrupted_at=_now())

    @property
    def task_store_name(self) -> Literal["memory", "sqlite"]:
        return cast(Literal["memory", "sqlite"], self._repository.storage_name)

    def submit(self, question: str) -> ResearchTaskView:
        with self._condition:
            self._ensure_open()
            task_id = uuid4().hex
            record = self._repository.create_task(
                task_id=task_id,
                question=question,
                created_at=_now(),
            )
            self._condition.notify_all()
            self._executor.submit(self._execute, task_id, False)
            return _task_view(record)

    def resume(self, task_id: str) -> ResearchTaskView:
        with self._condition:
            self._ensure_open()
            if self._checkpoint_store is None:
                raise TaskResumeError("LangGraph checkpointing is not configured")
            if not self._checkpoint_store.has_checkpoint(task_id):
                raise TaskResumeError("No LangGraph checkpoint exists for this task")
            try:
                record = self._repository.resume_task(task_id, resumed_at=_now())
            except TaskStateConflictError as exc:
                raise TaskResumeError(str(exc)) from exc
            self._condition.notify_all()
            self._executor.submit(self._execute, task_id, True)
            return _task_view(record)

    def get(self, task_id: str) -> ResearchTaskView:
        return _task_view(self._repository.get_task(task_id))

    def wait_for_events(
        self,
        task_id: str,
        after_sequence: int,
        timeout: float,
    ) -> tuple[tuple[ResearchStreamEvent, ...], bool]:
        with self._condition:
            self._repository.get_task(task_id)
            self._condition.wait_for(
                lambda: self._events_ready(task_id, after_sequence),
                timeout=timeout,
            )
            records = self._repository.list_events(
                task_id,
                after_sequence=after_sequence,
            )
            task = self._repository.get_task(task_id)
            return tuple(_stream_event(event) for event in records), (
                task.status in STREAM_END_STATUSES
            )

    def probe_runtime(self) -> tuple[bool, str | None]:
        try:
            self._get_runtime()
        except Exception as exc:
            return False, _public_error(exc)
        return True, None

    def probe_checkpoint(self) -> tuple[bool, str | None]:
        if self._checkpoint_store is None:
            return False, "LangGraph checkpointing is not configured"
        return self._checkpoint_store.probe()

    def task_counts(self) -> tuple[int, int, int]:
        return self._repository.task_counts()

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            self._closed = True
            self._condition.notify_all()
        self._executor.shutdown(wait=True, cancel_futures=False)
        with self._runtime_lock:
            if self._runtime is not None:
                self._runtime.close()
                self._runtime = None
        self._repository.close()
        if self._checkpoint_store is not None:
            self._checkpoint_store.close()

    def _execute(self, task_id: str, resume: bool) -> None:
        try:
            record = self._repository.start_task(task_id, started_at=_now())
            self._notify()
            runtime = self._get_runtime()

            def callback(event: AgentEvent) -> None:
                self._record_agent_event(task_id, event)

            if resume:
                result = runtime.resume(task_id, event_callback=callback)
            else:
                result = _run_new_task(runtime, record.question, task_id, callback)
        except Exception as exc:
            with suppress(TaskStateConflictError):
                self._repository.complete_task(
                    task_id,
                    status="failed",
                    completed_at=_now(),
                    result_json=None,
                    error=_public_error(exc),
                )
            self._notify()
            return
        self._repository.complete_task(
            task_id,
            status="succeeded",
            completed_at=_now(),
            result_json=result.model_dump_json(),
            error=None,
        )
        self._notify()

    def _record_agent_event(self, task_id: str, event: AgentEvent) -> None:
        self._repository.append_agent_event(
            task_id,
            created_at=_now(),
            agent_event_json=event.model_dump_json(),
            current_node=event.node,
        )
        self._notify()

    def _events_ready(self, task_id: str, after_sequence: int) -> bool:
        events = self._repository.list_events(task_id, after_sequence=after_sequence)
        task = self._repository.get_task(task_id)
        return bool(events) or task.status in STREAM_END_STATUSES or self._closed

    def _notify(self) -> None:
        with self._condition:
            self._condition.notify_all()

    def _get_runtime(self) -> AgentRuntimeProtocol:
        with self._runtime_lock:
            if self._runtime is None:
                self._runtime = self._runtime_factory()
            return self._runtime

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Research task service is closed")


def _run_new_task(
    runtime: AgentRuntimeProtocol,
    question: str,
    task_id: str,
    event_callback: Callable[[AgentEvent], None],
) -> AgentResult:
    # Keep simple injected test runtimes compatible while production receives thread_id.
    if "task_id" in inspect.signature(runtime.run).parameters:
        return runtime.run(
            question,
            event_callback=event_callback,
            task_id=task_id,
        )
    return runtime.run(question, event_callback=event_callback)


def _task_view(record: ResearchTaskRecord) -> ResearchTaskView:
    result = (
        AgentResult.model_validate_json(record.result_json)
        if record.result_json is not None
        else None
    )
    return ResearchTaskView(
        task_id=record.task_id,
        question=record.question,
        status=record.status,
        created_at=record.created_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
        event_count=record.event_count,
        result=result,
        error=record.error,
    )


def _stream_event(record: ResearchEventRecord) -> ResearchStreamEvent:
    agent_event = (
        AgentEvent.model_validate_json(record.agent_event_json)
        if record.agent_event_json is not None
        else None
    )
    return ResearchStreamEvent(
        sequence=record.sequence,
        event_type=record.event_type,
        task_id=record.task_id,
        created_at=record.created_at,
        status=record.status,
        agent_event=agent_event,
        message=record.message,
    )


def _public_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _now() -> datetime:
    return datetime.now(UTC)
