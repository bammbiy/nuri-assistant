from __future__ import annotations

import tkinter as tk
from typing import Callable

from ..theme import ACCENT_DARK, BG, DANGER, FONT, SOFT, SOFT_HOVER, SUBTLE, TEXT, button, entry


PRESETS = ((25, 5), (50, 10), (90, 15))
FOCUS_RANGE, BREAK_RANGE, CYCLE_RANGE = (1, 180), (0, 60), (1, 12)


class FocusDialog(tk.Toplevel):
    """Pick focus/break minutes and repeat count, then start (or stop a running timer)."""

    def __init__(
        self,
        master: tk.Misc,
        running: bool,
        on_start: Callable[[int, int, int], None],
        on_stop: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self.title("집중 타이머")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.on_start = on_start
        self.on_stop = on_stop

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=20)
        tk.Label(body, text="집중 타이머", font=(FONT, 16, "bold"), bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(body, text="집중하는 동안 캐릭터가 옆에서 지켜봐요." if not running else "타이머가 돌아가는 중이에요.",
                 font=(FONT, 9), bg=BG, fg=SUBTLE).pack(anchor="w", pady=(2, 12))

        chips = tk.Frame(body, bg=BG)
        chips.pack(fill="x", pady=(0, 10))
        for focus, rest in PRESETS:
            chip = tk.Label(chips, text=f"{focus}/{rest}", font=(FONT, 10, "bold"), bg=SOFT, fg=ACCENT_DARK,
                            padx=12, pady=5, cursor="hand2")
            chip.pack(side="left", padx=(0, 6))
            chip.bind("<Button-1>", lambda _event, f=focus, r=rest: self._preset(f, r))
            chip.bind("<Enter>", lambda _event, widget=chip: widget.configure(bg=SOFT_HOVER))
            chip.bind("<Leave>", lambda _event, widget=chip: widget.configure(bg=SOFT))

        self.focus_entry = self._row(body, "집중", "25", "분")
        self.break_entry = self._row(body, "쉬는 시간", "5", "분")
        self.cycles_entry = self._row(body, "반복", "1", "번")

        self.notice = tk.Label(body, text="", font=(FONT, 9), bg=BG, fg=DANGER, anchor="w")
        self.notice.pack(fill="x", pady=(8, 0))
        actions = tk.Frame(body, bg=BG)
        actions.pack(fill="x", pady=(8, 0))
        button(actions, "시작", self._start).pack(side="right")
        if running:
            button(actions, "지금 멈추기", self._stop, primary=False).pack(side="right", padx=6)
        else:
            button(actions, "취소", self.destroy, primary=False).pack(side="right", padx=6)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._start())

    def _row(self, parent: tk.Misc, label: str, value: str, unit: str) -> tk.Entry:
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, width=9, anchor="w", font=(FONT, 10, "bold"), bg=BG, fg=TEXT).pack(side="left")
        widget = entry(row, width=6)
        widget.insert(0, value)
        widget.pack(side="left", ipady=4)
        tk.Label(row, text=unit, font=(FONT, 10), bg=BG, fg=SUBTLE).pack(side="left", padx=(6, 0))
        return widget

    def _preset(self, focus: int, rest: int) -> None:
        for widget, value in ((self.focus_entry, focus), (self.break_entry, rest)):
            widget.delete(0, "end")
            widget.insert(0, str(value))

    def _number(self, widget: tk.Entry, name: str, low: int, high: int) -> int | None:
        try:
            value = int(widget.get().strip())
        except ValueError:
            value = low - 1
        if not low <= value <= high:
            self.notice.configure(text=f"{name}은(는) {low}~{high} 사이 숫자로 적어 주세요.")
            return None
        return value

    def _start(self) -> None:
        focus = self._number(self.focus_entry, "집중 시간", *FOCUS_RANGE)
        rest = self._number(self.break_entry, "쉬는 시간", *BREAK_RANGE) if focus is not None else None
        cycles = self._number(self.cycles_entry, "반복 횟수", *CYCLE_RANGE) if rest is not None else None
        if focus is None or rest is None or cycles is None:
            return
        self.on_start(focus, rest, cycles)
        self.destroy()

    def _stop(self) -> None:
        self.on_stop()
        self.destroy()
