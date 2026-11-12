"""Menu actions: settings windows, the character picker, name/model questions, log and memory.

Mixed into ``MascotApp``; relies on its settings, ``_update_settings``, stores and ``say``.
"""

from __future__ import annotations

import random
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, simpledialog

from ...companion import PERSONAS, OllamaClient, check_setup
from ...voice import VoicevoxClient
from ..windows.ai_settings import AISettingsWindow
from ..windows.conversation_log import ConversationLogWindow
from ..windows.focus_dialog import FocusDialog
from ..windows.price_settings import PriceSettingsWindow
from ..windows.routine_settings import RoutineSettingsWindow
from ..windows.setup_check import SetupCheckWindow
from .picker import CharacterPicker
from .timing import BRIEFING_DELAY_MS, HELD_NOTICE_DELAY_MS, HELD_NOTICE_GAP_MS


class MenuMixin:
    """Commands behind the character's right-click menu."""

    def open_ai_settings(self) -> None:
        def save(**changes: object) -> None:
            self._update_settings(**changes)
            threading.Thread(target=self._check_model, daemon=True).start()

        AISettingsWindow(self, self.settings, lambda: OllamaClient(self.settings.ollama_url).list_models(), save)

    def open_setup_check(self) -> None:
        window = getattr(self, "_setup_check_window", None)
        try:
            if window is not None and window.winfo_exists():
                window.deiconify()
                window.lift()
                return
        except tk.TclError:
            pass

        def voice_ok() -> bool:
            VoicevoxClient(self.settings.voice_url).voices()  # lightest existing call; raises when the engine is down
            return True

        def run_check():
            return check_setup(self.settings, OllamaClient(self.settings.ollama_url, timeout=5), voice_ok)

        self._setup_check_window = SetupCheckWindow(
            self, run_check, lambda: OllamaClient(self.settings.ollama_url).pull(self.settings.model), self.settings.model)

    def open_focus_dialog(self) -> None:
        running = self.focus_timer.state(datetime.now()).phase is not None
        FocusDialog(self, running, self.start_focus, self._stop_timer)

    def open_routine_settings(self) -> None:
        def save(**changes: object) -> None:
            self._update_settings(**changes)
            self.presence.configure(self.settings.away_minutes, self.settings.break_reminder_minutes,
                                    self.settings.water_reminder_minutes)
            self.chatter.set_level(self.settings.chatter)

        RoutineSettingsWindow(self, self.settings, save)

    def open_price_settings(self) -> None:
        def save(**changes: object) -> None:
            self._update_settings(**changes)
            self.check_prices_now()

        PriceSettingsWindow(self, self.settings, save)

    # ----- menu actions -----------------------------------------------------------

    def open_picker(self, startup: bool = False) -> None:
        if self.busy:
            return

        def thumbnail(persona, box):
            path = self.art.image_path("neutral", persona.id, full=False)
            return self.art.load(path, box) if path else None

        def picked(persona_id: str, remember: bool) -> None:
            if startup:
                self._reveal()  # first, so a later error cannot leave the app invisible
            self._update_settings(pick_on_start=not remember)
            if startup or persona_id != self.persona.id:
                self.switch_persona(persona_id)
            if startup:
                self.after(BRIEFING_DELAY_MS, self.brief_today)
                for index, (message, expression) in enumerate(self._held_notices):
                    self.after(HELD_NOTICE_DELAY_MS + index * HELD_NOTICE_GAP_MS, lambda m=message, e=expression: self.say(m, e))
                self._held_notices.clear()
                if self._setup_held:
                    self._setup_held = False
                    self.after(HELD_NOTICE_DELAY_MS, self.open_setup_check)

        try:
            CharacterPicker(self, PERSONAS.values(), self.persona.id, thumbnail, picked, remember=not self.settings.pick_on_start)
        except Exception:  # noqa: BLE001 - start with the last character instead of staying hidden
            self.report_callback_exception(*sys.exc_info())
            if startup:
                picked(self.persona.id, not self.settings.pick_on_start)

    def switch_persona(self, persona_id: str) -> None:
        if self.busy:
            return
        self._update_settings(persona_id=persona_id)
        self.chat.set_hint(self._idle_hint())
        self.expression = "neutral"
        self._render_character()
        self.talk(random.choice(self.persona.greetings), "happy")

    def toggle_sharp(self) -> None:
        on = bool(self.sharp_var.get())
        self._update_settings(sharp_display=on)
        if on:
            self.say("다음에 켤 때부터 선명하게 보여요. 화면 배율이 125%·150%면 그림이 또렷해지는 대신 조금 작아져요.")
        else:
            self.say("다음에 켤 때부터 예전처럼 보여요.")

    def ask_user_name(self) -> None:
        name = simpledialog.askstring("내 이름", "캐릭터가 알고 있을 이름을 입력하세요.", initialvalue=self.settings.user_name, parent=self)
        if name is not None:
            self._update_settings(user_name=name.strip())
            self.say("이름, 기억해 둘게요." if name.strip() else "알겠어요.", "happy")

    def ask_model(self) -> None:
        try:
            installed = OllamaClient(self.settings.ollama_url, timeout=5).list_models()
        except Exception:  # noqa: BLE001 - the list is only a hint
            installed = []
        hint = ", ".join(installed) if installed else "(설치된 모델을 확인하지 못했습니다)"
        model = simpledialog.askstring(
            "AI 모델",
            f"사용할 Ollama 모델 이름\n설치됨: {hint}",
            initialvalue=self.settings.model,
            parent=self,
        )
        if model and model.strip():
            self._update_settings(model=model.strip())
            threading.Thread(target=self._check_model, daemon=True).start()

    def show_log(self) -> None:
        persona_id = self.persona.id
        ConversationLogWindow(self, self.store, self.persona, lambda size, bg: self.art.face(persona_id, size, bg))

    def clear_memory(self) -> None:
        if messagebox.askyesno("기억 지우기", f"{self.persona.name}와의 대화 기록을 모두 지울까요?", parent=self):
            self.store.clear(self.persona.id)
            self.say("...처음 뵙겠습니다?", "surprised")
