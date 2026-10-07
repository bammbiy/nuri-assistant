from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from ..db import connect
from ..schedule.timeparse import format_day


EVE_NAG = time(19, 0)  # evening before the due date
DAY_NAG = time(9, 0)   # morning of the due date


@dataclass(frozen=True)
class Todo:
    id: int
    title: str
    due: datetime | None
    all_day: bool
    done: bool

    @property
    def due_text(self) -> str:
        if self.due is None:
            return "기한 없음"
        return f"{format_day(self.due.date())}{'' if self.all_day else ' ' + self.due.strftime('%H:%M')}까지"

    def d_day(self, today: date) -> str:
        if self.due is None:
            return ""
        days = (self.due.date() - today).days
        return "오늘" if days == 0 else f"D-{days}" if days > 0 else f"{-days}일 지남"


class TodoStore:
    """To-dos with optional due dates in the shared local SQLite file."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    due TEXT,
                    all_day INTEGER NOT NULL DEFAULT 1,
                    done INTEGER NOT NULL DEFAULT 0,
                    nag_eve INTEGER NOT NULL DEFAULT 0,
                    nag_day INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    done_at TEXT
                )
                """
            )

    def _connect(self) -> AbstractContextManager[sqlite3.Connection]:
        return connect(self.db_path, rows=True)

    @staticmethod
    def _todo(row: sqlite3.Row) -> Todo:
        return Todo(row["id"], row["title"], datetime.fromisoformat(row["due"]) if row["due"] else None,
                    bool(row["all_day"]), bool(row["done"]))

    def add(self, title: str, due: datetime | None = None, all_day: bool = True) -> Todo:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO todos (title, due, all_day, created_at) VALUES (?, ?, ?, ?)",
                (title.strip(), due.isoformat(timespec="minutes") if due else None, int(all_day),
                 datetime.now().isoformat(timespec="seconds")),
            )
            todo_id = cursor.lastrowid
        return self.get(todo_id)

    def get(self, todo_id: int) -> Todo | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        return self._todo(row) if row else None

    def open(self) -> list[Todo]:
        """Unfinished to-dos, earliest due first, undated last."""

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM todos WHERE done = 0 ORDER BY due IS NULL, due, id"
            ).fetchall()
        return [self._todo(row) for row in rows]

    def recently_done(self, limit: int = 10) -> list[Todo]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM todos WHERE done = 1 ORDER BY done_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._todo(row) for row in rows]

    def set_done(self, todo_id: int, done: bool = True) -> bool:
        with self._connect() as conn:
            return conn.execute(
                "UPDATE todos SET done = ?, done_at = ? WHERE id = ?",
                (int(done), datetime.now().isoformat(timespec="seconds") if done else None, todo_id),
            ).rowcount > 0

    def delete(self, todo_id: int) -> bool:
        with self._connect() as conn:
            return conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,)).rowcount > 0

    def due_nags(self, now: datetime) -> list[tuple[Todo, str]]:
        """("eve", todo) the evening before the due date, ("day", todo) on the morning of it."""

        nags = []
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM todos WHERE done = 0 AND due IS NOT NULL").fetchall()
        for row in rows:
            todo = self._todo(row)
            due_day = todo.due.date()
            if due_day == now.date() + timedelta(days=1) and now.time() >= EVE_NAG and not row["nag_eve"]:
                nags.append((todo, "eve"))
            elif due_day == now.date() and now.time() >= DAY_NAG and not row["nag_day"]:
                nags.append((todo, "day"))
        return nags

    def mark_nagged(self, todo_id: int, kind: str) -> None:
        column = {"eve": "nag_eve", "day": "nag_day"}[kind]
        with self._connect() as conn:
            conn.execute(f"UPDATE todos SET {column} = 1 WHERE id = ?", (todo_id,))  # noqa: S608 - fixed column names
