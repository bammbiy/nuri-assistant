from __future__ import annotations

import tkinter as tk
from typing import Callable

from ..schedule import PendingAction
from .chatbox import ACCENT, ACCENT_HOVER, ENTRY_FONT, PILL_LINE, SOFT, SOFT_HOVER, TEXT, draw_pill


TAG = "confirm"
HEIGHT = 92
CARD_SHADOW = "#ddd2f0"
DANGER = "#e06c8a"
DANGER_HOVER = "#c9506f"


class ConfirmCard:
    """On-canvas card asking the user to approve a schedule change the model proposed."""

    def __init__(self, canvas: tk.Canvas, left: int, top: int, width: int) -> None:
        self.canvas = canvas
        self.left, self.top, self.width = left, top, width
        self.action: PendingAction | None = None

    @property
    def visible(self) -> bool:
        return self.action is not None

    def show(self, action: PendingAction, on_yes: Callable[[], None], on_no: Callable[[], None]) -> None:
        self.hide()
        self.action = action
        canvas, x1, y1 = self.canvas, self.left, self.top
        x2, y2 = x1 + self.width, y1 + HEIGHT
        self._round_rect(x1, y1 + 3, x2, y2 + 3, 14, fill=CARD_SHADOW, outline="")
        self._round_rect(x1, y1, x2, y2, 14, fill="#ffffff", outline=PILL_LINE, width=2)
        adding = action.kind == "add"
        canvas.create_text(x1 + 16, y1 + 16, anchor="w", text=action.heading, fill=ACCENT if adding else DANGER,
                           font=(ENTRY_FONT[0], 9, "bold"), tags=TAG)
        canvas.create_text(x1 + 16, y1 + 38, anchor="w", text=f"{action.when}  ·  {action.title}", fill=TEXT,
                           width=self.width - 32, font=(ENTRY_FONT[0], 11, "bold"), tags=TAG)

        yes_color, yes_hover = (ACCENT, ACCENT_HOVER) if adding else (DANGER, DANGER_HOVER)
        self._button(x2 - 76, y2 - 32, 64, "등록" if adding else "삭제", yes_color, yes_hover, "#ffffff", "confirm_yes", on_yes)
        self._button(x2 - 146, y2 - 32, 64, "취소", SOFT, SOFT_HOVER, TEXT, "confirm_no", on_no)
        canvas.tag_raise(TAG)

    def hide(self) -> None:
        self.action = None
        self.canvas.delete(TAG)

    def _button(self, x: int, y: int, width: int, label: str, fill: str, hover: str, fg: str,
                tag: str, command: Callable[[], None]) -> None:
        canvas = self.canvas
        draw_pill(canvas, x, y, x + width, y + 24, fill=fill, tags=(TAG, tag, f"{tag}_bg"))
        canvas.create_text(x + width // 2, y + 12, text=label, fill=fg, font=(ENTRY_FONT[0], 9, "bold"), tags=(TAG, tag))
        canvas.tag_bind(tag, "<Button-1>", lambda _event: command())
        canvas.tag_bind(tag, "<Enter>", lambda _event: canvas.itemconfigure(f"{tag}_bg", fill=hover))
        canvas.tag_bind(tag, "<Leave>", lambda _event: canvas.itemconfigure(f"{tag}_bg", fill=fill))

    def _round_rect(self, x1: int, y1: int, x2: int, y2: int, r: int, **options: object) -> None:
        points = (
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
            x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        )
        self.canvas.create_polygon(*points, smooth=True, tags=TAG, **options)
