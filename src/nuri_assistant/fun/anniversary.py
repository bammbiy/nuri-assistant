from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


MILESTONES = (100, 200, 300, 500, 1000)


@dataclass(frozen=True)
class Occasion:
    kind: str
    days: int = 0


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _on_day(year: int, month: int, day: int) -> date:
    if month == 2 and day == 29 and not _is_leap(year):
        return date(year, 2, 28)
    return date(year, month, day)


def _parse_iso(text: str) -> date | None:
    try:
        return date.fromisoformat(str(text or "").strip())
    except ValueError:
        return None


def occasion_today(today: date, birthday: str, first_met: str) -> Occasion | None:
    month_day = parse_birthday(birthday) if birthday else None
    if month_day:
        month, day = int(month_day[:2]), int(month_day[3:])
        if _on_day(today.year, month, day) == today:
            return Occasion("birthday")
    met = _parse_iso(first_met)
    if met and met < today:
        days = (today - met).days
        if days in MILESTONES:
            return Occasion("together", days)
        if today.year > met.year and _on_day(today.year, met.month, met.day) == today:
            return Occasion("together", days)
    return None


def parse_birthday(text: str) -> str | None:
    s = str(text or "").strip()
    match = (re.fullmatch(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일?", s)
             or re.fullmatch(r"(\d{1,2})\s*[-/.]\s*(\d{1,2})", s)
             or re.fullmatch(r"(\d{2})(\d{2})", s))
    if not match:
        return None
    month, day = int(match.group(1)), int(match.group(2))
    try:
        date(2000, month, day)  # 2000 is a leap year, so 02-29 is accepted
    except ValueError:
        return None
    return f"{month:02d}-{day:02d}"
