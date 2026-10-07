from __future__ import annotations

import tkinter as tk
from typing import Callable

from ...focus.timer import TimerState
from ..theme import ACCENT, FONT, TODAY, draw_pill

TAG = "timer"


def draw_timer_badge(canvas: tk.Canvas, state: TimerState, head_top: int, on_stop: Callable[[], None]) -> None:
    """Small pill badge at the character's top-left: 집중 24:12 ■ (click to stop)."""

    canvas.delete(TAG)
    if state.phase is None:
        return
    label = f"{'집중' if state.phase == 'focus' else '휴식'} {state.clock}"
    if state.cycles > 1:
        label += f"  {min(state.cycle, state.cycles)}/{state.cycles}"
    color = ACCENT if state.phase == "focus" else TODAY
    x, y = 14, max(head_top - 6, 6)
    text = canvas.create_text(x + 14, y + 13, text=label, anchor="w", font=(FONT, 10, "bold"), fill="#ffffff", tags=TAG)
    right = canvas.bbox(text)[2] + 30
    draw_pill(canvas, x, y, right, y + 26, fill=color, tags=TAG)
    canvas.create_rectangle(right - 19, y + 9, right - 11, y + 17, fill="#ffffff", outline="", tags=TAG)
    canvas.tag_raise(text)
    canvas.tag_bind(TAG, "<Button-1>", lambda _event: on_stop())
    # Keep the documented z-order: character -> timer -> bubble -> confirm -> chat.
    for overlay in ("bubble", "confirm", "chat"):
        canvas.tag_raise(overlay)
