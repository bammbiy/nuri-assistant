from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Iterator

from .timeparse import format_when


DEFAULT_REMIND_MINUTES = 10
ALL_DAY_REMIND = time(9, 0)


@dataclass(frozen=True)
class Event:
    id: int
    title: str
    start: datetime
    all_day: bool
    remind_at: datetime | None
    reminded: bool

    @property
    def when(self) -> str:
        return format_when(self.start, self.all_day)


def default_remind_at(start: datetime, all_day: bool, now: datetime, minutes: int | None = None) -> datetime | None:
    """Timed events: N minutes before (now, if that already passed). All-day: 09:00 that day."""

    if all_day:
        remind = datetime.combine(start.date(), ALL_DAY_REMIND)
        return remind if remind > now else None
    remind = start - timedelta(minutes=DEFAULT_REMIND_MINUTES if minutes is None else minutes)
    return max(remind, now) if start > now else None


class ScheduleStore:
    """Events in a local SQLite file (shared with the conversation memory)."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schedule_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    start TEXT NOT NULL,
                    all_day INTEGER NOT NULL DEFAULT 0,
                    remind_at TEXT,
                    reminded INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_schedule_start ON schedule_events (start)")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _event(row: sqlite3.Row) -> Event:
        return Event(
            id=row["id"],
            title=row["title"],
            start=datetime.fromisoformat(row["start"]),
            all_day=bool(row["all_day"]),
            remind_at=datetime.fromisoformat(row["remind_at"]) if row["remind_at"] else None,
            reminded=bool(row["reminded"]),
        )

    def add(self, title: str, start: datetime, all_day: bool, remind_at: datetime | None) -> Event:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO schedule_events (title, start, all_day, remind_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (title, start.isoformat(timespec="minutes"), int(all_day),
                 remind_at.isoformat(timespec="minutes") if remind_at else None,
                 datetime.now().isoformat(timespec="seconds")),
            )
            event_id = cursor.lastrowid
        return self.get(event_id)

    def get(self, event_id: int) -> Event | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM schedule_events WHERE id = ?", (event_id,)).fetchone()
        return self._event(row) if row else None

    def delete(self, event_id: int) -> bool:
        with self._connect() as conn:
            return conn.execute("DELETE FROM schedule_events WHERE id = ?", (event_id,)).rowcount > 0

    def between(self, start: datetime, end: datetime) -> list[Event]:
        """Events starting in [start, end); all-day events count for their whole day."""

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM schedule_events
                WHERE (all_day = 0 AND start >= ? AND start < ?)
                   OR (all_day = 1 AND start >= ? AND start < ?)
                ORDER BY start, id
                """,
                (start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes"),
                 datetime.combine(start.date(), time(0, 0)).isoformat(timespec="minutes"),
                 end.isoformat(timespec="minutes")),
            ).fetchall()
        return [self._event(row) for row in rows]

    def due_reminders(self, now: datetime) -> list[Event]:
        """Reminders that are due and not yet shown; long-missed ones (app was off) are skipped."""

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM schedule_events
                WHERE reminded = 0 AND remind_at IS NOT NULL AND remind_at <= ? AND remind_at >= ?
                ORDER BY remind_at, id
                """,
                (now.isoformat(timespec="minutes"), (now - timedelta(hours=1)).isoformat(timespec="minutes")),
            ).fetchall()
        return [self._event(row) for row in rows]

    def mark_reminded(self, event_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE schedule_events SET reminded = 1 WHERE id = ?", (event_id,))
