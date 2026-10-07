from __future__ import annotations

import tkinter as tk
from datetime import datetime

from ...schedule import WhenError, parse_when
from ...todo import Todo, TodoStore
from ..theme import (
    ACCENT, BG, CARD, CARD_LINE, DANGER, FONT, SHADOW, SOFT, SUBTLE, TEXT, TODAY, button, draw_pill, entry, fit,
    round_rect,
)
from .cards import CardListMixin


WIDTH = 440
PAD = 20
CARD_H = 56


class TodoWindow(CardListMixin, tk.Toplevel):
    """Open to-dos with due chips (D-3 / 오늘 / 지남), tap the circle to finish one."""

    def __init__(self, master: tk.Misc, store: TodoStore) -> None:
        super().__init__(master)
        self.title("할 일")
        self.configure(bg=BG)
        self.geometry(f"{WIDTH}x600")
        self.minsize(WIDTH, 380)
        self.attributes("-topmost", True)
        self.store = store
        self._armed: int | None = None

        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=PAD, pady=(18, 8))
        tk.Label(header, text="할 일", font=(FONT, 17, "bold"), bg=BG, fg=TEXT).pack(side="left")
        self.summary = tk.Label(header, font=(FONT, 10), bg=BG, fg=SUBTLE)
        self.summary.pack(side="left", padx=(10, 0), pady=(6, 0))

        form = tk.Frame(self, bg=BG)
        form.pack(fill="x", padx=PAD, pady=(0, 4))
        self.title_entry = entry(form, width=18)
        self.due_entry = entry(form, width=15)
        self._placeholder(self.title_entry, "할 일")
        self._placeholder(self.due_entry, "기한 (예: 금요일)")
        self.title_entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.due_entry.pack(side="left", padx=6, ipady=6)
        button(form, "추가", self._add).pack(side="left")
        self.notice = tk.Label(self, text="", font=(FONT, 9), bg=BG, fg=DANGER, anchor="w")
        self.notice.pack(fill="x", padx=PAD)

        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True, pady=(4, 0))
        self.canvas.bind("<Configure>", lambda _event: self.refresh())
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind(sequence, self._scroll)
        self.canvas.bind("<Button-1>", self._disarm, add="+")
        self.bind("<FocusIn>", lambda event: self.refresh() if event.widget is self else None)
        self.bind("<Escape>", lambda _event: self.destroy())

    # ----- form -----------------------------------------------------------------------

    def _placeholder(self, widget: tk.Entry, hint: str) -> None:
        def show(_event=None) -> None:
            if not widget.get():
                widget.insert(0, hint)
                widget.configure(fg=SUBTLE)
                widget.is_hint = True

        def clear(_event=None) -> None:
            if getattr(widget, "is_hint", False):
                widget.delete(0, "end")
                widget.configure(fg=TEXT)
                widget.is_hint = False

        widget.bind("<FocusIn>", clear)
        widget.bind("<FocusOut>", show)
        widget.bind("<Return>", lambda _event: self._add())
        show()

    def _value(self, widget: tk.Entry) -> str:
        return "" if getattr(widget, "is_hint", False) else widget.get().strip()

    def _add(self) -> None:
        title, due_text = self._value(self.title_entry), self._value(self.due_entry)
        if not title:
            return
        due, all_day = None, True
        if due_text:
            try:
                when = parse_when(due_text.replace("까지", " "), datetime.now())
            except WhenError as exc:
                self.notice.configure(text=str(exc))
                return
            due, all_day = when.start, when.all_day
        self.store.add(title, due, all_day)
        self.notice.configure(text="")
        for widget in (self.title_entry, self.due_entry):
            widget.delete(0, "end")
            widget.event_generate("<FocusOut>")
        self.canvas.focus_set()
        self.refresh()

    # ----- drawing ----------------------------------------------------------------------

    def refresh(self) -> None:
        if not self.winfo_exists():
            return
        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), WIDTH)
        todos, done = self.store.open(), self.store.recently_done(5)
        today = datetime.now().date()
        overdue = sum(1 for todo in todos if todo.due and todo.due.date() < today)
        self.summary.configure(text=f"{len(todos)}개 남음" + (f" · 기한 지남 {overdue}개" if overdue else ""))
        if not todos and not done:
            cx, cy = width // 2, max(canvas.winfo_height() // 2 - 40, 110)
            canvas.create_oval(cx - 34, cy - 70, cx + 34, cy - 2, fill=SOFT, outline="")
            canvas.create_line(cx - 14, cy - 36, cx - 4, cy - 26, cx + 16, cy - 48, fill=ACCENT, width=5, capstyle="round", joinstyle="round")
            canvas.create_text(cx, cy + 22, text="할 일이 없어요", font=(FONT, 12, "bold"), fill=TEXT)
            canvas.create_text(cx, cy + 42, text="위에 적거나 비서에게\n\"보고서 금요일까지 해야 해\"라고 말해 보세요.",
                               anchor="n", font=(FONT, 10), fill=SUBTLE, justify="center")
            canvas.configure(scrollregion=(0, 0, width, canvas.winfo_height()))
            return
        y = 6
        for todo in todos:
            y = self._card(todo, y, width, today)
        if done:
            canvas.create_text(PAD, y + 14, text="최근 완료", anchor="w", font=(FONT, 10, "bold"), fill=SUBTLE)
            y += 30
            for todo in done:
                y = self._card(todo, y, width, today)
        canvas.configure(scrollregion=(0, 0, width, y + PAD))

    def _card(self, todo: Todo, y: int, width: int, today) -> int:
        canvas = self.canvas
        x1, x2, y2 = PAD, width - PAD, y + CARD_H
        round_rect(canvas, x1, y + 2, x2, y2 + 2, 12, fill=SHADOW, outline="")
        round_rect(canvas, x1, y, x2, y2, 12, fill=CARD, outline=CARD_LINE, width=1)

        # Check circle
        cx, cy = x1 + 24, y + CARD_H // 2
        tag = f"check_{todo.id}"
        if todo.done:
            canvas.create_oval(cx - 10, cy - 10, cx + 10, cy + 10, fill=TODAY, outline=TODAY, tags=(tag,))
            canvas.create_line(cx - 5, cy, cx - 1, cy + 4, cx + 6, cy - 4, fill="#ffffff", width=2, tags=(tag,))
        else:
            canvas.create_oval(cx - 10, cy - 10, cx + 10, cy + 10, fill=CARD, outline=ACCENT, width=2, tags=(tag, f"{tag}_bg"))
            canvas.tag_bind(tag, "<Enter>", lambda _e: canvas.itemconfigure(f"{tag}_bg", fill=SOFT))
            canvas.tag_bind(tag, "<Leave>", lambda _e: canvas.itemconfigure(f"{tag}_bg", fill=CARD))
        canvas.tag_bind(tag, "<Button-1>", lambda _e: self._toggle(todo))

        title_font = (FONT, 11, "bold") if not todo.done else (FONT, 11, "overstrike")
        canvas.create_text(x1 + 46, y + 19, text=fit(todo.title, title_font, x2 - x1 - 150), anchor="w",
                           font=title_font, fill=SUBTLE if todo.done else TEXT)
        canvas.create_text(x1 + 46, y + 39, text=todo.due_text, anchor="w", font=(FONT, 9), fill=SUBTLE)

        if todo.due and not todo.done:
            label = todo.d_day(today)
            days = (todo.due.date() - today).days
            color = DANGER if days <= 0 else ACCENT if days <= 2 else SUBTLE
            chip = canvas.create_text(0, 0, text=label, font=(FONT, 9, "bold"))
            chip_w = canvas.bbox(chip)[2] - canvas.bbox(chip)[0] + 18
            canvas.delete(chip)
            draw_pill(canvas, x2 - 48 - chip_w, cy - 11, x2 - 48, cy + 11, fill=color, tags=("chip",))
            canvas.create_text(x2 - 48 - chip_w / 2, cy, text=label, font=(FONT, 9, "bold"), fill="#ffffff")
        self._delete_button(todo.id, x2 - 22, cy)
        return y2 + 8

    # ----- interaction --------------------------------------------------------------

    def _toggle(self, todo: Todo) -> None:
        self.store.set_done(todo.id, not todo.done)
        self.after_idle(self.refresh)
