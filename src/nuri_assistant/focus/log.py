from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path

from ..db import connect


class FocusLog:
    """Finished focus blocks (when, how long), for the evening wrap-up. Stored in companion.sqlite3."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS focus_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ended_at TEXT NOT NULL,
                    minutes INTEGER NOT NULL
                )
                """
            )

    def _connect(self) -> AbstractContextManager[sqlite3.Connection]:
        return connect(self.db_path)

    def add(self, ended_at: datetime, minutes: int) -> None:
        with self._connect() as conn:
            conn.execute("INSERT INTO focus_sessions (ended_at, minutes) VALUES (?, ?)",
                         (ended_at.isoformat(timespec="seconds"), int(minutes)))

    def summary(self, start: datetime, end: datetime) -> tuple[int, int]:
        """(blocks, total minutes) finished in [start, end)."""

        with self._connect() as conn:
            count, minutes = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(minutes), 0) FROM focus_sessions WHERE ended_at >= ? AND ended_at < ?",
                (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
            ).fetchone()
        return int(count), int(minutes)
