from __future__ import annotations

import tkinter as tk
from datetime import date, datetime, time, timedelta

from ...schedule import Event, ScheduleStore, format_day
from ..theme import ACCENT, BG, CARD, CARD_LINE, FONT, SHADOW, SOFT, SUBTLE, TEXT, TODAY, fit, round_rect
from .cards import CardListMixin


WIDTH = 420
PAD = 20
CARD_H = 58
DAYS = 60


class ScheduleWindow(CardListMixin, tk.Toplevel):
    """Agenda of the next 60 days, grouped by day, drawn as pastel cards."""

    DELETE_PILL_HALF = 12
    DELETE_HOVER = "#fbe3ea"

    def __init__(self, master: tk.Misc, store: ScheduleStore) -> None:
        super().__init__(master)
        self.title("일정")
        self.configure(bg=BG)
        self.geometry(f"{WIDTH}x580")
        self.minsize(WIDTH, 360)
        self.attributes("-topmost", True)
        self.store = store
        self._armed: int | None = None  # event id whose delete button was pressed once

        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=PAD, pady=(18, 10))
        tk.Label(header, text="일정", font=(FONT, 17, "bold"), bg=BG, fg=TEXT).pack(side="left")
        self.summary = tk.Label(header, font=(FONT, 10), bg=BG, fg=SUBTLE)
        self.summary.pack(side="left", padx=(10, 0), pady=(6, 0))

        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self.refresh())
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind(sequence, self._scroll)
        self.canvas.bind("<Button-1>", self._disarm, add="+")
        self.bind("<FocusIn>", lambda event: self.refresh() if event.widget is self else None)
        self.bind("<Escape>", lambda _event: self.destroy())

    # ----- drawing ------------------------------------------------------------------

    def refresh(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        today = datetime.now().date()
        start = datetime.combine(today, time(0, 0))
        events = self.store.between(start, start + timedelta(days=DAYS + 1))
        upcoming = sum(1 for event in events if event.all_day or event.start >= datetime.now())
        self.summary.configure(text=f"앞으로 {DAYS}일 · {upcoming}개 남음" if events else f"앞으로 {DAYS}일")
        width = max(canvas.winfo_width(), WIDTH)
        if not events:
            self._empty(width)
            canvas.configure(scrollregion=(0, 0, width, canvas.winfo_height()))
            return

        y = 4
        by_day: dict[date, list[Event]] = {}
        for event in events:
            by_day.setdefault(event.start.date(), []).append(event)
        for day, day_events in by_day.items():
            y = self._day_header(day, today, y, width)
            for event in day_events:
                y = self._card(event, y, width)
            y += 10
        canvas.configure(scrollregion=(0, 0, width, y + PAD))

    def _empty(self, width: int) -> None:
        cx, cy = width // 2, max(self.canvas.winfo_height() // 2 - 30, 120)
        self.canvas.create_oval(cx - 34, cy - 70, cx + 34, cy - 2, fill=SOFT, outline="")
        # Little calendar glyph
        self.canvas.create_rectangle(cx - 16, cy - 50, cx + 16, cy - 20, fill=CARD, outline=ACCENT, width=2)
        self.canvas.create_rectangle(cx - 16, cy - 50, cx + 16, cy - 42, fill=ACCENT, outline=ACCENT)
        self.canvas.create_text(cx, cy + 22, text="등록된 일정이 없어요", font=(FONT, 12, "bold"), fill=TEXT)
        self.canvas.create_text(cx, cy + 42, text="비서에게 \"내일 3시에 회의 잡아줘\"라고\n말해 보세요.",
                                anchor="n", font=(FONT, 10), fill=SUBTLE, justify="center")

    def _day_header(self, day: date, today: date, y: int, width: int) -> int:
        delta = (day - today).days
        relative = {0: "오늘", 1: "내일", 2: "모레"}.get(delta)
        color = TODAY if delta == 0 else ACCENT if delta < 3 else SUBTLE
        x = PAD
        if relative:
            label = self.canvas.create_text(x, y + 12, text=relative, anchor="w", font=(FONT, 11, "bold"), fill=color)
            x = self.canvas.bbox(label)[2] + 8
        self.canvas.create_text(x, y + 12, text=format_day(day), anchor="w", font=(FONT, 10), fill=SUBTLE if relative else TEXT)
        return y + 30

    def _card(self, event: Event, y: int, width: int) -> int:
        canvas = self.canvas
        x1, x2, y2 = PAD, width - PAD, y + CARD_H
        past = not event.all_day and event.start < datetime.now()
        round_rect(canvas, x1, y + 2, x2, y2 + 2, 12, fill=SHADOW, outline="")
        round_rect(canvas, x1, y, x2, y2, 12, fill=CARD, outline=CARD_LINE, width=1)
        # Accent stripe on the left edge
        canvas.create_rectangle(x1 + 1, y + 10, x1 + 4, y2 - 10, fill=SUBTLE if past else ACCENT, outline="")

        time_text = "종일" if event.all_day else event.start.strftime("%H:%M")
        canvas.create_text(x1 + 18, y + CARD_H // 2, text=time_text, anchor="w",
                           font=(FONT, 12, "bold"), fill=SUBTLE if past else TEXT)
        title_color = SUBTLE if past else TEXT
        title_font = (FONT, 11, "bold")
        canvas.create_text(x1 + 84, y + 20, text=fit(event.title, title_font, x2 - x1 - 130), anchor="w",
                           font=title_font, fill=title_color)
        canvas.create_text(x1 + 84, y + 40, text=_remind_text(event, past), anchor="w", font=(FONT, 9), fill=SUBTLE)

        self._delete_button(event.id, x2 - 22, y + CARD_H // 2)
        return y2 + 8


def _remind_text(event: Event, past: bool) -> str:
    if past:
        return "지난 일정"
    if event.remind_at is None:
        return "알림 없음"
    if event.reminded:
        return "알림 완료"
    return f"알림 {event.remind_at.strftime('%H:%M')}" if event.remind_at.date() == event.start.date() \
        else f"알림 {event.remind_at.strftime('%m/%d %H:%M')}"
