from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


WEEKDAYS = "월화수목금토일"


@dataclass(frozen=True)
class When:
    start: datetime
    all_day: bool


class WhenError(ValueError):
    pass


# Native Korean hour words ("세 시 반") → digits, longest first.
_NATIVE_HOURS = (
    ("열한", 11), ("열두", 12), ("다섯", 5), ("여섯", 6), ("일곱", 7), ("여덟", 8), ("아홉", 9),
    ("열", 10), ("한", 1), ("두", 2), ("세", 3), ("네", 4),
)
_NATIVE_HOUR = re.compile(r"(?<![가-힣])(" + "|".join(word for word, _ in _NATIVE_HOURS) + r")\s*시(?!간)")
_NATIVE_MINUTES = (("한", 1), ("두", 2), ("세", 3), ("네", 4), ("다섯", 5), ("여섯", 6), ("일곱", 7), ("여덟", 8), ("아홉", 9), ("열", 10))
_NATIVE_HOURS_SPAN = re.compile(r"(?<![가-힣])(" + "|".join(word for word, _ in _NATIVE_MINUTES) + r")\s*시간")

_AM = ("오전", "새벽", "아침")
_PM = ("오후", "저녁", "밤")


def _add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


class _Text:
    """Text that patterns are consumed from, so one phrase is never read twice."""

    def __init__(self, text: str) -> None:
        self.text = text

    def take(self, pattern: str) -> re.Match[str] | None:
        match = re.search(pattern, self.text)
        if match:
            self.text = self.text[: match.start()] + " " * (match.end() - match.start()) + self.text[match.end():]
        return match

    def has(self, *words: str) -> bool:
        return any(word in self.text for word in words)


def _normalize(text: str) -> str:
    # Space after period words so "오후세시" still reads as 오후 + 세 시.
    text = re.sub(r"(오전|오후|새벽|아침|점심|저녁|밤)", r"\1 ", text.strip())
    text = _NATIVE_HOUR.sub(lambda m: f"{dict(_NATIVE_HOURS)[m.group(1)]}시", text)
    text = _NATIVE_HOURS_SPAN.sub(lambda m: f"{dict(_NATIVE_MINUTES)[m.group(1)]}시간", text)
    return text.replace("담주", "다음 주").replace("다음주", "다음 주").replace("이번주", "이번 주")


