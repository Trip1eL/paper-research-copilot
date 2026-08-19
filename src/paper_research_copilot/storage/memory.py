"""In-memory Repository Fake used by focused unit tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Literal

from paper_research_copilot.storage.repositories import (
    ResearchEventRecord,
    ResearchEventType,
    ResearchTaskRecord,
    ResearchTaskStatus,
    TaskNotFoundError,
    TaskStateConflictError,
)


@dataclass
class _MutableTask:
    task_id: str
    question: str
    status: ResearchTaskStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result_json: str | None = None
    error: str | None = None
    current_node: str | None = None
    attempt: int = 0


class InMemoryResearchRepository:
    storage_name = "memory"

    def __init__(self) -> None:
        self._tasks: dict[str, _MutableTask] = {}
        self._events: dict[str, list[ResearchEventRecord]] = {}
        self._lock = RLock()
        self._closed = False

    def create_task(
        self,
        *,
        task_id: str,
        question: str,
        created_at: datetime,
    ) -> ResearchTaskRecord:
        with self._lock:
            self._ensure_open()
            if task_id in self._tasks:
                raise TaskStateConflictError(f"Research task already exists: {task_id}")
            task = _MutableTask(task_id, question, "queued", created_at)
            self._tasks[task_id] = task
            self._events[task_id] = []
            self._append_event(task, "task_queued", created_at, "Research task queued")
            return self._snapshot(task)

    def get_task(self, task_id: str) -> ResearchTaskRecord:
        with self._lock:
            return self._snapshot(self._require(task_id))

    def start_task(self, task_id: str, *, started_at: datetime) -> ResearchTaskRecord:
        with self._lock:
            task = self._require_in_status(task_id, "queued")
            task.status = "running"
            task.started_at = task.started_at or started_at
            task.completed_at = None
            task.error = None
            task.attempt += 1
            self._append_event(task, "task_started", started_at, "Research task started")
            return self._snapshot(task)

    def resume_task(self, task_id: str, *, resumed_at: datetime) -> ResearchTaskRecord:
        with self._lock:
            task = self._require_in_status(task_id, "interrupted")
            task.status = "queued"
            task.completed_at = None
            task.error = None
            self._append_event(task, "task_resumed", resumed_at, "Research task resume queued")
            return self._snapshot(task)

    def complete_task(
        self,
        task_id: str,
        *,
        status: Literal["succeeded", "failed"],
        completed_at: datetime,
        result_json: str | None,
        error: str | None,
    ) -> ResearchTaskRecord:
        with self._lock:
            task = self._require_in_status(task_id, "running")
            task.status = status
            task.completed_at = completed_at
            task.result_json = result_json
            task.error = error
            event_type: ResearchEventType = (
                "task_succeeded" if status == "succeeded" else "task_failed"
            )
            message = "Research task completed" if status == "succeeded" else error
            self._append_event(task, event_type, completed_at, message)
            return self._snapshot(task)

    def append_agent_event(
        self,
        task_id: str,
        *,
        created_at: datetime,
        agent_event_json: str,
        current_node: str,
    ) -> ResearchEventRecord:
        with self._lock:
            task = self._require_in_status(task_id, "running")
            task.current_node = current_node
            return self._append_event(
                task,
                "agent_node",
                created_at,
                None,
                agent_event_json=agent_event_json,
            )

    def interrupt_running_tasks(self, *, interrupted_at: datetime) -> tuple[str, ...]:
        with self._lock:
            interrupted: list[str] = []
            for task in self._tasks.values():
                if task.status != "running":
                    continue
                task.status = "interrupted"
                task.error = "Process stopped before the research task completed"
                self._append_event(
                    task,
                    "task_interrupted",
                    interrupted_at,
                    task.error,
                )
                interrupted.append(task.task_id)
            return tuple(interrupted)

    def list_events(
        self,
        task_id: str,
        *,
        after_sequence: int = 0,
    ) -> tuple[ResearchEventRecord, ...]:
        with self._lock:
            self._require(task_id)
            return tuple(
                event
                for event in self._events[task_id]
                if event.sequence > after_sequence
            )

    def task_counts(self) -> tuple[int, int, int]:
        with self._lock:
            statuses = tuple(task.status for task in self._tasks.values())
            return (
                statuses.count("queued"),
                statuses.count("running"),
                sum(status in {"interrupted", "succeeded", "failed"} for status in statuses),
            )

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def _append_event(
        self,
        task: _MutableTask,
        event_type: ResearchEventType,
        created_at: datetime,
        message: str | None,
        *,
        agent_event_json: str | None = None,
    ) -> ResearchEventRecord:
        events = self._events[task.task_id]
        event = ResearchEventRecord(
            task_id=task.task_id,
            sequence=len(events) + 1,
            event_type=event_type,
            status=task.status,
            created_at=created_at,
            agent_event_json=agent_event_json,
            message=message,
        )
        events.append(event)
        return event

    def _require(self, task_id: str) -> _MutableTask:
        self._ensure_open()
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise TaskNotFoundError(f"Unknown research task: {task_id}") from exc

    def _require_in_status(
        self,
        task_id: str,
        expected: ResearchTaskStatus,
    ) -> _MutableTask:
        task = self._require(task_id)
        if task.status != expected:
            raise TaskStateConflictError(
                f"Task {task_id} is {task.status}; expected {expected}"
            )
        return task

    def _snapshot(self, task: _MutableTask) -> ResearchTaskRecord:
        return ResearchTaskRecord(
            task_id=task.task_id,
            question=task.question,
            status=task.status,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            result_json=task.result_json,
            error=task.error,
            current_node=task.current_node,
            attempt=task.attempt,
            event_count=len(self._events[task.task_id]),
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Research Repository is closed")
