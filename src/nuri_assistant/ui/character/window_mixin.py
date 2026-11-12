"""Window placement, staying on top, dragging, pointer hover and the display mode.

Mixed into ``MascotApp``; relies on its canvas, chat box, settings, ``_update_settings``
and the character drawing methods.
"""

from __future__ import annotations

import random
import time
import tkinter as tk

from ...presence import foreground_fullscreen
from ...screen import Rect, all_monitors, default_position, is_reachable, work_area
from .timing import (
    CANVAS_HEIGHT, CHAT_HIDE_DELAY_MS, DRAG_THRESHOLD_PX, FULL_EXTRA, HEAD_SHARE, KEEP_ON_TOP_MS, POINTER_POLL_MS,
    WIDTH,
)


class WindowMixin:
    """Where the character window sits and how it reacts to the pointer."""

    def _place_window(self) -> None:
        """Saved spot if it is still on a monitor, else bottom-right above the taskbar."""

        self.update_idletasks()
        height = self.winfo_reqheight()
        x, y = self.settings.x, self.settings.y
        if x is None or y is None or not is_reachable(int(x), int(y), WIDTH, height, self._monitors()):
            x, y = default_position(self._work_area(), WIDTH, height)
        self.geometry(f"+{int(x)}+{int(y)}")

    def _work_area(self) -> Rect:
        return work_area(self.winfo_screenwidth(), self.winfo_screenheight())

    def _monitors(self) -> Rect:
        return all_monitors(self.winfo_screenwidth(), self.winfo_screenheight())

    def _keep_on_screen(self) -> None:
        try:
            self._stay_visible()
        finally:
            self.after(KEEP_ON_TOP_MS, self._keep_on_screen)

    def _stay_visible(self) -> None:
        """Windows drops "topmost" after full-screen apps or other topmost windows, and a
        monitor change can strand the window off-screen: re-assert both every few seconds."""

        if self.state() == "withdrawn" or self._drag_start is not None:
            return
        if not is_reachable(self.winfo_x(), self.winfo_y(), WIDTH, self.winfo_height(), self._monitors()):
            x, y = default_position(self._work_area(), WIDTH, self.winfo_height())
            self.geometry(f"+{x}+{y}")
            self._update_settings(x=x, y=y)
        was_fullscreen, self._fullscreen = self._fullscreen, self._check_fullscreen()
        if self._fullscreen:
            if not was_fullscreen:
                self.attributes("-topmost", False)  # let the game or video cover us; back when it ends
            return
        # Not while our own windows are open: re-raising would cover them.
        if not any(isinstance(w, tk.Toplevel) and w.winfo_viewable() for w in self.winfo_children()):
            self.attributes("-topmost", True)

    def _check_fullscreen(self) -> bool:
        if not self.settings.fullscreen_quiet:
            return False
        own = {self.winfo_id()}
        try:
            own.add(int(self.wm_frame(), 16))
        except (tk.TclError, ValueError):
            pass
        return bool(foreground_fullscreen(own))

    def _optional_ok(self) -> bool:
        """Optional lines (idle talk, greetings, level-ups, suggestions) wait while the user is busy
        with something else; schedule, to-do, timer and price alerts are never held back."""

        return not (self._fullscreen or self.busy or self.card.visible or self.state() == "withdrawn")

    def _on_press(self, event: tk.Event) -> None:
        self._drag_start = (event.x_root, event.y_root, self.winfo_x(), self.winfo_y())
        self._dragged = False

    def _on_drag(self, event: tk.Event) -> None:
        if self._drag_start is None:
            return
        start_x, start_y, win_x, win_y = self._drag_start
        dx, dy = event.x_root - start_x, event.y_root - start_y
        if abs(dx) + abs(dy) > DRAG_THRESHOLD_PX:
            self._dragged = True
        if self._dragged:
            self.geometry(f"+{win_x + dx}+{win_y + dy}")

    def _on_release(self, _event: tk.Event) -> None:
        self._drag_start = None
        if self._dragged:
            self._update_settings(x=self.winfo_x(), y=self.winfo_y())
        elif not self.busy:
            if self.combo.click(time.monotonic()):
                self.talk(random.choice(self.persona.pokes_many), "angry")
            else:
                self.talk(random.choice(self.persona.pokes), random.choice(("surprised", "shy", "happy")))
            self.chat.focus()

    def _on_motion(self, event: tk.Event) -> None:
        """Rubbing the pointer back and forth over the head (no button) is a pat."""

        box = self.canvas.bbox("character")
        on_head = (box is not None and event.state & 0x0100 == 0
                   and box[0] <= event.x <= box[2] and box[1] <= event.y <= box[1] + (box[3] - box[1]) * HEAD_SHARE)
        if not on_head:
            self.pat.reset()
        elif self.pat.feed(event.x, time.monotonic()) and not self.busy:
            self.talk(random.choice(self.persona.pats), "shy")

    def _show_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def _idle_hint(self) -> str:
        return f"{self.persona.name}에게 말 걸기…"

    def _watch_pointer(self) -> None:
        """Show the chat box while the mouse is on the character (or the box itself)."""

        try:
            self._update_hover()
        finally:
            self.after(POINTER_POLL_MS, self._watch_pointer)

    def _update_hover(self) -> None:
        px, py = self.winfo_pointerxy()
        x, y = px - self.canvas.winfo_rootx(), py - self.canvas.winfo_rooty()
        box = self.canvas.bbox("character")
        over_character = box is not None and box[0] - 8 <= x <= box[2] + 8 and box[1] <= y <= box[3] + 12
        keep = (
            over_character
            or self.chat.contains(x, y)
            or self.busy
            or (self.chat.focused() and bool(self.chat.text()))
            or self._drag_start is not None
        )
        now = time.monotonic()
        if keep:
            self._last_hover = now
            self.chat.show()
        elif self.chat.visible and (now - self._last_hover) * 1000 > CHAT_HIDE_DELAY_MS:
            self.chat.hide()

    def set_display_mode(self, mode: str) -> None:
        """Switch bust/full body; the window grows upward so the character's feet stay put."""

        full = mode == "full"
        if full == self.full_mode:
            return
        dy = (FULL_EXTRA if full else 0) - self.extra
        self.full_mode, self.extra = full, FULL_EXTRA if full else 0
        self.full_var.set(full)
        self.canvas.configure(height=CANVAS_HEIGHT + self.extra)
        self.canvas.move("chat", 0, dy)
        self.chat.top += dy
        self.card.top += dy
        if self.card.visible:
            self._show_next_card()
        self.update_idletasks()
        y = max(self.winfo_y() - dy, self._monitors().top)
        self.geometry(f"+{self.winfo_x()}+{y}")
        self._update_settings(display_mode=mode, y=y)
        self._render_character()
        self._show_bubble(self.bubble.text)
