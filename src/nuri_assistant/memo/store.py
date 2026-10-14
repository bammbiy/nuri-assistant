from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..db import connect


@dataclass(frozen=True)
class Memo:
    id: int
    text: str
    created_at: datetime


class MemoStore:
    """Facts about the user that every character remembers, in the shared local SQLite file."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> AbstractContextManager[sqlite3.Connection]:
        return connect(self.db_path, rows=True)

    @staticmethod
    def _memo(row: sqlite3.Row) -> Memo:
        return Memo(row["id"], row["text"], datetime.fromisoformat(row["created_at"]))

    def add(self, text: str) -> Memo:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO memos (text, created_at) VALUES (?, ?)",
                (text.strip(), datetime.now().isoformat(timespec="seconds")),
            )
            row = conn.execute("SELECT * FROM memos WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._memo(row)

    def all(self) -> list[Memo]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM memos ORDER BY id").fetchall()
        return [self._memo(row) for row in rows]

    def delete(self, memo_id: int) -> bool:
        with self._connect() as conn:
            return conn.execute("DELETE FROM memos WHERE id = ?", (memo_id,)).rowcount > 0

    def find(self, keyword: str) -> list[Memo]:
        keyword = keyword.strip()
        if not keyword:
            return []
        return [memo for memo in self.all() if keyword in memo.text]
