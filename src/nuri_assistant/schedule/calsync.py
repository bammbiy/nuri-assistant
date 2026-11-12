"""Read-only calendar import: fetch iCal text from a URL or file and mirror it into the schedule store."""
from __future__ import annotations

import urllib.error
import urllib.request
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Callable

from .ical import CalendarEvent, parse_ics
from .store import ScheduleStore


SOURCE = "ical"
WINDOW_DAYS = 90
MAX_BYTES = 5 * 1024 * 1024
MAX_CALENDARS = 3


class CalendarError(RuntimeError):
    """A calendar could not be read; the message is one Korean line for the user."""


def read_source(location: str, timeout: float = 15) -> str:
    """Return the iCal text of an http(s)/webcal address or a local file path."""

    location = location.strip()
    lowered = location.lower()
    if lowered.startswith(("http://", "https://", "webcal://")):
        if lowered.startswith("webcal://"):
            location = "https://" + location[len("webcal://"):]
        try:
            request = urllib.request.Request(location, headers={"User-Agent": "nuri-assistant"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(MAX_BYTES)
        except (OSError, ValueError) as exc:  # URLError and timeouts are OSError subclasses
            raise CalendarError("캘린더 주소에 연결하지 못했어요. 주소와 인터넷 연결을 확인해 주세요.") from exc
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace")
    try:
        with open(Path(location).expanduser(), "rb") as handle:
            raw = handle.read(MAX_BYTES)
    except OSError as exc:
        raise CalendarError("캘린더 파일을 읽지 못했어요. 경로를 확인해 주세요.") from exc
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def sync_calendars(
    store: ScheduleStore,
    locations: list[str],
    now: datetime,
    read: Callable[[str], str] = read_source,
    parse: Callable[..., list[CalendarEvent]] = parse_ics,
) -> int:
    """Mirror all calendars into the store; returns the number of imported events.

    Any unreadable calendar aborts with CalendarError and leaves the stored events untouched,
    so a passing network error never wipes the schedule.
    """

    cleaned = [line.strip() for line in locations if line and line.strip()][:MAX_CALENDARS]
    if not cleaned:
        store.clear_imported(SOURCE)
        return 0
    window_start = datetime.combine(now.date(), time(0, 0)) - timedelta(days=1)
    window_end = now + timedelta(days=WINDOW_DAYS)
    merged: dict[tuple[str, datetime], CalendarEvent] = {}
    for location in cleaned:
        text = read(location)
        for event in parse(text, window_start, window_end):
            merged.setdefault((event.uid, event.start), event)
    return store.sync_imported(SOURCE, list(merged.values()), now)
