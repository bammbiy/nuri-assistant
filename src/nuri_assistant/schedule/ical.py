"""Minimal iCalendar (.ics) reader built on the standard library only.

Pure functions: no file or network access. ``parse_ics`` returns the event
occurrences that start inside a window, expressed as naive local wall-clock
datetimes. Anything that cannot be understood is skipped instead of raising.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import Iterator

try:  # Windows may ship without tz data
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment,misc]
    ZoneInfoNotFoundError = KeyError  # type: ignore[assignment,misc]

EMPTY_TITLE = "(제목 없음)"
MAX_TITLE = 120
MAX_ITERATIONS = 40000  # a daily event keeps working for about a century after its first day

_WEEKDAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
_BYDAY_RE = re.compile(r"^([+-]?\d{1,2})?(MO|TU|WE|TH|FR|SA|SU)$")
_SUPPORTED_RULE_KEYS = {"FREQ", "INTERVAL", "COUNT", "UNTIL", "BYDAY", "BYMONTHDAY", "WKST"}


@dataclass(frozen=True)
class CalendarEvent:
    uid: str
    title: str
    start: datetime  # naive, local wall-clock time
    all_day: bool


@dataclass
class _Raw:
    uid: str
    title: str
    wall: datetime
    zone: tzinfo | None
    all_day: bool
    cancelled: bool
    rrule: str | None
    exdates: list[tuple[str, dict[str, str]]]
    recurrence_id: tuple[str, dict[str, str]] | None


def _unfold(text: str) -> list[str]:
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = []
    for line in text.split("\n"):
        if line[:1] in (" ", "\t") and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def _split_line(line: str) -> tuple[str, dict[str, str], str] | None:
    """Split ``NAME;P=V:value`` into (NAME, params, value); quotes are respected."""
    n = len(line)
    i = 0
    while i < n and line[i] not in ";:":
        i += 1
    if i >= n:
        return None
    name = line[:i].strip().upper()
    params: dict[str, str] = {}
    while i < n and line[i] == ";":
        i += 1
        j = i
        while j < n and line[j] not in "=;:":
            j += 1
        pname = line[i:j].strip().upper()
        pval = ""
        if j < n and line[j] == "=":
            j += 1
            vstart = j
            quoted = False
            while j < n:
                c = line[j]
                if c == '"':
                    quoted = not quoted
                elif not quoted and c in ";:":
                    break
                j += 1
            pval = line[vstart:j].strip().strip('"')
        params[pname] = pval
        i = j
    if i >= n or line[i] != ":":
        return None
    return name, params, line[i + 1:]


def _unescape(value: str) -> str:
    def repl(m: re.Match) -> str:
        c = m.group(1)
        return " " if c in "nN" else c
    return re.sub(r"\\(.)", repl, value)


def _make_title(value: str) -> str:
    title = _unescape(value).strip()[:MAX_TITLE].strip()
    return title or EMPTY_TITLE


def _find_zone(tzid: str) -> tzinfo | None:
    if ZoneInfo is None or not tzid:
        return None
    try:
        return ZoneInfo(tzid)
    except (ZoneInfoNotFoundError, ValueError, KeyError, OSError):
        return None


def _parse_value(value: str, params: dict[str, str]) -> tuple[datetime, tzinfo | None, bool, bool]:
    """Return (wall, zone, all_day, has_explicit_zone). Raises ValueError if bad."""
    v = value.strip()
    if params.get("VALUE", "").upper() == "DATE" or re.fullmatch(r"\d{8}", v):
        return datetime.strptime(v, "%Y%m%d"), None, True, False
    if v.endswith(("Z", "z")):
        return _parse_datetime(v[:-1]), timezone.utc, False, True
    wall = _parse_datetime(v)
    tzid = params.get("TZID", "")
    zone = _find_zone(tzid)
    return wall, zone, False, zone is not None


def _parse_datetime(v: str) -> datetime:
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            pass
    raise ValueError(f"bad datetime: {v!r}")


def _to_local(wall: datetime, zone: tzinfo | None, tz: tzinfo | None) -> datetime:
    if zone is None:
        return wall
    return wall.replace(tzinfo=zone).astimezone(tz).replace(tzinfo=None)


def _parse_rule(rrule: str) -> dict[str, str] | None:
    parts: dict[str, str] = {}
    for item in rrule.split(";"):
        if not item.strip():
            continue
        key, sep, val = item.partition("=")
        if not sep:
            return None
        parts[key.strip().upper()] = val.strip()
    return parts


def _parse_byday(value: str) -> list[tuple[int | None, int]] | None:
    out: list[tuple[int | None, int]] = []
    for item in value.upper().split(","):
        m = _BYDAY_RE.match(item.strip())
        if not m:
            return None
        ordinal = int(m.group(1)) if m.group(1) else None
        if ordinal is not None and not (1 <= abs(ordinal) <= 5):
            return None
        out.append((ordinal, _WEEKDAYS[m.group(2)]))
    return out or None


def _month_days(year: int, month: int, byday, bymonthday, default_day: int) -> list[int]:
    ndays = calendar.monthrange(year, month)[1]
    sets: list[set[int]] = []
    if bymonthday is not None:
        days = set()
        for d in bymonthday:
            if d > 0 and d <= ndays:
                days.add(d)
            elif d < 0 and ndays + d + 1 >= 1:
                days.add(ndays + d + 1)
        sets.append(days)
    if byday is not None:
        first_wd = calendar.monthrange(year, month)[0]
        days = set()
        for ordinal, wd in byday:
            all_days = list(range(1 + (wd - first_wd) % 7, ndays + 1, 7))
            if ordinal is None:
                days.update(all_days)
            elif ordinal > 0 and ordinal <= len(all_days):
                days.add(all_days[ordinal - 1])
            elif ordinal < 0 and -ordinal <= len(all_days):
                days.add(all_days[ordinal])
        sets.append(days)
    if not sets:
        return [default_day] if default_day <= ndays else []
    result = sets[0]
    for s in sets[1:]:
        result = result & s
    return sorted(result)


def _occurrences(start: datetime, rule: dict[str, str] | None) -> Iterator[datetime]:
    """Yield wall-clock occurrences in increasing order (the first is ``start``)."""
    yield start
    if not rule:
        return
    if set(rule) - _SUPPORTED_RULE_KEYS:
        return
    freq = rule.get("FREQ", "").upper()
    try:
        interval = int(rule.get("INTERVAL", "1"))
    except ValueError:
        return
    if interval < 1 or freq not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
        return
    byday = None
    if "BYDAY" in rule:
        byday = _parse_byday(rule["BYDAY"])
        if byday is None:
            return
    bymonthday = None
    if "BYMONTHDAY" in rule:
        try:
            bymonthday = [int(x) for x in rule["BYMONTHDAY"].split(",")]
        except ValueError:
            return
        if any(d == 0 or abs(d) > 31 for d in bymonthday):
            return
    if freq != "MONTHLY" and bymonthday is not None:
        return
    if byday is not None:
        if freq == "WEEKLY" and any(o is not None for o, _ in byday):
            return
        if freq not in ("WEEKLY", "MONTHLY"):
            return

    t = start.time()
    try:
        if freq == "DAILY":
            for k in range(1, MAX_ITERATIONS):
                yield start + timedelta(days=k * interval)
        elif freq == "WEEKLY":
            wds = sorted({wd for _, wd in byday}) if byday else [start.weekday()]
            monday = start.date() - timedelta(days=start.weekday())
            for k in range(MAX_ITERATIONS):
                base = monday + timedelta(days=7 * interval * k)
                for wd in wds:
                    dt = datetime.combine(base + timedelta(days=wd), t)
                    if dt > start:
                        yield dt
        elif freq == "MONTHLY":
            for k in range(MAX_ITERATIONS):
                idx = start.year * 12 + start.month - 1 + k * interval
                year, month = divmod(idx, 12)
                month += 1
                if year > 9999:
                    return
                for d in _month_days(year, month, byday, bymonthday, start.day):
                    dt = datetime(year, month, d, start.hour, start.minute, start.second)
                    if dt > start:
                        yield dt
        else:  # YEARLY
            for k in range(1, MAX_ITERATIONS):
                year = start.year + k * interval
                if year > 9999:
                    return
                try:
                    yield start.replace(year=year)
                except ValueError:  # Feb 29 in a non-leap year
                    continue
    except (OverflowError, ValueError):
        return


class _Skip:
    """Set of local datetimes and whole dates to leave out."""

    def __init__(self) -> None:
        self.times: set[datetime] = set()
        self.days: set[date] = set()

    def add(self, value: str, params: dict[str, str], event_zone: tzinfo | None,
            tz: tzinfo | None) -> None:
        try:
            wall, zone, all_day, explicit = _parse_value(value, params)
        except ValueError:
            return
        if all_day:
            self.days.add(wall.date())
        else:
            self.times.add(_to_local(wall, zone if explicit else event_zone, tz))

    def __contains__(self, local: datetime) -> bool:
        return local in self.times or local.date() in self.days


def _collect_events(text: str) -> list[_Raw]:
    stack: list[str] = []
    current: list[tuple[str, dict[str, str], str]] | None = None
    raws: list[_Raw] = []
    for idx, line in enumerate(_unfold(text)):
        if not line.strip():
            continue
        parsed = _split_line(line)
        if parsed is None:
            continue
        name, params, value = parsed
        vname = value.strip().upper()
        if name == "BEGIN":
            if vname == "VEVENT" and stack and stack[-1] == "VEVENT":
                stack.pop()  # previous VEVENT was never closed
                current = None
            stack.append(vname)
            if vname == "VEVENT" and stack == ["VCALENDAR", "VEVENT"]:
                current = []
            continue
        if name == "END":
            if vname in stack:
                while stack:
                    popped = stack.pop()
                    if popped == "VEVENT" and current is not None:
                        raw = _build_raw(current, len(raws))
                        if raw is not None:
                            raws.append(raw)
                        current = None
                    if popped == vname:
                        break
            continue
        if current is not None and stack and stack[-1] == "VEVENT":
            current.append((name, params, value))
    return raws


def _build_raw(props: list[tuple[str, dict[str, str], str]], seq: int) -> _Raw | None:
    first: dict[str, tuple[dict[str, str], str]] = {}
    exdates: list[tuple[str, dict[str, str]]] = []
    for name, params, value in props:
        if name == "EXDATE":
            for part in value.split(","):
                if part.strip():
                    exdates.append((part, params))
        elif name not in first:
            first[name] = (params, value)
    if "DTSTART" not in first:
        return None
    params, value = first["DTSTART"]
    try:
        wall, zone, all_day, _ = _parse_value(value, params)
    except ValueError:
        return None
    title = _make_title(first["SUMMARY"][1]) if "SUMMARY" in first else EMPTY_TITLE
    uid = first["UID"][1].strip() if "UID" in first else ""
    if not uid:
        uid = f"noid:{title}:{value.strip()}"
    status = first.get("STATUS", ({}, ""))[1].strip().upper()
    rid = None
    if "RECURRENCE-ID" in first:
        rid = (first["RECURRENCE-ID"][1], first["RECURRENCE-ID"][0])
    rrule = first["RRULE"][1] if "RRULE" in first else None
    return _Raw(uid, title, wall, zone, all_day, status == "CANCELLED", rrule, exdates, rid)


def parse_ics(text: str, window_start: datetime, window_end: datetime,
              tz: tzinfo | None = None) -> list[CalendarEvent]:
    """Return event occurrences with ``window_start <= start < window_end``.

    ``tz`` is the local time zone (None means the system's). Never raises on
    malformed input; unreadable events are skipped.
    """
    try:
        raws = _collect_events(text or "")
    except Exception:
        return []

    overrides: dict[str, _Skip] = {}
    for raw in raws:
        if raw.recurrence_id is not None:
            value, params = raw.recurrence_id
            overrides.setdefault(raw.uid, _Skip()).add(value, params, raw.zone, tz)

    found: dict[tuple[str, datetime], CalendarEvent] = {}

    def emit(raw: _Raw, local: datetime) -> None:
        if window_start <= local < window_end:
            found.setdefault((raw.uid, local), CalendarEvent(raw.uid, raw.title, local, raw.all_day))

    horizon = window_end + timedelta(days=2)  # slack for zone offsets
    for raw in raws:
        if raw.cancelled:
            continue
        try:
            if raw.recurrence_id is not None:
                emit(raw, _to_local(raw.wall, raw.zone, tz))
                continue
            rule = _parse_rule(raw.rrule) if raw.rrule else None
            until = rule.get("UNTIL") if rule else None
            count = None
            if rule and "COUNT" in rule:
                try:
                    count = int(rule["COUNT"])
                except ValueError:
                    rule = None
                else:
                    if count < 1:
                        rule = None
            exskip = _Skip()
            for value, params in raw.exdates:
                exskip.add(value, params, raw.zone, tz)
            until_check = _make_until(until, tz, raw.zone) if until else None
            override = overrides.get(raw.uid)
            n = 0
            for wall in _occurrences(raw.wall, rule):
                n += 1
                if n > MAX_ITERATIONS or (count is not None and n > count):
                    break
                if wall > horizon:
                    break
                local = _to_local(wall, raw.zone, tz)
                if until_check is not None and not until_check(wall, local):
                    break
                if local in exskip or (override is not None and local in override):
                    continue
                emit(raw, local)
        except Exception:
            continue

    return sorted(found.values(), key=lambda e: (e.start, e.title, e.uid))


def _make_until(until: str, tz: tzinfo | None, zone: tzinfo | None):
    """Build a predicate (wall, local) -> bool telling whether an occurrence is allowed."""
    u = until.strip()
    try:
        if re.fullmatch(r"\d{8}", u):
            day = datetime.strptime(u, "%Y%m%d").date()
            return lambda wall, local: wall.date() <= day
        if u.endswith(("Z", "z")):
            limit = _to_local(_parse_datetime(u[:-1]), timezone.utc, tz)
            return lambda wall, local: local <= limit
        limit_wall = _parse_datetime(u)
        return lambda wall, local: wall <= limit_wall
    except ValueError:
        return lambda wall, local: True
