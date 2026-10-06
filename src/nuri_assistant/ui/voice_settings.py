from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from typing import Callable

from ..companion import CompanionSettings, Persona
from ..voice import ENGINES, Voice, VoicevoxClient
from .theme import ACCENT, ACCENT_DARK, BG, CARD, CARD_LINE, FONT, SOFT, SUBTLE, TEXT, button, entry


VOICEVOX_SITE = "https://voicevox.hiroshiba.jp/"


class VoiceSettingsWindow(tk.Toplevel):
    """Turn the Japanese voice on/off, pick the engine and this character's voice, and preview it."""

    def __init__(
        self,
        master: tk.Misc,
        settings: CompanionSettings,
        persona: Persona,
        on_save: Callable[..., None],
        preview: Callable[[str, int], None],
    ) -> None:
        super().__init__(master)
        self.title("음성 설정")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.settings, self.persona, self.on_save, self.preview = settings, persona, on_save, preview
        self.voices: list[Voice] = []
        self.selected_id = settings.voice_ids.get(persona.id, persona.voice_id)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=20)
        tk.Label(body, text="음성 설정", font=(FONT, 16, "bold"), bg=BG, fg=TEXT).pack(anchor="w")
        link = tk.Label(body, text="VOICEVOX(무료)를 설치하고 켜 두면 캐릭터가 일본어로 말해요  ↗",
                        font=(FONT, 9, "underline"), bg=BG, fg=ACCENT_DARK, cursor="hand2")
        link.pack(anchor="w", pady=(2, 12))
        link.bind("<Button-1>", lambda _event: webbrowser.open(VOICEVOX_SITE))

        self.enabled = tk.BooleanVar(value=settings.voice_enabled)
        tk.Checkbutton(body, text="음성으로 말하기", variable=self.enabled, font=(FONT, 11, "bold"), bg=BG, fg=TEXT,
                       activebackground=BG, selectcolor=CARD, highlightthickness=0).pack(anchor="w")

        engine_row = tk.Frame(body, bg=BG)
        engine_row.pack(fill="x", pady=(10, 0))
        tk.Label(engine_row, text="엔진 주소", width=9, anchor="w", font=(FONT, 10), bg=BG, fg=TEXT).pack(side="left")
        self.url = entry(engine_row, width=30)
        self.url.insert(0, settings.voice_url)
        self.url.pack(side="left", ipady=4)
        presets = tk.Frame(body, bg=BG)
        presets.pack(fill="x", pady=(4, 0))
        tk.Label(presets, text="", width=9, bg=BG).pack(side="left")
        for name, url in ENGINES.items():
            chip = tk.Label(presets, text=name, font=(FONT, 9, "bold"), bg=SOFT, fg=ACCENT_DARK, padx=10, pady=3, cursor="hand2")
            chip.pack(side="left", padx=(0, 6))
            chip.bind("<Button-1>", lambda _event, url=url: self._set_url(url))

        tk.Label(body, text=f"{persona.name}의 목소리", font=(FONT, 11, "bold"), bg=BG, fg=TEXT).pack(anchor="w", pady=(16, 4))
        frame = tk.Frame(body, bg=CARD, highlightthickness=1, highlightbackground=CARD_LINE)
        frame.pack(fill="x")
        self.listbox = tk.Listbox(frame, height=8, font=(FONT, 10), bg=CARD, fg=TEXT, bd=0, highlightthickness=0,
                                  selectbackground=ACCENT, selectforeground="#ffffff", activestyle="none")
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        scrollbar.pack(side="right", fill="y")
        self.listbox.bind("<<ListboxSelect>>", self._picked)
        self.status = tk.Label(body, text="목소리 목록을 불러오는 중…", font=(FONT, 9), bg=BG, fg=SUBTLE, anchor="w")
        self.status.pack(fill="x", pady=(4, 0))
        tk.Label(body, text="VOICEVOX 캐릭터 음성을 공개 콘텐츠에 쓸 때는 'VOICEVOX:캐릭터명' 표기 등 각 캐릭터 이용 규약을 지켜야 해요.",
                 font=(FONT, 8), bg=BG, fg=SUBTLE, wraplength=380, justify="left").pack(anchor="w", pady=(6, 0))

        actions = tk.Frame(body, bg=BG)
        actions.pack(fill="x", pady=(16, 0))
        button(actions, "저장", self._save).pack(side="right")
        button(actions, "취소", self.destroy, primary=False).pack(side="right", padx=6)
        button(actions, "들어보기", self._preview, primary=False).pack(side="left")
        self.bind("<Escape>", lambda _event: self.destroy())
        self._load_voices()

    def _set_url(self, url: str) -> None:
        self.url.delete(0, "end")
        self.url.insert(0, url)
        self._load_voices()

    def _load_voices(self) -> None:
        url = self.url.get().strip()
        self.status.configure(text="목소리 목록을 불러오는 중…", fg=SUBTLE)

        def work() -> None:
            try:
                voices, error = VoicevoxClient(url).voices(), ""
            except Exception as exc:  # noqa: BLE001 - shown in the window
                voices, error = [], str(exc)
            self.after(0, lambda: self._show_voices(voices, error))

        threading.Thread(target=work, daemon=True).start()

    def _show_voices(self, voices: list[Voice], error: str) -> None:
        if not self.winfo_exists():
            return
        self.voices = voices
        self.listbox.delete(0, "end")
        for voice in voices:
            self.listbox.insert("end", voice.label)
        if error:
            self.status.configure(text=error, fg="#e06c8a")
            return
        ids = [voice.id for voice in voices]
        if self.selected_id in ids:
            index = ids.index(self.selected_id)
            self.listbox.selection_set(index)
            self.listbox.see(index)
        self.status.configure(text=f"목소리 {len(voices)}개", fg=SUBTLE)

    def _picked(self, _event: tk.Event) -> None:
        selection = self.listbox.curselection()
        if selection:
            self.selected_id = self.voices[selection[0]].id

    def _preview(self) -> None:
        self.preview(self.url.get().strip(), self.selected_id)

    def _save(self) -> None:
        voice_ids = dict(self.settings.voice_ids)
        voice_ids[self.persona.id] = self.selected_id
        self.on_save(voice_enabled=self.enabled.get(), voice_url=self.url.get().strip(), voice_ids=voice_ids)
        self.destroy()
