from __future__ import annotations

import tkinter as tk
from datetime import datetime
from typing import Callable

from ...companion import ConversationStore, Persona
from ..theme import ACCENT, BG, CARD, CARD_LINE, FONT, SHADOW, SOFT, SUBTLE, TEXT, entry, round_rect
from .cards import CardListMixin

WIDTH = 460
PAD = 18
LIMIT = 500
BUBBLE_MAX = 0.72  # share of the canvas width a bubble may take
BUBBLE_PAD = (12, 8)
TEXT_FONT = (FONT, 10)
META_FONT = (FONT, 8)
WEEKDAYS = "월화수목금토일"
AVATAR = (64, 54)


def clean_content(role: str, content: str) -> str:
    """Stored assistant turns start with an [expression] tag; the log shows the words only."""

    if role == "assistant" and content.startswith("["):
        return content.split("]", 1)[-1].strip()
    return content


def day_label(moment: datetime, today: datetime) -> str:
    if moment.date() == today.date():
        return "오늘"
    if (today.date() - moment.date()).days == 1:
        return "어제"
    year = f"{moment.year}년 " if moment.year != today.year else ""
    return f"{year}{moment.month}월 {moment.day}일 ({WEEKDAYS[moment.weekday()]})"


def time_label(moment: datetime) -> str:
    half = "오전" if moment.hour < 12 else "오후"
    hour = moment.hour % 12 or 12
    return f"{half} {hour}:{moment.minute:02d}"


