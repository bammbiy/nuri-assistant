"""Holidays and the first day of each season, for the day's greeting. No Tk, no lunar library."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Holiday:
    kind: str  # "holiday" | "season"
    name: str


_FIXED = {
    (1, 1): "새해", (2, 14): "밸런타인데이", (3, 14): "화이트데이", (10, 31): "핼러윈",
    (11, 11): "빼빼로데이", (12, 24): "크리스마스 이브", (12, 25): "크리스마스", (12, 31): "한 해 마지막 날",
}
# Lunar holidays as solar dates; only the years in this table are known.
_LUNAR = {
    date(2026, 2, 17): "설날", date(2027, 2, 7): "설날", date(2028, 1, 27): "설날",
    date(2029, 2, 13): "설날", date(2030, 2, 3): "설날",
    date(2026, 9, 25): "추석", date(2027, 9, 15): "추석", date(2028, 10, 3): "추석",
    date(2029, 9, 22): "추석", date(2030, 9, 12): "추석",
}
_SEASONS = {(3, 1): "봄", (6, 1): "여름", (9, 1): "가을", (12, 1): "겨울"}


def holiday_today(day: date) -> Holiday | None:
    name = _FIXED.get((day.month, day.day)) or _LUNAR.get(day)
    if name:
        return Holiday("holiday", name)
    name = _SEASONS.get((day.month, day.day))
    return Holiday("season", name) if name else None
