"""Lifecycle wrapper around the LangGraph SQLite checkpointer."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver


class SqliteCheckpointStore:
    """Own the SQLite connection used by LangGraph checkpoints."""

    storage_name = "sqlite"

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            self.path,
            check_same_thread=False,
            timeout=30,
        )
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA busy_timeout=30000")
        self.saver = SqliteSaver(self._connection)
        self.saver.setup()
        self._closed = False

    def has_checkpoint(self, thread_id: str) -> bool:
        if self._closed:
            return False
        return (
            self.saver.get_tuple({"configurable": {"thread_id": thread_id}})
            is not None
        )

    def probe(self) -> tuple[bool, str | None]:
        if self._closed:
            return False, "Checkpoint Store is closed"
        try:
            self._connection.execute("SELECT 1").fetchone()
        except sqlite3.Error as exc:
            return False, f"{type(exc).__name__}: {exc}"
        return True, None

    def close(self) -> None:
        if self._closed:
            return
        self._connection.close()
        self._closed = True
