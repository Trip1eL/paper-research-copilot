"""Persistence contracts for durable research task execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

ResearchTaskStatus = Literal["queued", "running", "interrupted", "succeeded", "failed"]
ResearchEventType = Literal[
    "task_queued",
    "task_started",
    "task_interrupted",
    "task_resumed",
    "agent_node",
    "task_succeeded",
    "task_failed",
]


class TaskNotFoundError(KeyError):
    """Raised when a research task does not exist."""


class TaskStateConflictError(RuntimeError):
    """Raised when a state transition does not match the persisted task state."""


@dataclass(frozen=True)
class ResearchTaskRecord:
    task_id: str
    question: str
    status: ResearchTaskStatus
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    result_json: str | None
    error: str | None
    current_node: str | None
    attempt: int
    event_count: int


@dataclass(frozen=True)
class ResearchEventRecord:
    task_id: str
    sequence: int
    event_type: ResearchEventType
    status: ResearchTaskStatus
    created_at: datetime
    agent_event_json: str | None
    message: str | None


class ResearchRepository(Protocol):
    """Atomic task lifecycle and append-only event persistence."""

    storage_name: str

    def create_task(
        self,
        *,
        task_id: str,
        question: str,
        created_at: datetime,
    ) -> ResearchTaskRecord: ...

    def get_task(self, task_id: str) -> ResearchTaskRecord: ...

    def start_task(self, task_id: str, *, started_at: datetime) -> ResearchTaskRecord: ...

    def resume_task(self, task_id: str, *, resumed_at: datetime) -> ResearchTaskRecord: ...

    def complete_task(
        self,
        task_id: str,
        *,
        status: Literal["succeeded", "failed"],
        completed_at: datetime,
        result_json: str | None,
        error: str | None,
    ) -> ResearchTaskRecord: ...

    def append_agent_event(
        self,
        task_id: str,
        *,
        created_at: datetime,
        agent_event_json: str,
        current_node: str,
    ) -> ResearchEventRecord: ...

    def interrupt_running_tasks(self, *, interrupted_at: datetime) -> tuple[str, ...]: ...

    def list_events(
        self,
        task_id: str,
        *,
        after_sequence: int = 0,
    ) -> tuple[ResearchEventRecord, ...]: ...

    def task_counts(self) -> tuple[int, int, int]: ...

    def close(self) -> None: ...
