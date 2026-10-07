from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path

from ..db import connect


class ConversationStore:
    """Per-character chat log kept in a local SQLite file."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS companion_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    persona_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_companion_persona ON companion_messages (persona_id, id)"
            )

    def _connect(self) -> AbstractContextManager[sqlite3.Connection]:
        return connect(self.db_path)

    def add(self, persona_id: str, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError(f"Unsupported role: {role}")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO companion_messages (persona_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (persona_id, role, content, datetime.now().isoformat(timespec="seconds")),
            )

    def recent(self, persona_id: str, limit: int = 20) -> list[dict[str, str]]:
        """Return the last ``limit`` messages, oldest first."""

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT role, content, created_at
                FROM companion_messages
                WHERE persona_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (persona_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def clear(self, persona_id: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM companion_messages WHERE persona_id = ?", (persona_id,))
        return cursor.rowcount
