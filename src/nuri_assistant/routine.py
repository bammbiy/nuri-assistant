"""When the daily routine lines are due: the morning briefing and the evening wrap-up. No Tk."""
from __future__ import annotations

import re
from datetime import datetime, time, timedelta


def parse_clock(text: str) -> time | None:
    """'8:30', '08:30', '18시', '18시 30분' -> time; '' or nonsense -> None (feature off / at start-up)."""

    match = re.fullmatch(r"\s*(\d{1,2})\s*(?:[:시]\s*(\d{1,2})?\s*분?)?\s*", text or "")
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2) or 0)
    return time(hour, minute) if hour < 24 and minute < 60 else None


def daily_due(now: datetime, clock: time | None, last_done: str, window: timedelta | None = None) -> bool:
    """True once a day from the clock time on; with a window, only until clock + window
    (an app started much later skips it that day instead of saying it at midnight)."""

    if clock is None or last_done == now.date().isoformat():
        return False
    start = datetime.combine(now.date(), clock)
    return start <= now and (window is None or now < start + window)


def duration_text(minutes: int) -> str:
    """40 -> '40분', 80 -> '1시간 20분', 120 -> '2시간'."""

    hours, rest = divmod(max(int(minutes), 0), 60)
    if not hours:
        return f"{rest}분"
    return f"{hours}시간 {rest}분" if rest else f"{hours}시간"
