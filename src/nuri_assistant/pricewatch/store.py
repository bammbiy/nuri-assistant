from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..db import connect


@dataclass(frozen=True)
class Watch:
    id: int
    query: str
    url: str
    target_price: int | None
    lowest_seen: int | None
    last_price: int | None
    last_mall: str
    last_link: str
    last_checked: datetime | None
    notified_price: int | None
    last_error: str

    @property
    def label(self) -> str:
        return self.query or self.url


class WatchStore:
    """Price watches and their price history in the local SQLite file."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS price_watches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL DEFAULT '',
                    target_price INTEGER,
                    lowest_seen INTEGER,
                    last_price INTEGER,
                    last_mall TEXT NOT NULL DEFAULT '',
                    last_link TEXT NOT NULL DEFAULT '',
                    last_checked TEXT,
                    notified_price INTEGER,
                    last_error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS price_history (
                    watch_id INTEGER NOT NULL,
                    price INTEGER NOT NULL,
                    mall TEXT NOT NULL,
                    checked_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> AbstractContextManager[sqlite3.Connection]:
        return connect(self.db_path, rows=True)

    @staticmethod
    def _watch(row: sqlite3.Row) -> Watch:
        return Watch(
            id=row["id"], query=row["query"], url=row["url"], target_price=row["target_price"],
            lowest_seen=row["lowest_seen"], last_price=row["last_price"], last_mall=row["last_mall"],
            last_link=row["last_link"],
            last_checked=datetime.fromisoformat(row["last_checked"]) if row["last_checked"] else None,
            notified_price=row["notified_price"], last_error=row["last_error"],
        )

    def add(self, query: str, url: str = "", target_price: int | None = None) -> Watch:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO price_watches (query, url, target_price, created_at) VALUES (?, ?, ?, ?)",
                (query.strip(), url.strip(), target_price, datetime.now().isoformat(timespec="seconds")),
            )
            watch_id = cursor.lastrowid
        return self.get(watch_id)

    def get(self, watch_id: int) -> Watch | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM price_watches WHERE id = ?", (watch_id,)).fetchone()
        return self._watch(row) if row else None

    def all(self) -> list[Watch]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM price_watches ORDER BY id").fetchall()
        return [self._watch(row) for row in rows]

    def delete(self, watch_id: int) -> bool:
        with self._connect() as conn:
            conn.execute("DELETE FROM price_history WHERE watch_id = ?", (watch_id,))
            return conn.execute("DELETE FROM price_watches WHERE id = ?", (watch_id,)).rowcount > 0

    def record(self, watch_id: int, price: int, mall: str, link: str, now: datetime, notified: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE price_watches
                SET last_price = ?, last_mall = ?, last_link = ?, last_checked = ?, last_error = '',
                    lowest_seen = CASE WHEN lowest_seen IS NULL OR ? < lowest_seen THEN ? ELSE lowest_seen END,
                    notified_price = CASE WHEN ? THEN ? ELSE notified_price END
                WHERE id = ?
                """,
                (price, mall, link, now.isoformat(timespec="seconds"), price, price, int(notified), price, watch_id),
            )
            conn.execute(
                "INSERT INTO price_history (watch_id, price, mall, checked_at) VALUES (?, ?, ?, ?)",
                (watch_id, price, mall, now.isoformat(timespec="seconds")),
            )

    def record_error(self, watch_id: int, error: str, now: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE price_watches SET last_error = ?, last_checked = ? WHERE id = ?",
                (error, now.isoformat(timespec="seconds"), watch_id),
            )

    def history(self, watch_id: int, limit: int = 100) -> list[tuple[datetime, int, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT checked_at, price, mall FROM price_history WHERE watch_id = ? ORDER BY checked_at DESC LIMIT ?",
                (watch_id, limit),
            ).fetchall()
        return [(datetime.fromisoformat(row["checked_at"]), row["price"], row["mall"]) for row in rows]
