from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class TimerState:
    phase: str | None  # "focus" | "break" | None
    remaining: timedelta
    cycle: int
    cycles: int

    @property
    def clock(self) -> str:
        seconds = max(int(self.remaining.total_seconds()), 0)
        return f"{seconds // 60:02d}:{seconds % 60:02d}"


class FocusTimer:
    """Pomodoro-style focus/break cycles. Pure time logic; the UI calls tick() every second.

    Thread-safe because the model's tool calls arrive on a worker thread.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.phase: str | None = None
        self.ends_at: datetime | None = None
        self.focus_minutes = 25
        self.break_minutes = 5
        self.cycle = 0
        self.cycles = 1

    def start(self, now: datetime, focus_minutes: int = 25, break_minutes: int = 5, cycles: int = 1) -> TimerState:
        with self._lock:
            self.focus_minutes = min(max(int(focus_minutes), 1), 180)
            self.break_minutes = min(max(int(break_minutes), 0), 60)
            self.cycles = min(max(int(cycles), 1), 12)
            self.cycle = 1
            self.phase = "focus"
            self.ends_at = now + timedelta(minutes=self.focus_minutes)
        return self.state(now)

    def stop(self) -> bool:
        with self._lock:
            running = self.phase is not None
            self.phase, self.ends_at = None, None
        return running

    def state(self, now: datetime) -> TimerState:
        with self._lock:
            remaining = self.ends_at - now if self.ends_at else timedelta(0)
            return TimerState(self.phase, remaining, self.cycle, self.cycles)

    def tick(self, now: datetime) -> list[str]:
        """Advance phases that have ended. Returns events: focus_done, break_done, all_done."""

        events: list[str] = []
        with self._lock:
            while self.phase and self.ends_at and now >= self.ends_at:
                last = self.cycle >= self.cycles
                if self.phase == "focus" and self.break_minutes:
                    # Every focus block, the last one too, is followed by its break.
                    events.append("focus_done")
                    self.phase, self.ends_at = "break", self.ends_at + timedelta(minutes=self.break_minutes)
                elif last:
                    events.append("all_done")
                    self.phase, self.ends_at = None, None
                else:
                    events.append("break_done" if self.phase == "break" else "focus_done")
                    self.cycle += 1
                    self.phase, self.ends_at = "focus", self.ends_at + timedelta(minutes=self.focus_minutes)
        return events