def _parse_date(t: _Text, today: date) -> date | None:
    if m := t.take(r"(\d{4})\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})\s*일?"):
        return date(int(m[1]), int(m[2]), int(m[3]))
    if m := t.take(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일") or t.take(r"(?<![\d:])(\d{1,2})\s*/\s*(\d{1,2})(?![\d:])"):
        day = date(today.year, int(m[1]), int(m[2]))
        return day if day >= today else date(today.year + 1, day.month, day.day)
    if t.take(r"내일\s*모레"):
        return today + timedelta(days=2)
    for word, days in (("오늘", 0), ("내일", 1), ("모레", 2), ("글피", 3)):
        if t.take(word):
            return today + timedelta(days=days)
    if m := t.take(r"(\d+)\s*일\s*(뒤|후)"):
        return today + timedelta(days=int(m[1]))
    if m := t.take(r"(\d+)\s*주\s*(뒤|후)"):
        return today + timedelta(weeks=int(m[1]))
    if m := t.take(r"(\d+)\s*(개월|달)\s*(뒤|후)"):
        return _add_months(today, int(m[1]))
    if m := t.take(r"(다다음\s*주|다음\s*주|이번\s*주|저번\s*주|지난\s*주)?\s*([월화수목금토일])\s*요일"):
        weekday = WEEKDAYS.index(m[2])
        prefix = (m[1] or "").replace(" ", "")
        if not prefix:
            return today + timedelta(days=(weekday - today.weekday()) % 7)
        weeks = {"이번주": 0, "다음주": 1, "다다음주": 2, "저번주": -1, "지난주": -1}[prefix]
        monday = today - timedelta(days=today.weekday())
        return monday + timedelta(weeks=weeks, days=weekday)
    if t.take(r"주말"):
        return today + timedelta(days=max(5 - today.weekday(), 0))
    if m := t.take(r"(다음|이번)\s*달\s*(\d{1,2})\s*일"):
        base = _add_months(today.replace(day=1), 1 if m[1] == "다음" else 0)
        return base.replace(day=min(int(m[2]), calendar.monthrange(base.year, base.month)[1]))
    if m := t.take(r"(?<![\d월/])(\d{1,2})\s*일(?!\s*(뒤|후|간|동안))"):
        day = int(m[1])
        if not 1 <= day <= 31:
            return None
        base = today.replace(day=1)
        if day < today.day:
            base = _add_months(base, 1)
        return base.replace(day=min(day, calendar.monthrange(base.year, base.month)[1]))
    return None


def _parse_relative(t: _Text) -> timedelta | None:
    if m := t.take(r"(\d+)\s*시간\s*(\d+)\s*분\s*(뒤|후|있다가)"):
        return timedelta(hours=int(m[1]), minutes=int(m[2]))
    if m := t.take(r"(\d+)\s*시간\s*(반)?\s*(뒤|후|있다가)"):
        return timedelta(hours=int(m[1]), minutes=30 if m[2] else 0)
    if m := t.take(r"(\d+)\s*분\s*(뒤|후|있다가)"):
        return timedelta(minutes=int(m[1]))
    if t.take(r"반\s*시간\s*(뒤|후|있다가)"):
        return timedelta(minutes=30)
    return None


def _parse_time(t: _Text) -> tuple[time, bool] | None:
    """Return (time, next_day) — next_day for '밤 12시' / '자정'."""

    am = t.has(*_AM)
    pm = t.has(*_PM)
    lunch = t.has("점심")
    hour = minute = None
    if m := t.take(r"(\d{1,2})\s*:\s*(\d{2})"):
        hour, minute = int(m[1]), int(m[2])
    elif m := t.take(r"(\d{1,2})\s*시(?!간)\s*(?:(\d{1,2})\s*분|(반))?"):
        hour = int(m[1])
        minute = int(m[2]) if m[2] else 30 if m[3] else 0
    if hour is None:
        if t.take("정오"):
            return time(12, 0), False
        if t.take("자정"):
            return time(0, 0), True
        for word, default in (("새벽", 6), ("아침", 9), ("점심", 12), ("오전", 10), ("오후", 14), ("저녁", 19), ("밤", 21)):
            if t.has(word):
                return time(default, 0), False
        return None
    if hour > 24 or minute > 59:
        raise WhenError("시간을 이해하지 못했어요.")
    if hour == 24:
        return time(0, minute), True
    if t.has("새벽") and hour == 12:
        hour = 0
    elif pm or (lunch and hour <= 3):
        if hour < 12:
            hour += 12
        elif t.has("밤"):  # 밤 12시
            return time(0, minute), True
    elif am:
        if hour == 12:
            hour = 0
    elif 1 <= hour <= 6:
        # No 오전/오후: "3시 회의" almost always means the afternoon.
        hour += 12
    return time(hour, minute), False


def parse_when(text: str, now: datetime) -> When:
    """Resolve a Korean date/time phrase ("내일 오후 3시", "다음 주 화요일") against now."""

    t = _Text(_normalize(text))
    today = now.date()
    if delta := _parse_relative(t):
        return When((now + delta).replace(second=0, microsecond=0), False)
    day = _parse_date(t, today)
    clock = _parse_time(t)
    if day is None and clock is None:
        raise WhenError(f"'{text}'에서 날짜나 시간을 찾지 못했어요.")
    if clock is None:
        if day < today:
            raise WhenError("이미 지난 날짜예요.")
        return When(datetime.combine(day, time(0, 0)), True)
    moment, next_day = clock
    start = datetime.combine(day or today, moment) + timedelta(days=1 if next_day else 0)
    if day is None and start <= now:
        # "3시 회의" said after 3pm means tomorrow.
        start += timedelta(days=1)
    if start < now - timedelta(minutes=1):
        raise WhenError("이미 지난 시간이에요.")
    return When(start, False)


def parse_range(text: str, now: datetime) -> tuple[datetime, datetime, str]:
    """Range for listing events: 오늘, 내일, 이번 주, 다음 주, 이번 달, a date, or the next 7 days."""

    today = datetime.combine(now.date(), time(0, 0))
    phrase = _normalize(text or "")
    monday = today - timedelta(days=today.weekday())
    if "다음 주" in phrase:
        return monday + timedelta(weeks=1), monday + timedelta(weeks=2), "다음 주"
    if "이번 주" in phrase or phrase.strip() in {"주간", "이번주"}:
        return today, monday + timedelta(weeks=1), "이번 주"
    if "다음 달" in phrase:
        first = datetime.combine(_add_months(today.date().replace(day=1), 1), time(0, 0))
        return first, datetime.combine(_add_months(first.date(), 1), time(0, 0)), "다음 달"
    if "이번 달" in phrase:
        first = today.replace(day=1)
        return today, datetime.combine(_add_months(first.date(), 1), time(0, 0)), "이번 달"
    t = _Text(phrase)
    day = _parse_date(t, today.date()) if phrase.strip() else None
    if day is not None:
        start = datetime.combine(day, time(0, 0))
        label = "오늘" if day == today.date() else "내일" if day == today.date() + timedelta(days=1) else format_day(day)
        return start, start + timedelta(days=1), label
    return now, today + timedelta(days=8), "앞으로 일주일"


def format_day(day: date) -> str:
    return f"{day.month}/{day.day}({WEEKDAYS[day.weekday()]})"


def format_when(start: datetime, all_day: bool) -> str:
    return f"{format_day(start.date())} {'하루 종일' if all_day else start.strftime('%H:%M')}"
