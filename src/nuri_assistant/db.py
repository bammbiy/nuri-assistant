"""One way to open the app's SQLite files, shared by every store."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def connect(db_path: Path, rows: bool = False) -> Iterator[sqlite3.Connection]:
    """Commit on success, roll back on error, and always close.

    sqlite3's own context manager commits but never closes, which keeps the file locked on
    Windows. rows=True returns sqlite3.Row so columns can be read by name.
    """

    conn = sqlite3.connect(db_path)
    if rows:
        conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()
