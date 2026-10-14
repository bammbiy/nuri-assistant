from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path

from ..db import connect


LEVELS = ((0, "처음"), (30, "친근"), (100, "가까움"), (250, "단짝"))  # (min points, name)
POINTS = {"chat": 1, "todo_done": 3, "focus_done": 3, "approved": 1}
DAILY_CHAT_CAP = 30  # chat points per persona per day
DAILY_CAP = 40  # all points per persona per day, whatever the reason


def level_index(points: int) -> int:
    index = 0
    for i, (minimum, _name) in enumerate(LEVELS):
        if points >= minimum:
            index = i
    return index


class AffectionStore:
    """Closeness points per character in the shared local SQLite file. Points never decrease."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS affection (
                    persona_id TEXT PRIMARY KEY,
                    points INTEGER NOT NULL DEFAULT 0,
                    chat_date TEXT,
                    chat_count INTEGER NOT NULL DEFAULT 0,
                    day_total INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(affection)")}
            if "day_total" not in columns:
                conn.execute("ALTER TABLE affection ADD COLUMN day_total INTEGER NOT NULL DEFAULT 0")

    def _connect(self) -> AbstractContextManager[sqlite3.Connection]:
        return connect(self.db_path, rows=True)

    def points(self, persona_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT points FROM affection WHERE persona_id = ?", (persona_id,)).fetchone()
        return row["points"] if row else 0

    def level(self, persona_id: str) -> tuple[int, str]:
        index = level_index(self.points(persona_id))
        return index, LEVELS[index][1]

    def hearts(self, persona_id: str) -> str:
        filled = self.level(persona_id)[0] + 1
        return "♥" * filled + "♡" * (len(LEVELS) - filled)

    def next_threshold(self, persona_id: str) -> int | None:
        index = self.level(persona_id)[0]
        return LEVELS[index + 1][0] if index + 1 < len(LEVELS) else None

    def add(self, persona_id: str, reason: str, now: datetime) -> int | None:
        """Add points for a reason; returns the new level index if this crossed into a higher level."""

        gain = POINTS.get(reason)
        if gain is None:
            raise ValueError(f"알 수 없는 친밀도 사유: {reason}")
        today = now.date().isoformat()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM affection WHERE persona_id = ?", (persona_id,)).fetchone()
            points = row["points"] if row else 0
            chat_date = row["chat_date"] if row else None
            chat_count = row["chat_count"] if row else 0
            if chat_date != today:
                chat_count = 0
            day_total = row["day_total"] if row else 0
            if (row["chat_date"] if row else None) != today:
                day_total = 0
            if day_total >= DAILY_CAP:
                return None
            if reason == "chat":
                if chat_count >= DAILY_CHAT_CAP:
                    return None
                chat_count += 1
                chat_date = today
            chat_date = today
            day_total += gain
            new_points = points + gain
            conn.execute(
                "INSERT INTO affection (persona_id, points, chat_date, chat_count, day_total) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(persona_id) DO UPDATE SET points = excluded.points, "
                "chat_date = excluded.chat_date, chat_count = excluded.chat_count, day_total = excluded.day_total",
                (persona_id, new_points, chat_date, chat_count, day_total),
            )
        before, after = level_index(points), level_index(new_points)
        return after if after > before else None
