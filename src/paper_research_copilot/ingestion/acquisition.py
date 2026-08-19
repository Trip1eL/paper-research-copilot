"""Bounded search, selection, and dynamic ingestion orchestration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from paper_research_copilot.domain import (
    AcquisitionBudget,
    AcquisitionResult,
    AcquisitionStatus,
    DynamicIngestionResult,
    PaperCandidate,
)
from paper_research_copilot.integrations.scholarly import (
    AcademicSearchProvider,
    rank_and_deduplicate_candidates,
)
from paper_research_copilot.storage import (
    AcquisitionNotFoundError,
    AcquisitionRepository,
)


class CandidateIngestion(Protocol):
    def ingest(
        self,
        candidate: PaperCandidate,
        *,
        acquisition_query: str,
    ) -> DynamicIngestionResult: ...


class AcademicAcquisitionService:
    def __init__(
        self,
        search_provider: AcademicSearchProvider,
        ingestion: CandidateIngestion,
        repository: AcquisitionRepository,
        *,
        budget: AcquisitionBudget | None = None,
        close_callbacks: tuple[Callable[[], None], ...] = (),
    ) -> None:
        self._search_provider = search_provider
        self._ingestion = ingestion
        self._repository = repository
        self.budget = budget or AcquisitionBudget()
        self._close_callbacks = close_callbacks
        self._closed = False

    def acquire(
        self,
        query: str,
        *,
        task_id: str | None = None,
        round_number: int = 1,
    ) -> AcquisitionResult:
        normalized = " ".join(query.split())
        if not normalized:
            raise ValueError("Acquisition query must not be empty")
        if round_number < 1:
            raise ValueError("Acquisition round must be at least one")
        if self._closed:
            raise RuntimeError("Academic Acquisition Service is closed")
        acquisition_id = _acquisition_id(task_id, normalized, round_number)
        try:
            run = self._repository.get_acquisition(acquisition_id)
        except AcquisitionNotFoundError:
            run = self._repository.start_acquisition(
                acquisition_id=acquisition_id,
                task_id=task_id,
                query=normalized,
                budget=self.budget,
                started_at=_now(),
            )
        if run.status != "running":
            return AcquisitionResult(run=run, candidates=(), ingestions=())

        try:
            found = self._search_provider.search(
                normalized,
                self.budget.candidates_per_query,
            )
            candidates = rank_and_deduplicate_candidates(
                normalized,
                found,
                limit=self.budget.candidates_per_query,
            )
        except Exception as exc:
            failed = self._repository.complete_acquisition(
                acquisition_id,
                status="failed",
                candidate_count=0,
                selected_count=0,
                downloaded_count=0,
                indexed_count=0,
                completed_at=_now(),
                error=_public_error(exc),
            )
            return AcquisitionResult(run=failed, candidates=(), ingestions=())

        selected = candidates[: self.budget.max_downloads]
        ingestions: list[DynamicIngestionResult] = []
        errors: list[str] = []
        for candidate in selected:
            try:
                ingestions.append(
                    self._ingestion.ingest(
                        candidate,
                        acquisition_query=normalized,
                    )
                )
            except Exception as exc:
                errors.append(f"{candidate.identity}: {_public_error(exc)}")

        downloaded_count = sum(item.downloaded for item in ingestions)
        indexed_count = sum(item.outcome == "indexed" for item in ingestions)
        successful = sum(
            item.outcome in {"indexed", "already_active", "duplicate"}
            for item in ingestions
        )
        if successful == len(selected) and not errors:
            status: AcquisitionStatus = "succeeded"
        elif successful:
            status = "partial"
        else:
            status = "failed"
        error = "; ".join(
            [
                *errors,
                *(
                    f"{item.asset.candidate.identity}: {item.asset.error}"
                    for item in ingestions
                    if item.outcome == "failed"
                ),
            ]
        ) or ("Academic search returned no candidates" if not selected else None)
        completed = self._repository.complete_acquisition(
            acquisition_id,
            status=status,
            candidate_count=len(candidates),
            selected_count=len(selected),
            downloaded_count=downloaded_count,
            indexed_count=indexed_count,
            completed_at=_now(),
            error=error,
        )
        return AcquisitionResult(
            run=completed,
            candidates=candidates,
            ingestions=tuple(ingestions),
        )

    def close(self) -> None:
        if self._closed:
            return
        for callback in reversed(self._close_callbacks):
            callback()
        self._closed = True


def _acquisition_id(task_id: str | None, query: str, round_number: int) -> str:
    key = f"{task_id or 'standalone'}:{round_number}:{query.casefold()}"
    return uuid5(NAMESPACE_URL, key).hex


def _public_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _now() -> datetime:
    return datetime.now(UTC)
