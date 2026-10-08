from __future__ import annotations

import tkinter as tk
from typing import Callable

from ...classic.tools import RenameAction
from ..theme import (
    BG, CARD, CARD_LINE, DANGER, FONT, SHADOW, SUBTLE, TEXT, TODAY, button, draw_pill, fit, round_rect,
)
from .cards import CardListMixin

WIDTH = 520
PAD = 20
ROW_H = 58

# status -> (chip label, chip color); ready rows first, then the ones that stay as they are.
STATUS = {"ready": ("바뀜", TODAY), "skip": ("그대로", SUBTLE), "conflict": ("겹침", DANGER), "error": ("오류", DANGER)}


class RenamePreviewWindow(CardListMixin, tk.Toplevel):
    """Every file a chat rename would touch (old -> new name), with the confirm card's two choices.

    Only the wheel scrolling of CardListMixin is used; nothing here is deleted.
    """

    def __init__(self, master: tk.Misc, action: RenameAction, on_yes: Callable[[], None], on_no: Callable[[], None]) -> None:
        super().__init__(master)
        self.title("파일 이름 정리 미리보기")
        self.configure(bg=BG)
        self.geometry(f"{WIDTH}x560")
        self.minsize(420, 320)
        self.attributes("-topmost", True)
        self.action = action
        self.rows = sorted(action.previews, key=lambda p: p.status != "ready")

        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=PAD, pady=(18, 4))
        tk.Label(header, text="파일 이름 정리", font=(FONT, 17, "bold"), bg=BG, fg=TEXT).pack(side="left")
        others = len(self.rows) - action.count
        summary = f"{action.folder} · 바뀔 파일 {action.count}개" + (f" · 그대로 {others}개" if others else "")
        tk.Label(header, text=summary, font=(FONT, 10), bg=BG, fg=SUBTLE).pack(side="left", padx=(10, 0), pady=(6, 0))
        tk.Label(self, text="아래 '정리'를 누르기 전까지는 아무것도 바뀌지 않아요. 정리한 뒤에도 되돌릴 수 있어요.",
                 font=(FONT, 9), bg=BG, fg=SUBTLE, anchor="w").pack(fill="x", padx=PAD, pady=(0, 6))

        footer = tk.Frame(self, bg=BG)
        footer.pack(side="bottom", fill="x", padx=PAD, pady=12)
        button(footer, "정리", lambda: self._choose(on_yes)).pack(side="right")
        button(footer, "취소", lambda: self._choose(on_no), primary=False).pack(side="right", padx=(0, 8))

        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self.refresh())
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind(sequence, self._scroll)
        self.bind("<Escape>", lambda _event: self.destroy())

    def _choose(self, choice: Callable[[], None]) -> None:
        self.destroy()
        choice()

    def refresh(self) -> None:
        if not self.winfo_exists():
            return
        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 420)
        y = 4
        for preview in self.rows:
            x1, x2, y2 = PAD, width - PAD, y + ROW_H
            round_rect(canvas, x1, y + 2, x2, y2 + 2, 12, fill=SHADOW, outline="")
            round_rect(canvas, x1, y, x2, y2, 12, fill=CARD, outline=CARD_LINE, width=1)
            label, color = STATUS.get(preview.status, ("?", SUBTLE))
            chip_w = 52
            draw_pill(canvas, x2 - 14 - chip_w, y + ROW_H // 2 - 11, x2 - 14, y + ROW_H // 2 + 11, fill=color, tags=("chip",))
            canvas.create_text(x2 - 14 - chip_w / 2, y + ROW_H // 2, text=label, font=(FONT, 9, "bold"), fill="#ffffff")
            text_w = x2 - x1 - chip_w - 44
            canvas.create_text(x1 + 16, y + 19, text=fit(preview.source.name, (FONT, 9), text_w), anchor="w",
                               font=(FONT, 9), fill=SUBTLE)
            if preview.status == "ready":
                second, font, fill = f"→ {preview.target.name}", (FONT, 11, "bold"), TEXT
            else:
                second, font, fill = preview.message, (FONT, 10), DANGER if color == DANGER else SUBTLE
            canvas.create_text(x1 + 16, y + 39, text=fit(second, font, text_w), anchor="w", font=font, fill=fill)
            y = y2 + 8
        canvas.configure(scrollregion=(0, 0, width, y + PAD))
