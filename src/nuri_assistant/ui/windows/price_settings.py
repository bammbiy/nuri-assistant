from __future__ import annotations

import tkinter as tk
import webbrowser
from typing import Callable

from ...companion import CompanionSettings
from ..theme import ACCENT_DARK, BG, FONT, SUBTLE, TEXT, button, entry


NAVER_GUIDE = "https://developers.naver.com/apps/#/register"


class PriceSettingsWindow(tk.Toplevel):
    """API keys and check interval for price watching. Keys stay in the local settings file."""

    def __init__(self, master: tk.Misc, settings: CompanionSettings, on_save: Callable[..., None]) -> None:
        super().__init__(master)
        self.title("가격 알림 설정")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.on_save = on_save

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=20)
        tk.Label(body, text="가격 알림 설정", font=(FONT, 16, "bold"), bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(body, text="키는 이 PC의 설정 파일에만 저장돼요.", font=(FONT, 9), bg=BG, fg=SUBTLE).pack(anchor="w", pady=(2, 14))

        self.fields: dict[str, tk.Entry] = {}
        self._section(body, "네이버 쇼핑 검색 API (무료)", NAVER_GUIDE,
                      "developers.naver.com에서 애플리케이션 등록 → '검색' API 선택 → Client ID/Secret 복사")
        self._field(body, "naver_client_id", "Client ID", settings.naver_client_id)
        self._field(body, "naver_client_secret", "Client Secret", settings.naver_client_secret, secret=True)
        tk.Label(body, text="상품 링크로 등록한 알림은 키 없이도 동작해요 (가격 정보를 공개하는 쇼핑몰만).",
                 font=(FONT, 9), bg=BG, fg=SUBTLE, wraplength=420, justify="left").pack(anchor="w", pady=(6, 0))

        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(14, 0))
        tk.Label(row, text="확인 주기", font=(FONT, 10, "bold"), bg=BG, fg=TEXT).pack(side="left")
        self.interval = entry(row, width=5)
        self.interval.insert(0, str(settings.price_check_minutes))
        self.interval.pack(side="left", padx=(10, 6), ipady=4)
        tk.Label(row, text="분마다 (최소 10분)", font=(FONT, 10), bg=BG, fg=SUBTLE).pack(side="left")

        actions = tk.Frame(body, bg=BG)
        actions.pack(fill="x", pady=(20, 0))
        button(actions, "저장", self._save).pack(side="right")
        button(actions, "취소", self.destroy, primary=False).pack(side="right", padx=6)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._save())

    def _section(self, parent: tk.Misc, title: str, link: str, guide: str) -> None:
        tk.Label(parent, text=title, font=(FONT, 11, "bold"), bg=BG, fg=TEXT).pack(anchor="w", pady=(8, 0))
        guide_label = tk.Label(parent, text=f"{guide}  ↗", font=(FONT, 9, "underline"), bg=BG, fg=ACCENT_DARK, cursor="hand2")
        guide_label.pack(anchor="w", pady=(0, 6))
        guide_label.bind("<Button-1>", lambda _event: webbrowser.open(link))

    def _field(self, parent: tk.Misc, key: str, label: str, value: str, secret: bool = False) -> None:
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, width=12, anchor="w", font=(FONT, 10), bg=BG, fg=TEXT).pack(side="left")
        widget = entry(row, width=34, show="•" if secret else "")
        widget.insert(0, value)
        widget.pack(side="left", fill="x", expand=True, ipady=4)
        self.fields[key] = widget

    def _save(self) -> None:
        try:
            minutes = max(int(self.interval.get().strip()), 10)
        except ValueError:
            minutes = 60
        self.on_save(price_check_minutes=minutes, **{key: widget.get().strip() for key, widget in self.fields.items()})
        self.destroy()
