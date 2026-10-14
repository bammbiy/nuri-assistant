from __future__ import annotations

import tkinter as tk
from typing import Callable

from ..theme import BG, FONT, SUBTLE, TEXT, button

WRAP = 420

SECTIONS = (
    ("모두 이 PC 안에서",
     "대화·일정·할 일·기억 수첩·친밀도는 이 PC의 ~/.nuri-assistant 폴더에만 저장돼요. "
     "AI 대답과 일본어 음성도 이 PC에서 돌아가요(Ollama, VOICEVOX)."),
    ("밖으로 나가는 것",
     "날씨 도시를 적으면 그 도시 이름과 좌표만 날씨 서비스(Open-Meteo)로, "
     "최저가 알림을 쓰면 상품 이름만 네이버 쇼핑으로 보내요."),
    ("직접 켜야 하는 것",
     "복사한 글 도우미와 다운로드 폴더 감시는 기본으로 꺼져 있어요. 켜도 복사한 글과 파일 내용은 저장하지 않아요."),
    ("보지 않는 것",
     "화면을 캡처하거나 입력한 키를 읽지 않아요. 자리 비움은 마지막으로 키보드·마우스를 쓴 시각만 봐요."),
    ("바꾸고 지우기",
     "메뉴의 설정 창들에서 언제든 끄고, 기억 수첩·대화 기록은 메뉴에서 지울 수 있어요."),
)


class PrivacyWindow(tk.Toplevel):
    """First-run notice: what stays on this PC, what leaves it, and what is never looked at."""

    def __init__(self, master: tk.Misc, on_close: Callable[[], None] | None = None) -> None:
        super().__init__(master)
        self.title("처음 오신 걸 환영해요")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.on_close = on_close
        self._closed = False

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=20)
        tk.Label(body, text="처음 오신 걸 환영해요", font=(FONT, 16, "bold"), bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(body, text="시작하기 전에, 제가 다루는 정보를 알려 드릴게요.", font=(FONT, 9), bg=BG, fg=SUBTLE,
                 wraplength=WRAP, justify="left").pack(anchor="w", pady=(2, 4))
        for title, text in SECTIONS:
            tk.Label(body, text=title, font=(FONT, 11, "bold"), bg=BG, fg=TEXT).pack(anchor="w", pady=(12, 2))
            tk.Label(body, text=text, font=(FONT, 10), bg=BG, fg=TEXT, wraplength=WRAP, justify="left").pack(anchor="w")

        actions = tk.Frame(body, bg=BG)
        actions.pack(fill="x", pady=(20, 0))
        button(actions, "확인", self._close).pack(side="right")
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Return>", lambda _event: self._close())

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self.on_close is not None:
                self.on_close()
        finally:
            self.destroy()
