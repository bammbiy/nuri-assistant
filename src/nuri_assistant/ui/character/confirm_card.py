from __future__ import annotations

import tkinter as tk
from typing import Callable

from ...companion import ConfirmableAction
from ..theme import ACCENT, ACCENT_DARK, DANGER, FONT, SOFT, SOFT_HOVER, draw_pill, round_rect
from .chatbox import PILL_LINE, TEXT


TAG = "confirm"
HEIGHT = 92
CARD_SHADOW = "#ddd2f0"
DANGER_HOVER = "#c9506f"
YES_LABELS = {"add": "등록", "done": "완료", "rename": "정리", "undo": "되돌리기"}


class ConfirmCard:
    """On-canvas card asking the user to approve a change the model proposed (schedule, todo, price watch, file names)."""

    def __init__(self, canvas: tk.Canvas, left: int, top: int, width: int) -> None:
        self.canvas = canvas
        self.left, self.top, self.width = left, top, width
        self.action: ConfirmableAction | None = None

    @property
    def visible(self) -> bool:
        return self.action is not None

    def show(self, action: ConfirmableAction, on_yes: Callable[[], None], on_no: Callable[[], None]) -> None:
        self.hide()
        self.action = action
        canvas, x1, y1 = self.canvas, self.left, self.top
        x2, y2 = x1 + self.width, y1 + HEIGHT
        round_rect(canvas, x1, y1 + 3, x2, y2 + 3, 14, fill=CARD_SHADOW, outline="", tags=TAG)
        round_rect(canvas, x1, y1, x2, y2, 14, fill="#ffffff", outline=PILL_LINE, width=2, tags=TAG)
        # add/done/rename/undo are positive actions (accent); cancel/delete are destructive (red).
        adding = action.kind in ("add", "done", "rename", "undo")
        canvas.create_text(x1 + 16, y1 + 16, anchor="w", text=action.heading, fill=ACCENT if adding else DANGER,
                           font=(FONT, 9, "bold"), tags=TAG)
        canvas.create_text(x1 + 16, y1 + 38, anchor="w", text=f"{action.when}  ·  {action.title}", fill=TEXT,
                           width=self.width - 32, font=(FONT, 11, "bold"), tags=TAG)

        yes_color, yes_hover = (ACCENT, ACCENT_DARK) if adding else (DANGER, DANGER_HOVER)
        self._button(x2 - 76, y2 - 32, 64, YES_LABELS.get(action.kind, "삭제"), yes_color, yes_hover, "#ffffff", "confirm_yes", on_yes)
        self._button(x2 - 146, y2 - 32, 64, "취소", SOFT, SOFT_HOVER, TEXT, "confirm_no", on_no)
        canvas.tag_raise(TAG)

    def hide(self) -> None:
        self.action = None
        self.canvas.delete(TAG)

    def _button(self, x: int, y: int, width: int, label: str, fill: str, hover: str, fg: str,
                tag: str, command: Callable[[], None]) -> None:
        canvas = self.canvas
        draw_pill(canvas, x, y, x + width, y + 24, fill=fill, tags=(TAG, tag, f"{tag}_bg"))
        canvas.create_text(x + width // 2, y + 12, text=label, fill=fg, font=(FONT, 9, "bold"), tags=(TAG, tag))
        canvas.tag_bind(tag, "<Button-1>", lambda _event: command())
        canvas.tag_bind(tag, "<Enter>", lambda _event: canvas.itemconfigure(f"{tag}_bg", fill=hover))
        canvas.tag_bind(tag, "<Leave>", lambda _event: canvas.itemconfigure(f"{tag}_bg", fill=fill))
