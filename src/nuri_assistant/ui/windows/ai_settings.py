from __future__ import annotations

import queue
import threading
import tkinter as tk
from typing import Callable

from ...companion import CompanionSettings
from ..theme import ACCENT_DARK, BG, DANGER, FONT, SOFT, SOFT_HOVER, SUBTLE, TEXT, button, entry


POLL_MS = 150
HISTORY_MIN, HISTORY_MAX = 4, 100
SMALL_MODEL = "qwen3:4b"  # suggested for light mode; still calls tools, needs about half the memory


class AISettingsWindow(tk.Toplevel):
    """Model name (with installed-model chips), Ollama address, conversation memory length and light mode."""

    def __init__(
        self,
        master: tk.Misc,
        settings: CompanionSettings,
        installed: Callable[[], list[str]],
        on_save: Callable[..., None],
    ) -> None:
        super().__init__(master)
        self.title("AI 설정")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.on_save = on_save
        self._results: queue.Queue = queue.Queue()

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=20)
        tk.Label(body, text="AI 설정", font=(FONT, 16, "bold"), bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(body, text="대화는 이 PC의 Ollama가 맡아요.", font=(FONT, 9), bg=BG, fg=SUBTLE).pack(anchor="w", pady=(2, 14))

        tk.Label(body, text="모델 이름", font=(FONT, 10, "bold"), bg=BG, fg=TEXT).pack(anchor="w")
        self.model = entry(body, width=36)
        self.model.insert(0, settings.model)
        self.model.pack(fill="x", ipady=4, pady=(4, 6))
        self.chips = tk.Frame(body, bg=BG)
        self.chips.pack(fill="x")
        self.chips_note = tk.Label(self.chips, text="설치된 모델을 찾는 중이에요...", font=(FONT, 9), bg=BG, fg=SUBTLE)
        self.chips_note.pack(anchor="w")

        tk.Label(body, text="Ollama 주소", font=(FONT, 10, "bold"), bg=BG, fg=TEXT).pack(anchor="w", pady=(14, 0))
        self.url = entry(body, width=36)
        self.url.insert(0, settings.ollama_url)
        self.url.pack(fill="x", ipady=4, pady=(4, 0))

        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(14, 0))
        tk.Label(row, text="대화 기억 길이", font=(FONT, 10, "bold"), bg=BG, fg=TEXT).pack(side="left")
        self.history = entry(row, width=5)
        self.history.insert(0, str(settings.history_limit))
        self.history.pack(side="left", padx=(10, 6), ipady=4)
        tk.Label(row, text=f"개 ({HISTORY_MIN}~{HISTORY_MAX}, 길수록 느려져요)", font=(FONT, 9), bg=BG, fg=SUBTLE).pack(side="left")

        self.light = tk.BooleanVar(value=settings.light_mode)
        tk.Checkbutton(body, text="가벼운 모드", variable=self.light, font=(FONT, 10, "bold"), bg=BG, fg=TEXT,
                       activebackground=BG, selectcolor="#ffffff", highlightthickness=0, bd=0, anchor="w",
                       command=self._light_hint).pack(fill="x", pady=(14, 0))
        tk.Label(body, text="음성을 끄고, 움직임을 줄이고, AI가 한 번에 읽는 양을 줄여요. 느린 PC·노트북용.",
                 font=(FONT, 9), bg=BG, fg=SUBTLE, wraplength=380, justify="left").pack(anchor="w")
        self.light_note = tk.Label(body, text="", font=(FONT, 9), bg=BG, fg=ACCENT_DARK, cursor="hand2",
                                   wraplength=380, justify="left")
        self.light_note.pack(anchor="w")
        self.light_note.bind("<Button-1>", lambda _event: self._pick(SMALL_MODEL))
        self._light_hint()

        self.notice = tk.Label(body, text="", font=(FONT, 9), bg=BG, fg=DANGER, anchor="w")
        self.notice.pack(fill="x", pady=(10, 0))
        actions = tk.Frame(body, bg=BG)
        actions.pack(fill="x", pady=(8, 0))
        button(actions, "저장", self._save).pack(side="right")
        button(actions, "취소", self.destroy, primary=False).pack(side="right", padx=6)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._save())

        threading.Thread(target=self._load_models, args=(installed,), daemon=True).start()
        self.after(POLL_MS, self._poll)

    # ----- installed models (worker thread -> queue -> Tk) ------------------------------

    def _load_models(self, installed: Callable[[], list[str]]) -> None:
        try:
            self._results.put(("models", list(installed())))
        except Exception:
            self._results.put(("error", None))

    def _poll(self) -> None:
        try:
            if not self.winfo_exists():
                return
            try:
                kind, value = self._results.get_nowait()
            except queue.Empty:
                self.after(POLL_MS, self._poll)
                return
            self._show_models(value if kind == "models" else None)
        except tk.TclError:
            return

    def _show_models(self, models: list[str] | None) -> None:
        self.chips_note.pack_forget()
        if models is None:
            tk.Label(self.chips, text="Ollama에 연결하지 못했어요", font=(FONT, 9), bg=BG, fg=SUBTLE).pack(anchor="w")
            return
        if not models:
            tk.Label(self.chips, text="설치된 모델이 없어요", font=(FONT, 9), bg=BG, fg=SUBTLE).pack(anchor="w")
            return
        tk.Label(self.chips, text="설치된 모델 (눌러서 고르기)", font=(FONT, 9), bg=BG, fg=SUBTLE).pack(anchor="w")
        flow = tk.Frame(self.chips, bg=BG)
        flow.pack(fill="x", pady=(4, 0))
        for index, name in enumerate(models):
            chip = tk.Label(flow, text=name, font=(FONT, 9, "bold"), bg=SOFT, fg=ACCENT_DARK, padx=10, pady=4, cursor="hand2")
            chip.grid(row=index // 3, column=index % 3, padx=(0, 6), pady=2, sticky="w")
            chip.bind("<Button-1>", lambda _event, value=name: self._pick(value))
            chip.bind("<Enter>", lambda _event, widget=chip: widget.configure(bg=SOFT_HOVER))
            chip.bind("<Leave>", lambda _event, widget=chip: widget.configure(bg=SOFT))

    def _light_hint(self) -> None:
        small = self.light.get() and self.model.get().strip() != SMALL_MODEL
        self.light_note.configure(text=f"더 가볍게: 작은 모델 {SMALL_MODEL}로 바꾸기 (누르기, 먼저 ollama pull {SMALL_MODEL})"
                                  if small else "")

    def _pick(self, name: str) -> None:
        self.model.delete(0, "end")
        self.model.insert(0, name)
        self._light_hint()

    # ----- save -------------------------------------------------------------------------

    def _save(self) -> None:
        model = self.model.get().strip()
        url = self.url.get().strip().rstrip("/")
        if not model:
            self.notice.configure(text="모델 이름을 적어 주세요.")
            return
        if not url.startswith(("http://", "https://")):
            self.notice.configure(text="주소는 http:// 또는 https://로 시작해야 해요.")
            return
        try:
            limit = int(self.history.get().strip())
        except ValueError:
            limit = -1
        if not HISTORY_MIN <= limit <= HISTORY_MAX:
            self.notice.configure(text=f"대화 기억 길이는 {HISTORY_MIN}~{HISTORY_MAX} 사이 숫자로 적어 주세요.")
            return
        self.on_save(model=model, ollama_url=url, history_limit=limit, light_mode=self.light.get())
        self.destroy()
