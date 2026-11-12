"""Focus timer: start, tick, badge drawing and stop.

Mixed into ``MascotApp``; relies on its ``focus_timer``, canvas, ``talk`` and ``gain``.
"""

from __future__ import annotations

from datetime import datetime

from ...announcements import timer_line
from .timer_badge import draw_timer_badge
from .timing import MIN_FOCUS_FOR_POINTS, TIMER_TICK_MS


class TimerMixin:
    """Focus timer driven by Tk ``after``."""

    # ----- focus timer --------------------------------------------------------------

    def start_focus(self, focus_minutes: int = 25, break_minutes: int = 5, cycles: int = 1) -> None:
        self.focus_timer.start(datetime.now(), focus_minutes, break_minutes, cycles)
        times = f" × {cycles}번" if cycles > 1 else ""
        self.talk(f"{focus_minutes}분 집중{times} 시작! 끝나면 알려 줄게요.", "happy")
        self._draw_timer()

    def _tick_timer(self) -> None:
        try:
            self._timer_step()
        finally:
            self.after(TIMER_TICK_MS, self._tick_timer)

    def _timer_step(self) -> None:
        now = datetime.now()
        events = self.focus_timer.tick(now)
        for minutes in self.focus_timer.take_finished():
            self.focus_log.add(now, minutes)
            if minutes >= MIN_FOCUS_FOR_POINTS:
                self.gain("focus_done")
        for event in events:
            self.talk(*timer_line(self.persona, self.focus_timer, event))
            self.bell()
        self._draw_timer()

    def _draw_timer(self) -> None:
        draw_timer_badge(self.canvas, self.focus_timer.state(datetime.now()), self.head_top, self._stop_timer)

    def _stop_timer(self) -> None:
        if self.focus_timer.stop():
            self._draw_timer()
            self.talk("타이머를 멈췄어요.", "neutral")
