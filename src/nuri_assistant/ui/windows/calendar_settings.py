from __future__ import annotations

import queue
import threading
import tkinter as tk
from typing import Callable

from ..theme import BG, CARD_LINE, DANGER, FONT, SUBTLE, TEXT, TODAY, button


POLL_MS = 150
MAX_URLS = 3
HELP = (
    "구글 캘린더: 설정 → 내 캘린더의 설정 → 캘린더 통합 → 'iCal 형식의 비공개 주소'를 복사해 붙여 넣어요. "
    "이 주소는 비밀번호처럼 다뤄 주세요.\n.ics 파일 경로도 돼요."
)


class CalendarSettingsWindow(tk.Toplevel):
    """Calendar addresses (one per line, up to 3) with a button that loads them right away."""

    def __init__(
        self,
        master: tk.Misc,
        urls: list[str],
        on_save: Callable[[list[str]], None],
        sync_now: Callable[[list[str]], int],
    ) -> None:
        super().__init__(master)
        self.title("캘린더 연결")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self._on_save, self._sync_now = on_save, sync_now
        self._results: queue.Queue = queue.Queue()
        self._loading = False

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=20)
        tk.Label(body, text="캘린더 연결", font=(FONT, 16, "bold"), bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(body, text="캘린더의 일정을 읽어 와서 알림과 브리핑에 함께 보여 줘요.\n읽기만 하고 캘린더는 고치지 않아요.",
                 font=(FONT, 9), bg=BG, fg=SUBTLE, justify="left").pack(anchor="w", pady=(2, 12))
        self.text = tk.Text(body, width=52, height=4, font=(FONT, 10), bg="#ffffff", fg=TEXT, relief="flat",
                            highlightthickness=1, highlightbackground=CARD_LINE, highlightcolor=CARD_LINE, wrap="none")
        self.text.pack(fill="x")
        self.text.insert("1.0", "\n".join(urls))
        tk.Label(body, text=HELP, font=(FONT, 8), bg=BG, fg=SUBTLE, wraplength=380, justify="left").pack(anchor="w", pady=(6, 0))
        self.status = tk.Label(body, text="", font=(FONT, 9), bg=BG, fg=SUBTLE, anchor="w", wraplength=380, justify="left")
        self.status.pack(fill="x", pady=(10, 0))
        actions = tk.Frame(body, bg=BG)
        actions.pack(fill="x", pady=(8, 0))
        self.load_button = button(actions, "지금 불러오기", self._load, primary=False)
        self.load_button.pack(side="left")
        button(actions, "닫기", self.destroy, primary=False).pack(side="right")
        button(actions, "저장", self._save).pack(side="right", padx=6)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.after(POLL_MS, self._poll)

    def _urls(self) -> list[str]:
        lines = [line.strip() for line in self.text.get("1.0", "end").splitlines()]
        return [line for line in lines if line][:MAX_URLS]

    def _load(self) -> None:
        if self._loading:
            return
        urls = self._urls()
        if not urls:
            self.status.configure(text="주소나 파일 경로를 먼저 적어 주세요.", fg=DANGER)
            return
        self._loading = True
        self.status.configure(text="불러오는 중이에요...", fg=SUBTLE)
        threading.Thread(target=self._worker, args=(urls,), daemon=True).start()

    def _worker(self, urls: list[str]) -> None:
        try:
            self._results.put(("done", self._sync_now(urls)))
        except Exception as exc:  # noqa: BLE001 - shown in the window
            self._results.put(("failed", str(exc) or "불러오지 못했어요."))

    def _save(self) -> None:
        self._on_save(self._urls())
        self.destroy()

    def _poll(self) -> None:
        try:
            if not self.winfo_exists():
                return
            while True:
                try:
                    kind, value = self._results.get_nowait()
                except queue.Empty:
                    break
                self._loading = False
                if kind == "done":
                    self.status.configure(text=f"일정 {value}개를 불러왔어요.", fg=TODAY)
                else:
                    self.status.configure(text=value, fg=DANGER)
        except tk.TclError:
            return
        finally:
            try:
                if self.winfo_exists():
                    self.after(POLL_MS, self._poll)
            except tk.TclError:
                pass
