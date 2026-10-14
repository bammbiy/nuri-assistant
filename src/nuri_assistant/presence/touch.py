"""Petting and click-combo detection: pure logic fed pointer positions and click times."""

from __future__ import annotations

JITTER_PX = 6


class PatDetector:
    """Detects rubbing back and forth over the character's head."""

    def __init__(self, reversals: int = 4, window_s: float = 1.2, cooldown_s: float = 8.0):
        self.reversals = reversals
        self.window_s = window_s
        self.cooldown_s = cooldown_s
        self._quiet_until = None
        self.reset()

    def reset(self) -> None:
        """Forget the current stroke (call when the pointer leaves the head)."""
        self._anchor = None
        self._direction = 0
        self._times: list[float] = []

    def feed(self, x: float, t: float) -> bool:
        """Add a pointer position; True once when enough reversals happen in the window."""
        if self._quiet_until is not None and t < self._quiet_until:
            return False
        if self._anchor is None:
            self._anchor = x
            return False
        delta = x - self._anchor
        if abs(delta) < JITTER_PX:
            return False
        direction = 1 if delta > 0 else -1
        self._anchor = x
        if self._direction and direction != self._direction:
            self._times.append(t)
        self._direction = direction
        self._times = [s for s in self._times if t - s <= self.window_s]
        if len(self._times) >= self.reversals:
            self._quiet_until = t + self.cooldown_s
            self.reset()
            return True
        return False


class ClickCombo:
    """Detects several quick clicks in a row."""

    def __init__(self, count: int = 4, window_s: float = 3.0):
        self.count = count
        self.window_s = window_s
        self._times: list[float] = []

    def click(self, t: float) -> bool:
        """True when this click makes `count` clicks within the window."""
        self._times = [s for s in self._times if t - s <= self.window_s]
        self._times.append(t)
        if len(self._times) >= self.count:
            self._times = []
            return True
        return False
