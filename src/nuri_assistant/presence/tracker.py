"""When to say welcome back, take a break or drink water: pure logic fed one idle-time poll at a time."""

from __future__ import annotations

from datetime import datetime, timedelta

ACTIVE_SECONDS = 60


class PresenceTracker:
    def __init__(self, away_minutes: int = 30, break_minutes: int = 60,
                 water_minutes: int = 90, rest_minutes: int = 5):
        self.away_minutes = away_minutes
        self.break_minutes = break_minutes
        self.water_minutes = water_minutes
        self.rest_minutes = rest_minutes
        self._away_start = None
        self._back_at = None
        self._streak_start = None
        self._last_break = None
        self._last_water = None

    def configure(self, away_minutes=None, break_minutes=None, water_minutes=None):
        if away_minutes is not None:
            self.away_minutes = away_minutes
        if break_minutes is not None:
            self.break_minutes = break_minutes
        if water_minutes is not None:
            self.water_minutes = water_minutes

    def update(self, now: datetime, idle_seconds: float,
               quiet: bool = False) -> list[tuple[str, int]]:
        events: list[tuple[str, int]] = []
        if self.away_minutes > 0 and idle_seconds >= self.away_minutes * 60:
            if self._away_start is None:
                self._away_start = now - _seconds(idle_seconds)
        if self.rest_minutes > 0 and idle_seconds >= self.rest_minutes * 60:
            self._streak_start = None
            self._last_break = None
        if idle_seconds >= ACTIVE_SECONDS:
            self._back_at = None
            return events

        started = now - _seconds(idle_seconds)
        if self._away_start is not None:
            if self._back_at is None:
                self._back_at = started
            if quiet:
                self._streak_start = now
                self._last_break = None
                return events
            away = int((self._back_at - self._away_start).total_seconds() // 60)
            self._away_start = None
            self._back_at = None
            self._streak_start = started
            self._last_break = started
            self._last_water = now
            events.append(("welcome_back", away))
            return events

        if self._streak_start is None:
            self._streak_start = started
        if self._last_water is None:
            self._last_water = started
        if quiet:
            self._streak_start = now
            self._last_break = None
            return events
        if self._last_break is None:
            self._last_break = self._streak_start
        if (self.break_minutes > 0
                and now - self._last_break >= _minutes(self.break_minutes)):
            events.append(("break", int((now - self._streak_start).total_seconds() // 60)))
            self._last_break = now
        if (self.water_minutes > 0
                and now - self._last_water >= _minutes(self.water_minutes)):
            events.append(("water", self.water_minutes))
            self._last_water = now
        return events


def _seconds(value: float):
    return timedelta(seconds=value)


def _minutes(value: int):
    return timedelta(minutes=value)
