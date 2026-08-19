"""SQLite implementation of the durable research Repository."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Literal, cast

from sqlalchemy import URL, Engine, create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from paper_research_copilot.storage.migrations import upgrade_database
from paper_research_copilot.storage.models import ResearchEventRow, ResearchTaskRow
from paper_research_copilot.storage.repositories import (
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
