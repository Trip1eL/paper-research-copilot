"""Persistence contracts for durable research task execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from paper_research_copilot.domain import (
    AcquisitionBudget,
    AcquisitionRun,
    AcquisitionStatus,
    DownloadedPaper,
    PaperAsset,
    PaperCandidate,
)

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


class PaperAssetNotFoundError(KeyError):
    """Raised when a dynamic paper asset does not exist."""


class AcquisitionNotFoundError(KeyError):
    """Raised when an acquisition run does not exist."""


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
    parent_task_id: str | None = None
    parent_question: str | None = None
    clarification_response: str | None = None


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

    def create_clarified_task(
        self,
        *,
        parent_task_id: str,
        task_id: str,
        question: str,
        clarification_response: str,
        created_at: datetime,
    ) -> tuple[ResearchTaskRecord, bool]: ...

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


class AcquisitionRepository(Protocol):
    """Paper Registry and Acquisition Run persistence boundary."""

    def register_candidate(
        self,
        candidate: PaperCandidate,
        *,
        acquisition_query: str,
        discovered_at: datetime,
    ) -> PaperAsset: ...

    def get_paper_asset(self, asset_id: str) -> PaperAsset: ...

    def find_paper_asset(
        self,
        *,
        provider: str,
        external_id: str,
        revision: int,
    ) -> PaperAsset | None: ...

    def find_paper_asset_by_sha256(self, sha256: str) -> PaperAsset | None: ...

    def mark_asset_downloaded(
        self,
        asset_id: str,
        downloaded: DownloadedPaper,
    ) -> PaperAsset: ...

    def mark_asset_parsed(
        self,
        asset_id: str,
        *,
        page_count: int,
        parse_summary_json: str,
        updated_at: datetime,
    ) -> PaperAsset: ...

    def mark_asset_indexed(
        self,
        asset_id: str,
        *,
        chunk_count: int,
        collection_name: str,
        index_version: str,
        updated_at: datetime,
    ) -> PaperAsset: ...

    def activate_asset(self, asset_id: str, *, updated_at: datetime) -> PaperAsset: ...

    def mark_asset_duplicate(
        self,
        asset_id: str,
        *,
        duplicate_of_asset_id: str,
        updated_at: datetime,
    ) -> PaperAsset: ...

    def mark_asset_failed(
        self,
        asset_id: str,
        *,
        status: Literal["download_failed", "quarantined", "indexing_failed"],
        error: str,
        updated_at: datetime,
    ) -> PaperAsset: ...

    def start_acquisition(
        self,
        *,
        acquisition_id: str,
        task_id: str | None,
        query: str,
        budget: AcquisitionBudget,
        started_at: datetime,
    ) -> AcquisitionRun: ...

    def complete_acquisition(
        self,
        acquisition_id: str,
        *,
        status: AcquisitionStatus,
        candidate_count: int,
        selected_count: int,
        downloaded_count: int,
        indexed_count: int,
        completed_at: datetime,
        error: str | None,
    ) -> AcquisitionRun: ...

    def get_acquisition(self, acquisition_id: str) -> AcquisitionRun: ...
