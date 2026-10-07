"""Write unexpected errors to ~/.nuri-assistant/error.log so a failed start can be diagnosed.

Started by double-click or pythonw, the app has no console: without this a crash during
start-up just looks like "nothing happens".
"""
from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path

from .paths import ERROR_LOG as LOG_PATH

MAX_BYTES = 512_000


def log_exception(exc_type, value, tb, path: Path = LOG_PATH) -> Path | None:
    """Append the traceback with a timestamp; returns the log path, or None if it could not be written."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > MAX_BYTES:
            path.unlink()
        text = "".join(traceback.format_exception(exc_type, value, tb))
        with path.open("a", encoding="utf-8") as file:
            file.write(f"===== {datetime.now():%Y-%m-%d %H:%M:%S} =====\n{text}\n")
        return path
    except OSError:
        return None


def show_error(title: str, message: str) -> None:
    """Best-effort message box; falls back to stderr when Tk itself is unusable."""

    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message, parent=root)
        root.destroy()
    except Exception:  # noqa: BLE001 - last resort, nothing else to report to
        import sys

        if sys.stderr is not None:
            print(f"{title}\n{message}", file=sys.stderr)
