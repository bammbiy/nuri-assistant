from __future__ import annotations

import tkinter as tk
from typing import Protocol

from ..theme import DANGER, FONT, SOFT, SUBTLE, draw_pill


class _DeletableStore(Protocol):
    def delete(self, item_id: int) -> object: ...


class CardListMixin:
    """Two-press delete and wheel scrolling shared by the card-list windows (schedule, todo, price).

    The window provides `canvas`, `store` (with delete(id)), `refresh()` and sets `_armed = None`.
    """

    canvas: tk.Canvas
    store: _DeletableStore
    _armed: int | None
    # Per-window looks, kept so each window renders exactly as it did before the merge.
    DELETE_PILL_HALF = 11
    DELETE_HOVER: str | None = None

    def refresh(self) -> None:
        raise NotImplementedError

    def _delete_button(self, item_id: int, cx: int, cy: int) -> None:
        canvas = self.canvas
        tag = f"delete_{item_id}"
        if self._armed == item_id:
            half = self.DELETE_PILL_HALF
            draw_pill(canvas, cx - 30, cy - half, cx + 12, cy + half, fill=DANGER, tags=(tag,))
            canvas.create_text(cx - 9, cy, text="삭제", font=(FONT, 9, "bold"), fill="#ffffff", tags=(tag,))
        else:
            canvas.create_oval(cx - 11, cy - 11, cx + 11, cy + 11, fill=SOFT, outline="", tags=(tag, f"{tag}_bg"))
            canvas.create_line(cx - 4, cy - 4, cx + 4, cy + 4, fill=SUBTLE, width=2, tags=(tag,))
            canvas.create_line(cx - 4, cy + 4, cx + 4, cy - 4, fill=SUBTLE, width=2, tags=(tag,))
            if self.DELETE_HOVER:
                hover = self.DELETE_HOVER
                canvas.tag_bind(tag, "<Enter>", lambda _e: canvas.itemconfigure(f"{tag}_bg", fill=hover))
                canvas.tag_bind(tag, "<Leave>", lambda _e: canvas.itemconfigure(f"{tag}_bg", fill=SOFT))
        canvas.tag_bind(tag, "<Button-1>", lambda _e: self._delete_clicked(item_id))

    def _delete_clicked(self, item_id: int) -> str:
        # First click arms the button ("삭제"), second click deletes.
        if self._armed == item_id:
            self.store.delete(item_id)
            self._armed = None
        else:
            self._armed = item_id
        self.after_idle(self.refresh)  # type: ignore[attr-defined]
        return "break"

    def _disarm(self, _event: tk.Event) -> None:
        # Any click outside a delete button cancels a half-done delete.
        current = self.canvas.find_withtag("current")
        tags = self.canvas.gettags(current[0]) if current else ()
        if self._armed is not None and not any(tag.startswith("delete_") for tag in tags):
            self._armed = None
            self.refresh()

    def _scroll(self, event: tk.Event) -> None:
        # X11 sends Button-4/5; Windows and macOS send MouseWheel with a signed delta.
        up = event.num == 4 or getattr(event, "delta", 0) > 0
        self.canvas.yview_scroll(-2 if up else 2, "units")
