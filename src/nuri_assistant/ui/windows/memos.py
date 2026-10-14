from __future__ import annotations

import tkinter as tk

from ...memo import Memo, MemoStore
from ..theme import ACCENT, BG, CARD, CARD_LINE, FONT, SHADOW, SOFT, SUBTLE, TEXT, button, entry, round_rect
from .cards import CardListMixin


WIDTH = 440
PAD = 20
CARD_H = 52


class MemoWindow(CardListMixin, tk.Toplevel):
    """Facts the characters remember about the user, one card each."""

    def __init__(self, master: tk.Misc, store: MemoStore) -> None:
        super().__init__(master)
        self.title("기억 수첩")
        self.configure(bg=BG)
        self.geometry(f"{WIDTH}x520")
        self.minsize(WIDTH, 340)
        self.attributes("-topmost", True)
        self.store = store
        self._armed: int | None = None

        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=PAD, pady=(18, 8))
        tk.Label(header, text="기억 수첩", font=(FONT, 17, "bold"), bg=BG, fg=TEXT).pack(side="left")
        self.summary = tk.Label(header, font=(FONT, 10), bg=BG, fg=SUBTLE)
        self.summary.pack(side="left", padx=(10, 0), pady=(6, 0))

        form = tk.Frame(self, bg=BG)
        form.pack(fill="x", padx=PAD, pady=(0, 4))
        self.text_entry = entry(form, width=30)
        self.text_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 6))
        self.text_entry.bind("<Return>", lambda _event: self._add())
        button(form, "추가", self._add).pack(side="left")

        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True, pady=(8, 0))
        self.canvas.bind("<Configure>", lambda _event: self.refresh())
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind(sequence, self._scroll)
        self.canvas.bind("<Button-1>", self._disarm, add="+")
        self.bind("<FocusIn>", lambda event: self.refresh() if event.widget is self else None)
        self.bind("<Escape>", lambda _event: self.destroy())

    def _add(self) -> None:
        text = self.text_entry.get().strip()
        if not text:
            return
        self.store.add(text)
        self.text_entry.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        if not self.winfo_exists():
            return
        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), WIDTH)
        memos = self.store.all()
        self.summary.configure(text=f"{len(memos)}개" if memos else "")
        if not memos:
            cx, cy = width // 2, max(canvas.winfo_height() // 2 - 40, 110)
            canvas.create_oval(cx - 34, cy - 70, cx + 34, cy - 2, fill=SOFT, outline="")
            canvas.create_text(cx, cy - 36, text="♥", font=(FONT, 26, "bold"), fill=ACCENT)
            canvas.create_text(cx, cy + 22, text="아직 기억한 게 없어요", font=(FONT, 12, "bold"), fill=TEXT)
            canvas.create_text(cx, cy + 42, text="비서에게 \"나 고양이 알레르기 있어\"처럼 말해 보세요.",
                               anchor="n", font=(FONT, 10), fill=SUBTLE, justify="center")
            canvas.configure(scrollregion=(0, 0, width, canvas.winfo_height()))
            return
        y = 6
        for memo in memos:
            y = self._card(memo, y, width)
        canvas.configure(scrollregion=(0, 0, width, y + PAD))

    def _card(self, memo: Memo, y: int, width: int) -> int:
        canvas = self.canvas
        x1, x2, y2 = PAD, width - PAD, y + CARD_H
        round_rect(canvas, x1, y + 2, x2, y2 + 2, 12, fill=SHADOW, outline="")
        round_rect(canvas, x1, y, x2, y2, 12, fill=CARD, outline=CARD_LINE, width=1)
        cy = y + CARD_H // 2
        canvas.create_text(x1 + 18, y + 8, text=memo.text, anchor="nw", width=x2 - x1 - 70,
                           font=(FONT, 11, "bold"), fill=TEXT)
        canvas.create_text(x1 + 18, y2 - 8, text=memo.created_at.strftime("%Y-%m-%d"), anchor="sw",
                           font=(FONT, 8), fill=SUBTLE)
        self._delete_button(memo.id, x2 - 22, cy)
        return y2 + 8
