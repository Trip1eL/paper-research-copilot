"""SQLite implementation of the durable research Repository."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from threading import RLock
from typing import Literal, cast

from sqlalchemy import URL, Engine, create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from paper_research_copilot.domain import (
    AcquisitionBudget,
    AcquisitionRun,
    AcquisitionStatus,
    DownloadedPaper,
    PaperAsset,
    PaperAssetStatus,
    PaperCandidate,
)
from paper_research_copilot.storage.migrations import upgrade_database
from paper_research_copilot.storage.models import (
    AcquisitionRunRow,
    PaperAssetRow,
    ResearchEventRow,
    ResearchTaskClarificationRow,
    ResearchTaskRow,
)
from paper_research_copilot.storage.repositories import (
    AcquisitionNotFoundError,
    PaperAssetNotFoundError,
    ResearchEventRecord,
    ResearchEventType,
    ResearchTaskRecord,
    ResearchTaskStatus,
    TaskNotFoundError,
    TaskStateConflictError,
)


class SqliteResearchRepository:
    storage_name = "sqlite"

    def __init__(self, path: Path, *, run_migrations: bool = True) -> None:
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if run_migrations:
            upgrade_database(self.path)
        self._engine = _create_sqlite_engine(self.path)
        self._sessions = sessionmaker(self._engine, expire_on_commit=False)
        self._write_lock = RLock()
        self._closed = False

    def create_task(
        self,
        *,
        task_id: str,
        question: str,
        created_at: datetime,
    ) -> ResearchTaskRecord:
        with self._write_lock, self._sessions.begin() as session:
            self._ensure_open()
            if session.get(ResearchTaskRow, task_id) is not None:
                raise TaskStateConflictError(f"Research task already exists: {task_id}")
            row = ResearchTaskRow(
                task_id=task_id,
                question=question,
                status="queued",
                created_at=_serialize_datetime(created_at),
                attempt=0,
            )
            session.add(row)
            session.flush()
            self._append_event(
                session,
                row,
                "task_queued",
                created_at,
                "Research task queued",
            )
            session.flush()
            return self._snapshot(session, row)

    def create_clarified_task(
        self,
        *,
        parent_task_id: str,
        task_id: str,
        question: str,
        clarification_response: str,
        created_at: datetime,
    ) -> tuple[ResearchTaskRecord, bool]:
        response_hash = sha256(
            clarification_response.casefold().encode("utf-8")
        ).hexdigest()
        with self._write_lock, self._sessions.begin() as session:
            parent = self._require_in_status(session, parent_task_id, "succeeded")
            existing = session.scalar(
                select(ResearchTaskClarificationRow).where(
                    ResearchTaskClarificationRow.parent_task_id == parent.task_id,
                    ResearchTaskClarificationRow.response_hash == response_hash,
                )
            )
            if existing is not None:
                return (
                    self._snapshot(
                        session,
                        self._require(session, existing.child_task_id),
                    ),
                    False,
                )
            if session.get(ResearchTaskRow, task_id) is not None:
                raise TaskStateConflictError(f"Research task already exists: {task_id}")
            row = ResearchTaskRow(
                task_id=task_id,
                question=question,
                status="queued",
                created_at=_serialize_datetime(created_at),
                attempt=0,
            )
            session.add(row)
            session.flush()
            session.add(
                ResearchTaskClarificationRow(
                    parent_task_id=parent.task_id,
                    child_task_id=task_id,
                    response=clarification_response,
                    response_hash=response_hash,
                    created_at=_serialize_datetime(created_at),
                )
            )
            self._append_event(
                session,
                row,
                "task_queued",
                created_at,
                "Clarified research task queued",
            )
            session.flush()
            return self._snapshot(session, row), True

    def get_task(self, task_id: str) -> ResearchTaskRecord:
        with self._sessions() as session:
            self._ensure_open()
            return self._snapshot(session, self._require(session, task_id))

    def start_task(self, task_id: str, *, started_at: datetime) -> ResearchTaskRecord:
        with self._write_lock, self._sessions.begin() as session:
            row = self._require_in_status(session, task_id, "queued")
            row.status = "running"
            row.started_at = row.started_at or _serialize_datetime(started_at)
            row.completed_at = None
            row.error = None
            row.attempt += 1
            self._append_event(
                session,
                row,
                "task_started",
                started_at,
                "Research task started",
            )
            session.flush()
            return self._snapshot(session, row)

    def resume_task(self, task_id: str, *, resumed_at: datetime) -> ResearchTaskRecord:
        with self._write_lock, self._sessions.begin() as session:
            row = self._require_in_status(session, task_id, "interrupted")
            row.status = "queued"
            row.completed_at = None
            row.error = None
            self._append_event(
                session,
                row,
                "task_resumed",
                resumed_at,
                "Research task resume queued",
            )
            session.flush()
            return self._snapshot(session, row)

    def complete_task(
        self,
        task_id: str,
        *,
        status: Literal["succeeded", "failed"],
        completed_at: datetime,
        result_json: str | None,
        error: str | None,
    ) -> ResearchTaskRecord:
        if status == "succeeded" and (result_json is None or error is not None):
            raise ValueError("Succeeded tasks require result_json and no error")
        if status == "failed" and (error is None or result_json is not None):
            raise ValueError("Failed tasks require an error and no result_json")
        with self._write_lock, self._sessions.begin() as session:
            row = self._require_in_status(session, task_id, "running")
            row.status = status
            row.completed_at = _serialize_datetime(completed_at)
            row.result_json = result_json
            row.error = error
            event_type: ResearchEventType = (
                "task_succeeded" if status == "succeeded" else "task_failed"
            )
            message = "Research task completed" if status == "succeeded" else error
            self._append_event(session, row, event_type, completed_at, message)
            session.flush()
            return self._snapshot(session, row)

    def append_agent_event(
        self,
        task_id: str,
        *,
        created_at: datetime,
        agent_event_json: str,
        current_node: str,
    ) -> ResearchEventRecord:
        with self._write_lock, self._sessions.begin() as session:
            row = self._require_in_status(session, task_id, "running")
            row.current_node = current_node
            persisted = self._append_event(
                session,
                row,
                "agent_node",
                created_at,
                None,
                agent_event_json=agent_event_json,
            )
            session.flush()
            return _event_record(persisted)

    def interrupt_running_tasks(self, *, interrupted_at: datetime) -> tuple[str, ...]:
        with self._write_lock, self._sessions.begin() as session:
            rows = tuple(
                session.scalars(
                    select(ResearchTaskRow)
                    .where(ResearchTaskRow.status == "running")
                    .order_by(ResearchTaskRow.created_at)
                )
            )
            for row in rows:
                row.status = "interrupted"
                row.error = "Process stopped before the research task completed"
                self._append_event(
                    session,
                    row,
                    "task_interrupted",
                    interrupted_at,
                    row.error,
                )
            return tuple(row.task_id for row in rows)

    def list_events(
        self,
        task_id: str,
        *,
        after_sequence: int = 0,
    ) -> tuple[ResearchEventRecord, ...]:
        with self._sessions() as session:
            self._require(session, task_id)
            rows = session.scalars(
                select(ResearchEventRow)
                .where(
                    ResearchEventRow.task_id == task_id,
                    ResearchEventRow.sequence > after_sequence,
                )
                .order_by(ResearchEventRow.sequence)
            )
            return tuple(_event_record(row) for row in rows)

    def task_counts(self) -> tuple[int, int, int]:
        with self._sessions() as session:
            statuses = tuple(session.scalars(select(ResearchTaskRow.status)))
            return (
                statuses.count("queued"),
                statuses.count("running"),
                sum(status in {"interrupted", "succeeded", "failed"} for status in statuses),
            )

    def register_candidate(
        self,
        candidate: PaperCandidate,
        *,
        acquisition_query: str,
        discovered_at: datetime,
    ) -> PaperAsset:
        with self._write_lock, self._sessions.begin() as session:
            self._ensure_open()
            existing = session.scalar(
                select(PaperAssetRow).where(
                    PaperAssetRow.provider == candidate.provider,
                    PaperAssetRow.external_id == candidate.external_id,
                    PaperAssetRow.revision == candidate.revision,
                )
            )
            if existing is None and candidate.doi is not None:
                existing = session.scalar(
                    select(PaperAssetRow).where(PaperAssetRow.doi == candidate.doi)
                )
            if existing is not None:
                return _asset_record(existing)
            timestamp = _serialize_datetime(discovered_at)
            row = PaperAssetRow(
                asset_id=candidate.asset_id,
                provider=candidate.provider,
                external_id=candidate.external_id,
                revision=candidate.revision,
                doi=candidate.doi,
                candidate_json=candidate.model_dump_json(),
                acquisition_query=acquisition_query,
                status="discovered",
                created_at=timestamp,
                updated_at=timestamp,
            )
            session.add(row)
            session.flush()
            return _asset_record(row)

    def get_paper_asset(self, asset_id: str) -> PaperAsset:
        with self._sessions() as session:
            self._ensure_open()
            return _asset_record(self._require_asset(session, asset_id))

    def find_paper_asset(
        self,
        *,
        provider: str,
        external_id: str,
        revision: int,
    ) -> PaperAsset | None:
        with self._sessions() as session:
            self._ensure_open()
            row = session.scalar(
                select(PaperAssetRow).where(
                    PaperAssetRow.provider == provider,
                    PaperAssetRow.external_id == external_id,
                    PaperAssetRow.revision == revision,
                )
            )
            return _asset_record(row) if row is not None else None

    def find_paper_asset_by_sha256(self, sha256: str) -> PaperAsset | None:
        with self._sessions() as session:
            self._ensure_open()
            row = session.scalar(
                select(PaperAssetRow).where(PaperAssetRow.sha256 == sha256)
            )
            return _asset_record(row) if row is not None else None

    def mark_asset_downloaded(
        self,
        asset_id: str,
        downloaded: DownloadedPaper,
    ) -> PaperAsset:
        with self._write_lock, self._sessions.begin() as session:
            row = self._require_asset_status(
                session,
                asset_id,
                {"discovered", "download_failed"},
            )
            row.status = "downloaded"
            row.sha256 = downloaded.sha256
            row.local_path = downloaded.local_path
            row.file_size_bytes = downloaded.file_size_bytes
            row.error = None
            row.updated_at = _serialize_datetime(downloaded.downloaded_at)
            session.flush()
            return _asset_record(row)

    def mark_asset_parsed(
        self,
        asset_id: str,
        *,
        page_count: int,
        parse_summary_json: str,
        updated_at: datetime,
    ) -> PaperAsset:
        with self._write_lock, self._sessions.begin() as session:
            row = self._require_asset_status(
                session,
                asset_id,
                {"downloaded", "quarantined"},
            )
            row.status = "parsed"
            row.page_count = page_count
            row.parse_summary_json = parse_summary_json
            row.error = None
            row.updated_at = _serialize_datetime(updated_at)
            session.flush()
            return _asset_record(row)

    def mark_asset_indexed(
        self,
        asset_id: str,
        *,
        chunk_count: int,
        collection_name: str,
        index_version: str,
        updated_at: datetime,
    ) -> PaperAsset:
        with self._write_lock, self._sessions.begin() as session:
            row = self._require_asset_status(
                session,
                asset_id,
                {"parsed", "indexing_failed"},
            )
            row.status = "indexed"
            row.chunk_count = chunk_count
            row.collection_name = collection_name
            row.index_version = index_version
            row.error = None
            row.updated_at = _serialize_datetime(updated_at)
            session.flush()
            return _asset_record(row)

    def activate_asset(self, asset_id: str, *, updated_at: datetime) -> PaperAsset:
        with self._write_lock, self._sessions.begin() as session:
            row = self._require_asset_status(session, asset_id, {"indexed", "active"})
            row.status = "active"
            row.updated_at = _serialize_datetime(updated_at)
            session.flush()
            return _asset_record(row)

    def mark_asset_duplicate(
        self,
        asset_id: str,
        *,
        duplicate_of_asset_id: str,
        updated_at: datetime,
    ) -> PaperAsset:
        if asset_id == duplicate_of_asset_id:
            raise ValueError("A paper asset cannot duplicate itself")
        with self._write_lock, self._sessions.begin() as session:
            self._require_asset(session, duplicate_of_asset_id)
            row = self._require_asset_status(
                session,
                asset_id,
                {"discovered", "download_failed"},
            )
            row.status = "duplicate"
            row.duplicate_of_asset_id = duplicate_of_asset_id
            row.error = None
            row.updated_at = _serialize_datetime(updated_at)
            session.flush()
            return _asset_record(row)

    def mark_asset_failed(
        self,
        asset_id: str,
        *,
        status: Literal["download_failed", "quarantined", "indexing_failed"],
        error: str,
        updated_at: datetime,
    ) -> PaperAsset:
        allowed: dict[str, set[str]] = {
            "download_failed": {
                "discovered",
                "downloaded",
                "download_failed",
                "quarantined",
                "parsed",
                "indexing_failed",
            },
            "quarantined": {"downloaded", "quarantined"},
            "indexing_failed": {"parsed", "indexing_failed"},
        }
        with self._write_lock, self._sessions.begin() as session:
            row = self._require_asset_status(session, asset_id, allowed[status])
            row.status = status
            row.error = error
            if status == "download_failed":
                row.sha256 = None
                row.local_path = None
                row.file_size_bytes = None
                row.page_count = None
                row.chunk_count = None
                row.parse_summary_json = None
                row.collection_name = None
                row.index_version = None
            row.updated_at = _serialize_datetime(updated_at)
            session.flush()
            return _asset_record(row)

    def start_acquisition(
        self,
        *,
        acquisition_id: str,
        task_id: str | None,
        query: str,
        budget: AcquisitionBudget,
        started_at: datetime,
    ) -> AcquisitionRun:
        with self._write_lock, self._sessions.begin() as session:
            self._ensure_open()
            if session.get(AcquisitionRunRow, acquisition_id) is not None:
                raise TaskStateConflictError(
                    f"Acquisition run already exists: {acquisition_id}"
                )
            row = AcquisitionRunRow(
                acquisition_id=acquisition_id,
                task_id=task_id,
                query=query,
                status="running",
                budget_json=budget.model_dump_json(),
                started_at=_serialize_datetime(started_at),
            )
            session.add(row)
            session.flush()
            return _acquisition_record(row)

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
    ) -> AcquisitionRun:
        if status == "running":
            raise ValueError("Completed acquisition cannot remain running")
        if status == "failed" and not error:
            raise ValueError("Failed acquisition requires an error")
        with self._write_lock, self._sessions.begin() as session:
            row = self._require_acquisition(session, acquisition_id)
            if row.status != "running":
                raise TaskStateConflictError(
                    f"Acquisition {acquisition_id} is already {row.status}"
                )
            row.status = status
            row.candidate_count = candidate_count
            row.selected_count = selected_count
            row.downloaded_count = downloaded_count
            row.indexed_count = indexed_count
            row.completed_at = _serialize_datetime(completed_at)
            row.error = error
            session.flush()
            return _acquisition_record(row)

    def get_acquisition(self, acquisition_id: str) -> AcquisitionRun:
        with self._sessions() as session:
            self._ensure_open()
            return _acquisition_record(
                self._require_acquisition(session, acquisition_id)
            )

    def close(self) -> None:
        with self._write_lock:
            if self._closed:
                return
            self._closed = True
            self._engine.dispose()

    def _append_event(
        self,
        session: Session,
        task: ResearchTaskRow,
        event_type: ResearchEventType,
        created_at: datetime,
        message: str | None,
        *,
        agent_event_json: str | None = None,
    ) -> ResearchEventRow:
        current = session.scalar(
            select(func.max(ResearchEventRow.sequence)).where(
                ResearchEventRow.task_id == task.task_id
            )
        )
        row = ResearchEventRow(
            task_id=task.task_id,
            sequence=(current or 0) + 1,
            event_type=event_type,
            status=task.status,
            created_at=_serialize_datetime(created_at),
            agent_event_json=agent_event_json,
            message=message,
        )
        session.add(row)
        return row

    def _require(self, session: Session, task_id: str) -> ResearchTaskRow:
        self._ensure_open()
        row = session.get(ResearchTaskRow, task_id)
        if row is None:
            raise TaskNotFoundError(f"Unknown research task: {task_id}")
        return row

    def _require_asset(self, session: Session, asset_id: str) -> PaperAssetRow:
        self._ensure_open()
        row = session.get(PaperAssetRow, asset_id)
        if row is None:
            raise PaperAssetNotFoundError(f"Unknown paper asset: {asset_id}")
        return row

    def _require_asset_status(
        self,
        session: Session,
        asset_id: str,
        allowed: set[str],
    ) -> PaperAssetRow:
        row = self._require_asset(session, asset_id)
        if row.status not in allowed:
            expected = ", ".join(sorted(allowed))
            raise TaskStateConflictError(
                f"Paper asset {asset_id} is {row.status}; expected one of {expected}"
            )
        return row

    def _require_acquisition(
        self,
        session: Session,
        acquisition_id: str,
    ) -> AcquisitionRunRow:
        self._ensure_open()
        row = session.get(AcquisitionRunRow, acquisition_id)
        if row is None:
            raise AcquisitionNotFoundError(
                f"Unknown acquisition run: {acquisition_id}"
            )
        return row

    def _require_in_status(
        self,
        session: Session,
        task_id: str,
        expected: ResearchTaskStatus,
    ) -> ResearchTaskRow:
        row = self._require(session, task_id)
        if row.status != expected:
            raise TaskStateConflictError(
                f"Task {task_id} is {row.status}; expected {expected}"
            )
        return row

    def _snapshot(self, session: Session, row: ResearchTaskRow) -> ResearchTaskRecord:
        event_count = session.scalar(
            select(func.count())
            .select_from(ResearchEventRow)
            .where(ResearchEventRow.task_id == row.task_id)
        )
        clarification = session.scalar(
            select(ResearchTaskClarificationRow).where(
                ResearchTaskClarificationRow.child_task_id == row.task_id
            )
        )
        parent = (
            session.get(ResearchTaskRow, clarification.parent_task_id)
            if clarification is not None
            else None
        )
        return ResearchTaskRecord(
            task_id=row.task_id,
            question=row.question,
            status=cast(ResearchTaskStatus, row.status),
            created_at=_deserialize_datetime(row.created_at),
            started_at=_optional_datetime(row.started_at),
            completed_at=_optional_datetime(row.completed_at),
            result_json=row.result_json,
            error=row.error,
            current_node=row.current_node,
            attempt=row.attempt,
            event_count=event_count or 0,
            parent_task_id=(clarification.parent_task_id if clarification else None),
            parent_question=(parent.question if parent is not None else None),
            clarification_response=(clarification.response if clarification else None),
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Research Repository is closed")


def _create_sqlite_engine(path: Path) -> Engine:
    engine = create_engine(
        URL.create("sqlite+pysqlite", database=str(path)),
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection: sqlite3.Connection, _: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    return engine


def _event_record(row: ResearchEventRow) -> ResearchEventRecord:
    return ResearchEventRecord(
        task_id=row.task_id,
        sequence=row.sequence,
        event_type=cast(ResearchEventType, row.event_type),
        status=cast(ResearchTaskStatus, row.status),
        created_at=_deserialize_datetime(row.created_at),
        agent_event_json=row.agent_event_json,
        message=row.message,
    )


def _asset_record(row: PaperAssetRow) -> PaperAsset:
    return PaperAsset(
        asset_id=row.asset_id,
        candidate=PaperCandidate.model_validate_json(row.candidate_json),
        acquisition_query=row.acquisition_query,
        status=cast(PaperAssetStatus, row.status),
        created_at=_deserialize_datetime(row.created_at),
        updated_at=_deserialize_datetime(row.updated_at),
        sha256=row.sha256,
        local_path=row.local_path,
        file_size_bytes=row.file_size_bytes,
        page_count=row.page_count,
        chunk_count=row.chunk_count,
        collection_name=row.collection_name,
        index_version=row.index_version,
        parse_summary_json=row.parse_summary_json,
        duplicate_of_asset_id=row.duplicate_of_asset_id,
        error=row.error,
    )


def _acquisition_record(row: AcquisitionRunRow) -> AcquisitionRun:
    return AcquisitionRun(
        acquisition_id=row.acquisition_id,
        task_id=row.task_id,
        query=row.query,
        status=cast(AcquisitionStatus, row.status),
        budget=AcquisitionBudget.model_validate_json(row.budget_json),
        candidate_count=row.candidate_count,
        selected_count=row.selected_count,
        downloaded_count=row.downloaded_count,
        indexed_count=row.indexed_count,
        started_at=_deserialize_datetime(row.started_at),
        completed_at=_optional_datetime(row.completed_at),
        error=row.error,
    )


def _serialize_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Persisted datetimes must be timezone-aware")
    return value.astimezone(UTC).isoformat()


def _deserialize_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Persisted datetime is missing timezone information")
    return parsed.astimezone(UTC)


def _optional_datetime(value: str | None) -> datetime | None:
    return _deserialize_datetime(value) if value is not None else None
