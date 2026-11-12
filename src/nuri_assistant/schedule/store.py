from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from ..db import connect
from .timeparse import format_when

if TYPE_CHECKING:
    from .ical import CalendarEvent


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
    source: str = ""  # "" = made in the app, otherwise the import source (e.g. "ical")

    @property
    def imported(self) -> bool:
        return self.source != ""

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
            columns = {row[1] for row in conn.execute("PRAGMA table_info(schedule_events)")}
            if "source" not in columns:
                conn.execute("ALTER TABLE schedule_events ADD COLUMN source TEXT NOT NULL DEFAULT ''")
            if "external_id" not in columns:
                conn.execute("ALTER TABLE schedule_events ADD COLUMN external_id TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_schedule_start ON schedule_events (start)")

    def _connect(self) -> AbstractContextManager[sqlite3.Connection]:
        return connect(self.db_path, rows=True)

    @staticmethod
    def _event(row: sqlite3.Row) -> Event:
        return Event(
            id=row["id"],
            title=row["title"],
            start=datetime.fromisoformat(row["start"]),
            all_day=bool(row["all_day"]),
            remind_at=datetime.fromisoformat(row["remind_at"]) if row["remind_at"] else None,
            reminded=bool(row["reminded"]),
            source=row["source"] or "",
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
        """Delete an app-made event. Imported events are refused (the next sync would bring them back)."""

        with self._connect() as conn:
            return conn.execute("DELETE FROM schedule_events WHERE id = ? AND source = ''", (event_id,)).rowcount > 0

    def sync_imported(self, source: str, events: list[CalendarEvent], now: datetime) -> int:
        """Make the rows of `source` match `events` in one transaction; returns the resulting row count."""

        wanted = {f"{e.uid}|{e.start.isoformat()}": e for e in events}
        with self._connect() as conn:
            existing = {
                row["external_id"]: row["id"]
                for row in conn.execute("SELECT id, external_id FROM schedule_events WHERE source = ?", (source,))
            }
            for external_id, row_id in existing.items():
                if external_id not in wanted:
                    conn.execute("DELETE FROM schedule_events WHERE id = ?", (row_id,))
            for external_id, event in wanted.items():
                if external_id in existing:
                    conn.execute("UPDATE schedule_events SET title = ? WHERE id = ?", (event.title, existing[external_id]))
                    continue
                remind_at = default_remind_at(event.start, event.all_day, now)
                conn.execute(
                    "INSERT INTO schedule_events (title, start, all_day, remind_at, created_at, source, external_id)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (event.title, event.start.isoformat(timespec="minutes"), int(event.all_day),
                     remind_at.isoformat(timespec="minutes") if remind_at else None,
                     now.isoformat(timespec="seconds"), source, external_id),
                )
            return conn.execute("SELECT COUNT(*) FROM schedule_events WHERE source = ?", (source,)).fetchone()[0]

    def clear_imported(self, source: str) -> int:
        with self._connect() as conn:
            return conn.execute("DELETE FROM schedule_events WHERE source = ?", (source,)).rowcount

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
