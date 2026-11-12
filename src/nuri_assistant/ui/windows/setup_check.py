from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from typing import Callable, Iterator

from ...companion import Step, ready
from ..theme import BG, DANGER, FONT, SUBTLE, TEXT, TODAY, button


POLL_MS = 150
DOWNLOAD_URL = "https://ollama.com/download"
GRAY = SUBTLE


class SetupCheckWindow(tk.Toplevel):
    """Step-by-step readiness list (Ollama, model, voice) with a button that downloads the model."""

    def __init__(
        self,
        master: tk.Misc,
        run_check: Callable[[], list[Step]],
        pull: Callable[[], Iterator[tuple[str, int | None]]],
        model: str,
    ) -> None:
        super().__init__(master)
        self.title("준비 확인")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self._run_check, self._pull, self.model = run_check, pull, model
        self._results: queue.Queue = queue.Queue()
        self._steps: list[Step] | None = None
        self._checking = False
        self._pulling = False
        self._progress = ""
        self._error = ""

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=20)
        tk.Label(body, text="준비 확인", font=(FONT, 16, "bold"), bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(body, text="대화에 필요한 것들이 준비됐는지 살펴봐요.", font=(FONT, 9), bg=BG, fg=SUBTLE).pack(anchor="w", pady=(2, 14))
        self.list_frame = tk.Frame(body, bg=BG, width=380, height=170)
        self.list_frame.pack(fill="x")
        self.list_frame.pack_propagate(False)
        self.status = tk.Label(body, text="", font=(FONT, 9), bg=BG, fg=SUBTLE, anchor="w", wraplength=380, justify="left")
        self.status.pack(fill="x", pady=(10, 0))
        self.actions = tk.Frame(body, bg=BG)
        self.actions.pack(fill="x", pady=(8, 0))
        self.bind("<Escape>", lambda _event: self.destroy())

        self._render()
        self.recheck()
        self.after(POLL_MS, self._poll)

    # ----- worker threads (-> queue -> Tk) ----------------------------------------------

    def recheck(self) -> None:
        if self._checking:
            return
        self._checking = True
        threading.Thread(target=self._check_worker, daemon=True).start()
        self._render()

    def _check_worker(self) -> None:
        try:
            self._results.put(("steps", self._run_check()))
        except Exception as exc:  # noqa: BLE001 - shown in the window
            self._results.put(("check_error", str(exc)))

    def _start_pull(self) -> None:
        if self._pulling:
            return
        self._pulling = True
        self._error = ""
        self._progress = "받는 중…"
        threading.Thread(target=self._pull_worker, daemon=True).start()
        self._render()

    def _pull_worker(self) -> None:
        try:
            for status, percent in self._pull():
                self._results.put(("progress", f"받는 중… {percent}%" if percent is not None else status))
            self._results.put(("pull_done", None))
        except Exception as exc:  # noqa: BLE001 - shown in the window
            self._results.put(("pull_failed", str(exc)))

    # ----- polling ----------------------------------------------------------------------

    def _poll(self) -> None:
        try:
            if not self.winfo_exists():
                return
            self._drain()
        except tk.TclError:
            return
        finally:
            try:
                if self.winfo_exists():
                    self.after(POLL_MS, self._poll)
            except tk.TclError:
                pass

    def _drain(self) -> None:
        changed = False
        while True:
            try:
                kind, value = self._results.get_nowait()
            except queue.Empty:
                break
            changed = True
            if kind == "steps":
                self._steps, self._checking = value, False
            elif kind == "check_error":
                self._steps, self._checking, self._error = None, False, value
            elif kind == "progress":
                self._progress = value
            elif kind == "pull_done":
                self._pulling = False
                self._checking = False
                self.recheck()
            elif kind == "pull_failed":
                self._pulling, self._error = False, value
        if changed:
            self._render()

    # ----- drawing ----------------------------------------------------------------------

    def _render(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        for child in self.actions.winfo_children():
            child.destroy()
        steps = self._steps or []
        if self._steps is None:
            tk.Label(self.list_frame, text="확인하는 중이에요..." if self._checking else "아직 확인하지 않았어요.",
                     font=(FONT, 9), bg=BG, fg=SUBTLE).pack(anchor="w")
        for step in steps:
            self._draw_step(step)

        by_key = {step.key: step for step in steps}
        if self._pulling:
            self.status.configure(text=self._progress, fg=SUBTLE)
        elif self._error:
            self.status.configure(text=self._error, fg=DANGER)
        elif self._steps is not None and ready(steps):
            self.status.configure(text="준비 끝! 이제 말을 걸어 보세요.", fg=TODAY)
        else:
            self.status.configure(text="", fg=SUBTLE)

        if self._steps is not None and not self._pulling:
            if "ollama" in by_key and not by_key["ollama"].ok:
                button(self.actions, "Ollama 설치 페이지 열기", lambda: webbrowser.open(DOWNLOAD_URL)).pack(side="left")
            elif "model" in by_key and not by_key["model"].ok:
                button(self.actions, "모델 받기", self._start_pull).pack(side="left")
        button(self.actions, "닫기", self.destroy, primary=False).pack(side="right")
        if not self._pulling:
            button(self.actions, "다시 확인", self.recheck, primary=False).pack(side="right", padx=6)

    def _draw_step(self, step: Step) -> None:
        color = TODAY if step.ok else (GRAY if step.optional else DANGER)
        row = tk.Frame(self.list_frame, bg=BG)
        row.pack(fill="x", pady=(0, 8))
        dot = tk.Canvas(row, width=16, height=16, bg=BG, highlightthickness=0)
        dot.create_oval(2, 2, 14, 14, fill=color, outline=color)
        dot.grid(row=0, column=0, sticky="n", pady=(3, 0))
        tk.Label(row, text=step.title, font=(FONT, 10, "bold"), bg=BG, fg=TEXT, anchor="w").grid(row=0, column=1, sticky="w", padx=(8, 0))
        tk.Label(row, text=step.detail, font=(FONT, 9), bg=BG, fg=SUBTLE, anchor="w", wraplength=350, justify="left").grid(
            row=1, column=1, sticky="w", padx=(8, 0))