class ConversationLogWindow(CardListMixin, tk.Toplevel):
    """Messenger-style transcript: day dividers, my lines on the right, the character's on the left."""

    def __init__(
        self,
        master: tk.Misc,
        store: ConversationStore,
        persona: Persona,
        avatar: Callable[[tuple[int, int]], tk.PhotoImage | None] | None = None,
    ) -> None:
        super().__init__(master)
        self.title(f"{persona.name} 대화 기록")
        self.configure(bg=BG)
        self.geometry(f"{WIDTH}x620")
        self.minsize(380, 360)
        self.persona = persona
        self.rows = [dict(row, content=clean_content(row["role"], row["content"])) for row in store.recent(persona.id, limit=LIMIT)]
        self._query = ""

        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=PAD, pady=(16, 8))
        self._avatar = avatar(AVATAR) if avatar else None
        if self._avatar is not None:
            tk.Label(header, image=self._avatar, bg=BG).pack(side="left", padx=(0, 10))
        titles = tk.Frame(header, bg=BG)
        titles.pack(side="left", fill="x", expand=True)
        tk.Label(titles, text=f"{persona.name}와의 대화", font=(FONT, 15, "bold"), bg=BG, fg=TEXT, anchor="w").pack(fill="x")
        more = f" (최근 {LIMIT}개)" if len(self.rows) >= LIMIT else ""
        tk.Label(titles, text=f"{persona.archetype} · 메시지 {len(self.rows)}개{more}", font=(FONT, 9), bg=BG, fg=SUBTLE,
                 anchor="w").pack(fill="x")

        self.search = entry(self, width=30)
        self.search.pack(fill="x", padx=PAD, pady=(0, 8), ipady=5)
        self._hint = True
        self.search.insert(0, "대화 검색")
        self.search.configure(fg=SUBTLE)
        self.search.bind("<FocusIn>", self._clear_hint)
        self.search.bind("<KeyRelease>", lambda _event: self._search())

        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self.refresh(scroll_end=self._at_end))
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind(sequence, self._scroll)
        self.bind("<Escape>", lambda _event: self.destroy())
        self._at_end = True

    # ----- search ---------------------------------------------------------------------

    def _clear_hint(self, _event=None) -> None:
        if self._hint:
            self.search.delete(0, "end")
            self.search.configure(fg=TEXT)
            self._hint = False

    def _search(self) -> None:
        self._query = "" if self._hint else self.search.get().strip()
        self.refresh(scroll_end=not self._query)

    # ----- drawing ----------------------------------------------------------------------

    def refresh(self, scroll_end: bool = False) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 300)
        rows = [row for row in self.rows if self._query.lower() in row["content"].lower()] if self._query else self.rows
        if not rows:
            self._empty(width)
            return
        today = datetime.now()
        y, last_day, last_role = 8, None, None
        for row in rows:
            moment = _parse(row["created_at"])
            if moment and moment.date() != last_day:
                y = self._divider(day_label(moment, today), y, width)
                last_day, last_role = moment.date(), None
            y = self._bubble(row, moment, y, width, show_name=row["role"] != last_role)
            last_role = row["role"]
        canvas.configure(scrollregion=(0, 0, width, y + PAD))
        if scroll_end:
            canvas.yview_moveto(1.0)

    def _empty(self, width: int) -> None:
        canvas = self.canvas
        cx, cy = width // 2, max(canvas.winfo_height() // 2 - 30, 90)
        round_rect(canvas, cx - 34, cy - 58, cx + 34, cy - 14, 16, fill=SOFT, outline="")
        for dx in (-14, 0, 14):
            canvas.create_oval(cx + dx - 4, cy - 40, cx + dx + 4, cy - 32, fill=ACCENT, outline="")
        title = "찾는 대화가 없어요" if self._query else "아직 대화가 없어요"
        canvas.create_text(cx, cy + 6, text=title, font=(FONT, 12, "bold"), fill=TEXT)
        hint = "다른 낱말로 찾아보세요." if self._query else f"캐릭터에 마우스를 올리고 {self.persona.name}에게 말을 걸어 보세요."
        canvas.create_text(cx, cy + 28, text=hint, font=(FONT, 9), fill=SUBTLE)
        canvas.configure(scrollregion=(0, 0, width, canvas.winfo_height()))

    def _divider(self, label: str, y: int, width: int) -> int:
        canvas = self.canvas
        text = canvas.create_text(width // 2, y + 14, text=label, font=(FONT, 8, "bold"), fill=SUBTLE)
        x1, _, x2, _ = canvas.bbox(text)
        round_rect(canvas, x1 - 10, y + 4, x2 + 10, y + 24, 9, fill=SOFT, outline="")
        canvas.tag_raise(text)
        for a, b in ((PAD, x1 - 18), (x2 + 18, width - PAD)):
            canvas.create_line(a, y + 14, b, y + 14, fill=CARD_LINE)
        return y + 34

    def _bubble(self, row: dict, moment: datetime | None, y: int, width: int, show_name: bool) -> int:
        canvas = self.canvas
        mine = row["role"] == "user"
        max_text = int((width - 2 * PAD) * BUBBLE_MAX) - 2 * BUBBLE_PAD[0]
        if show_name and not mine:
            canvas.create_text(PAD + 4, y + 2, text=self.persona.name, anchor="nw", font=(FONT, 8, "bold"), fill=ACCENT)
            y += 16
        elif show_name:
            y += 4
        text = canvas.create_text(0, 0, text=row["content"], anchor="nw", width=max_text, font=TEXT_FONT,
                                  fill="#ffffff" if mine else TEXT)
        x1, y1, x2, y2 = canvas.bbox(text)
        w, h = x2 - x1 + 2 * BUBBLE_PAD[0], y2 - y1 + 2 * BUBBLE_PAD[1]
        left = width - PAD - w if mine else PAD
        if mine:
            round_rect(canvas, left, y, left + w, y + h, 14, fill=ACCENT, outline="")
        else:
            round_rect(canvas, left, y + 2, left + w, y + h + 2, 14, fill=SHADOW, outline="")
            round_rect(canvas, left, y, left + w, y + h, 14, fill=CARD, outline=CARD_LINE, width=1)
        canvas.coords(text, left + BUBBLE_PAD[0], y + BUBBLE_PAD[1])
        canvas.tag_raise(text)
        if moment:
            stamp_x, anchor = (left - 6, "se") if mine else (left + w + 6, "sw")
            canvas.create_text(stamp_x, y + h, text=time_label(moment), anchor=anchor, font=META_FONT, fill=SUBTLE)
        return y + h + 8

    def _scroll(self, event: tk.Event) -> None:
        super()._scroll(event)
        self._at_end = self.canvas.yview()[1] >= 0.999


def _parse(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
