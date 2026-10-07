from __future__ import annotations

import tkinter as tk
from typing import Callable

from ..theme import ACCENT, ACCENT_DARK, FONT, SOFT, SOFT_HOVER, draw_pill


TAG = "chat"
HEIGHT = 40
ENTRY_FONT = (FONT, 10)

# The on-canvas pill is a shade stronger than theme's window cards so it reads over the character.
PILL = "#ffffff"
PILL_LINE = "#b9a3e3"
SHADOW = "#ddd2f0"
TEXT = "#3b2f4a"
HINT = "#a99bbd"
ACCENT_OFF = "#d9cff0"


def subject_particle(name: str) -> str:
    """'누리가' / '하은이' — pick 이/가 from the last syllable's final consonant."""

    last = name[-1:] if name else ""
    if "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28:
        return f"{name}이"
    return f"{name}가"


class ChatBox:
    """Pill-shaped chat input drawn on the mascot canvas, shown only on demand."""

    def __init__(
        self,
        canvas: tk.Canvas,
        left: int,
        top: int,
        width: int,
        on_send: Callable[[], None],
        on_menu: Callable[[int, int], None],
    ) -> None:
        self.canvas = canvas
        self.left, self.top, self.width = left, top, width
        self.on_send = on_send
        self.on_menu = on_menu
        self.visible = False
        self.enabled = True
        self._hint = ""
        self._hint_on = False
        self._slide = 0

        right, bottom = left + width, top + HEIGHT
        cy = top + HEIGHT // 2
        draw_pill(canvas, left, top + 3, right, bottom + 3, fill=SHADOW, tags=TAG)
        draw_pill(canvas, left, top, right, bottom, fill=PILL, outline=PILL_LINE, width=2, tags=TAG)

        # Menu button (three dots) on the left.
        mx = left + 22
        self.menu_button = canvas.create_oval(mx - 13, cy - 13, mx + 13, cy + 13, fill=SOFT, outline="", tags=(TAG, "chat_menu"))
        for dx in (-6, 0, 6):
            canvas.create_oval(mx + dx - 2, cy - 2, mx + dx + 2, cy + 2, fill=ACCENT, outline="", tags=(TAG, "chat_menu"))

        # Send button with a paper-plane arrow on the right.
        sx = right - 22
        self.send_button = canvas.create_oval(sx - 15, cy - 15, sx + 15, cy + 15, fill=ACCENT, outline="", tags=(TAG, "chat_send"))
        canvas.create_polygon(sx - 7, cy - 7, sx + 8, cy, sx - 7, cy + 7, sx - 4, cy,
                              fill="#ffffff", outline="", tags=(TAG, "chat_send"))

        self.entry = tk.Entry(
            canvas, relief="flat", bd=0, highlightthickness=0, font=ENTRY_FONT,
            bg=PILL, fg=TEXT, insertbackground=ACCENT, insertwidth=2,
            disabledbackground=PILL, disabledforeground=HINT,
        )
        entry_left = mx + 20
        canvas.create_window(entry_left, cy, anchor="w", window=self.entry,
                             width=(sx - 22) - entry_left, height=24, tags=TAG)

        self.entry.bind("<Return>", lambda _event: self.on_send())
        self.entry.bind("<Escape>", lambda _event: self.canvas.focus_set())
        # Borderless windows do not always take focus on click (notably on X11).
        self.entry.bind("<Button-1>", lambda _event: self.focus())
        self.entry.bind("<FocusIn>", lambda _event: self._clear_hint())
        self.entry.bind("<FocusOut>", lambda _event: self._show_hint())
        canvas.tag_bind("chat_send", "<Button-1>", lambda _event: self.on_send())
        canvas.tag_bind("chat_menu", "<Button-1>", self._open_menu)
        for tag, item, normal, hover in (
            ("chat_send", self.send_button, ACCENT, ACCENT_DARK),
            ("chat_menu", self.menu_button, SOFT, SOFT_HOVER),
        ):
            canvas.tag_bind(tag, "<Enter>", lambda _e, i=item, c=hover: self._hover(i, c))
            canvas.tag_bind(tag, "<Leave>", lambda _e, i=item, c=normal: self._hover(i, c))
        canvas.itemconfigure(TAG, state="hidden")

    def _hover(self, item: int, color: str) -> None:
        if item == self.send_button and not self.enabled:
            return
        self.canvas.itemconfigure(item, fill=color)

    def _open_menu(self, _event: tk.Event) -> None:
        x1, y1, _x2, _y2 = self.canvas.bbox(self.menu_button)
        self.on_menu(self.canvas.winfo_rootx() + x1, self.canvas.winfo_rooty() + y1)

    # ----- text and placeholder -------------------------------------------------

    def text(self) -> str:
        return "" if self._hint_on else self.entry.get()

    def clear(self) -> None:
        self.entry.delete(0, "end")
        if self.canvas.focus_get() is not self.entry:
            self._show_hint()

    def set_hint(self, hint: str) -> None:
        self._hint = hint
        if self._hint_on or not self.entry.get():
            self._show_hint()

    def _show_hint(self) -> None:
        if self.entry.get() and not self._hint_on:
            return
        state = self.entry.cget("state")
        self.entry.configure(state="normal")
        self.entry.delete(0, "end")
        self.entry.insert(0, self._hint)
        self.entry.configure(fg=HINT, state=state)
        self._hint_on = True

    def _clear_hint(self) -> None:
        # A FocusIn can arrive late, after the box was disabled for a reply; a disabled
        # Entry ignores delete(), so only clear while enabled or the flag goes out of sync.
        if self._hint_on and self.enabled:
            self.entry.delete(0, "end")
            self.entry.configure(fg=TEXT)
            self._hint_on = False

    def focused(self) -> bool:
        try:
            return self.canvas.focus_get() is self.entry
        except (KeyError, tk.TclError):  # focus on a Tk-internal window, e.g. a Combobox dropdown
            return False

    def focus(self) -> None:
        self.show()
        if self.enabled:
            # Clear the hint now: FocusIn arrives later and must not wipe fresh typing.
            self._clear_hint()
            self.entry.focus_force()

    def set_enabled(self, enabled: bool, hint: str) -> None:
        self.enabled = enabled
        self.canvas.itemconfigure(self.send_button, fill=ACCENT if enabled else ACCENT_OFF)
        if not enabled:
            self.canvas.focus_set()
        self.entry.configure(state="normal" if enabled else "disabled")
        self.set_hint(hint)

    # ----- show / hide ------------------------------------------------------------

    def contains(self, x: int, y: int, margin: int = 6) -> bool:
        return (
            self.visible
            and self.left - margin <= x <= self.left + self.width + margin
            and self.top - margin <= y <= self.top + HEIGHT + margin
        )

    def show(self) -> None:
        if self.visible:
            return
        self.visible = True
        self.canvas.itemconfigure(TAG, state="normal")
        self.canvas.tag_raise(TAG)
        # Slide up a few pixels as it appears.
        self.canvas.move(TAG, 0, 8 - self._slide)
        self._slide = 8
        self._step_slide()

    def _step_slide(self) -> None:
        if self._slide <= 0 or not self.visible:
            return
        step = min(2, self._slide)
        self.canvas.move(TAG, 0, -step)
        self._slide -= step
        self.canvas.after(16, self._step_slide)

    def hide(self) -> None:
        if not self.visible:
            return
        self.visible = False
        if self.focused():
            self.canvas.focus_set()
        self.canvas.itemconfigure(TAG, state="hidden")
