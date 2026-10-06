from __future__ import annotations

import tkinter as tk
import webbrowser
from datetime import datetime
from typing import Callable

from ..pricewatch import Watch, WatchStore, won
from ..pricewatch.tools import _price
from .chatbox import draw_pill
from .theme import (
    ACCENT, BG, CARD, CARD_LINE, DANGER, FONT, SHADOW, SOFT, SUBTLE, TEXT, TODAY, button, entry, fit, round_rect,
)


WIDTH = 460
PAD = 20
CARD_H = 92


class PriceWindow(tk.Toplevel):
    """Price watches as cards: current lowest price, target, history low, open/delete."""

    def __init__(self, master: tk.Misc, store: WatchStore, check_now: Callable[[], None], has_source: Callable[[], bool]) -> None:
        super().__init__(master)
        self.title("최저가 알림")
        self.configure(bg=BG)
        self.geometry(f"{WIDTH}x620")
        self.minsize(WIDTH, 400)
        self.attributes("-topmost", True)
        self.store = store
        self.check_now = check_now
        self.has_source = has_source
        self._armed: int | None = None

        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=PAD, pady=(18, 8))
        tk.Label(header, text="최저가 알림", font=(FONT, 17, "bold"), bg=BG, fg=TEXT).pack(side="left")
        button(header, "지금 확인", self._check_clicked, primary=False).pack(side="right")

        form = tk.Frame(self, bg=BG)
        form.pack(fill="x", padx=PAD, pady=(0, 6))
        self.query = entry(form, width=24)
        self.target = entry(form, width=10)
        self._placeholder(self.query, "상품 이름 또는 링크")
        self._placeholder(self.target, "목표가 (선택)")
        self.query.pack(side="left", fill="x", expand=True, ipady=6)
        self.target.pack(side="left", padx=6, ipady=6)
        button(form, "추가", self._add).pack(side="left")
        self.notice = tk.Label(self, text="", font=(FONT, 9), bg=BG, fg=SUBTLE, anchor="w", justify="left", wraplength=WIDTH - 2 * PAD)
        self.notice.pack(fill="x", padx=PAD)

        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True, pady=(4, 0))
        self.canvas.bind("<Configure>", lambda _event: self.refresh())
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind(sequence, self._scroll)
        self.canvas.bind("<Button-1>", self._disarm, add="+")
        self.bind("<FocusIn>", lambda event: self.refresh() if event.widget is self else None)
        self.bind("<Escape>", lambda _event: self.destroy())
        self._update_notice()

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
        text = self._value(self.query)
        if not text:
            return
        is_url = text.startswith(("http://", "https://"))
        if not is_url and not self.has_source():
            self.notice.configure(text="상품 이름으로 감시하려면 메뉴의 '가격 알림 설정'에서 네이버 쇼핑 API 키를 먼저 넣어 주세요.", fg=DANGER)
            return
        target = _price(self._value(self.target))
        self.store.add("" if is_url else text, text if is_url else "", target)
        for widget in (self.query, self.target):
            widget.delete(0, "end")
            widget.event_generate("<FocusOut>")
        self.canvas.focus_set()
        self.check_now()
        self.refresh()

    def _update_notice(self) -> None:
        if not self.has_source():
            self.notice.configure(text="API 키가 없어서 상품 링크 감시만 돼요. 메뉴의 '가격 알림 설정'에서 네이버 쇼핑 키를 넣어 주세요.", fg=DANGER)
        else:
            self.notice.configure(text="이름으로 등록하면 네이버 쇼핑(설정 시 쿠팡 포함)에서 최저가를 찾아요.", fg=SUBTLE)

    def _check_clicked(self) -> None:
        self.check_now()
        self.notice.configure(text="가격을 확인하는 중이에요. 잠시 뒤 새로 고쳐져요.", fg=SUBTLE)
        self.after(4000, self.refresh)
        self.after(4000, self._update_notice)

    # ----- drawing ----------------------------------------------------------------------

    def refresh(self) -> None:
        if not self.winfo_exists():
            return
        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), WIDTH)
        watches = self.store.all()
        if not watches:
            cx, cy = width // 2, max(canvas.winfo_height() // 2 - 40, 110)
            canvas.create_oval(cx - 34, cy - 70, cx + 34, cy - 2, fill=SOFT, outline="")
            canvas.create_text(cx, cy - 36, text="₩", font=(FONT, 24, "bold"), fill=ACCENT)
            canvas.create_text(cx, cy + 22, text="등록된 최저가 알림이 없어요", font=(FONT, 12, "bold"), fill=TEXT)
            canvas.create_text(cx, cy + 42, text="위에 상품을 추가하거나 비서에게\n\"에어팟 30만원 아래로 떨어지면 알려줘\"라고 말해 보세요.",
                               anchor="n", font=(FONT, 10), fill=SUBTLE, justify="center")
            canvas.configure(scrollregion=(0, 0, width, canvas.winfo_height()))
            return
        y = 6
        for watch in watches:
            y = self._card(watch, y, width)
        canvas.configure(scrollregion=(0, 0, width, y + PAD))

    def _card(self, watch: Watch, y: int, width: int) -> int:
        canvas = self.canvas
        x1, x2, y2 = PAD, width - PAD, y + CARD_H
        hit = watch.target_price is not None and watch.last_price is not None and watch.last_price <= watch.target_price
        round_rect(canvas, x1, y + 2, x2, y2 + 2, 12, fill=SHADOW, outline="")
        round_rect(canvas, x1, y, x2, y2, 12, fill=CARD, outline=TODAY if hit else CARD_LINE, width=2 if hit else 1)
        canvas.create_rectangle(x1 + 1, y + 12, x1 + 4, y2 - 12, fill=TODAY if hit else ACCENT, outline="")

        title_font = (FONT, 11, "bold")
        canvas.create_text(x1 + 18, y + 20, text=fit(watch.label, title_font, x2 - x1 - 150), anchor="w", font=title_font, fill=TEXT)
        if watch.last_price is not None:
            price = canvas.create_text(x1 + 18, y + 46, text=won(watch.last_price), anchor="w", font=(FONT, 15, "bold"), fill=TODAY if hit else TEXT)
            canvas.create_text(canvas.bbox(price)[2] + 8, y + 48, text=watch.last_mall, anchor="w", font=(FONT, 9), fill=SUBTLE)
        else:
            canvas.create_text(x1 + 18, y + 46, text="확인 전", anchor="w", font=(FONT, 13, "bold"), fill=SUBTLE)

        details = []
        if watch.target_price:
            details.append(f"목표 {won(watch.target_price)}")
        if watch.lowest_seen:
            details.append(f"최저 {won(watch.lowest_seen)}")
        if watch.last_checked:
            details.append(_ago(watch.last_checked))
        detail = "  ·  ".join(details)
        color = SUBTLE
        if watch.last_error:
            detail, color = watch.last_error, DANGER
        detail_font = (FONT, 9)
        canvas.create_text(x1 + 18, y + 72, text=fit(detail, detail_font, x2 - x1 - 90), anchor="w", font=detail_font, fill=color)

        if watch.last_link:
            tag = f"open_{watch.id}"
            draw_pill(canvas, x2 - 84, y + 10, x2 - 40, y + 32, fill=SOFT, tags=(tag, f"{tag}_bg"))
            canvas.create_text(x2 - 62, y + 21, text="열기", font=(FONT, 9, "bold"), fill=ACCENT, tags=(tag,))
            canvas.tag_bind(tag, "<Button-1>", lambda _e, link=watch.last_link: webbrowser.open(link))
        self._delete_button(watch, x2 - 22, y + 21)
        return y2 + 10

    def _delete_button(self, watch: Watch, cx: int, cy: int) -> None:
        canvas = self.canvas
        tag = f"delete_{watch.id}"
        if self._armed == watch.id:
            draw_pill(canvas, cx - 30, cy - 11, cx + 12, cy + 11, fill=DANGER, tags=(tag,))
            canvas.create_text(cx - 9, cy, text="삭제", font=(FONT, 9, "bold"), fill="#ffffff", tags=(tag,))
        else:
            canvas.create_oval(cx - 11, cy - 11, cx + 11, cy + 11, fill=SOFT, outline="", tags=(tag, f"{tag}_bg"))
            canvas.create_line(cx - 4, cy - 4, cx + 4, cy + 4, fill=SUBTLE, width=2, tags=(tag,))
            canvas.create_line(cx - 4, cy + 4, cx + 4, cy - 4, fill=SUBTLE, width=2, tags=(tag,))
        canvas.tag_bind(tag, "<Button-1>", lambda _e: self._delete_clicked(watch.id))

    def _delete_clicked(self, watch_id: int) -> str:
        if self._armed == watch_id:
            self.store.delete(watch_id)
            self._armed = None
        else:
            self._armed = watch_id
        self.after_idle(self.refresh)
        return "break"

    def _disarm(self, _event: tk.Event) -> None:
        current = self.canvas.find_withtag("current")
        tags = self.canvas.gettags(current[0]) if current else ()
        if self._armed is not None and not any(tag.startswith("delete_") for tag in tags):
            self._armed = None
            self.refresh()

    def _scroll(self, event: tk.Event) -> None:
        up = event.num == 4 or getattr(event, "delta", 0) > 0
        self.canvas.yview_scroll(-2 if up else 2, "units")


def _ago(moment: datetime) -> str:
    minutes = int((datetime.now() - moment).total_seconds() // 60)
    if minutes < 1:
        return "방금 확인"
    if minutes < 60:
        return f"{minutes}분 전 확인"
    if minutes < 60 * 24:
        return f"{minutes // 60}시간 전 확인"
    return f"{moment:%m/%d} 확인"
