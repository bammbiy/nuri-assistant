"""When the character may speak up on her own while idle: pure logic with random spacing."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

CHATTER_MINUTES = {"많이": 15, "보통": 40, "조금": 90, "끄기": 0}
DEFAULT_LEVEL = "보통"
JITTER = (0.7, 1.3)


class IdleChatter:
    def __init__(self, level: str = DEFAULT_LEVEL, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.level = DEFAULT_LEVEL
        self._next = None
        self.set_level(level)

    def set_level(self, level: str) -> None:
        """Change the frequency; unknown names fall back to the default."""
        new = level if level in CHATTER_MINUTES else DEFAULT_LEVEL
        if new != self.level:
            self._next = None
        self.level = new

    def due(self, now: datetime) -> bool:
        """True when the next talk time has arrived."""
        minutes = CHATTER_MINUTES[self.level]
        if minutes <= 0:
            return False
        if self._next is None:
            self._schedule(now)
            return False
        return now >= self._next

    def spoke(self, now: datetime) -> None:
        """Schedule the next idle talk after speaking."""
        self._schedule(now)

    def reset(self, now: datetime) -> None:
        """Restart the wait (call after any other line the character says)."""
        self._schedule(now)

    def _schedule(self, now: datetime) -> None:
        minutes = CHATTER_MINUTES[self.level]
        if minutes <= 0:
            self._next = None
            return
        self._next = now + timedelta(minutes=minutes * self.rng.uniform(*JITTER))
