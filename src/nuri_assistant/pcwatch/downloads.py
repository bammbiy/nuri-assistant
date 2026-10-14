from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path


TEMP_SUFFIXES = (".crdownload", ".part", ".tmp", ".download")


def count_waiting(folder: Path, extensions: tuple[str, ...], named: re.Pattern | None) -> int:
    """Count files directly in folder that still wait to be organized. Never opens files."""

    wanted = {ext.lower() if ext.startswith(".") else "." + ext.lower() for ext in extensions}
    try:
        entries = list(Path(folder).iterdir())
    except OSError:
        return 0
    count = 0
    for path in entries:
        name = path.name
        if name.startswith(".") or name.startswith("~$"):
            continue
        suffix = path.suffix.lower()
        if suffix in TEMP_SUFFIXES or suffix not in wanted:
            continue
        try:
            if not path.is_file():
                continue
        except OSError:
            continue
        if named is not None and named.fullmatch(path.stem):
            continue
        count += 1
    return count


class DownloadNudge:
    def __init__(self, threshold: int = 10, gap: timedelta = timedelta(hours=24)) -> None:
        self.threshold = threshold
        self.gap = gap
        self.last: datetime | None = None

    def due(self, now: datetime, waiting: int) -> bool:
        if self.threshold <= 0 or waiting < self.threshold:
            return False
        return self.last is None or now - self.last >= self.gap

    def mark(self, now: datetime) -> None:
        self.last = now
