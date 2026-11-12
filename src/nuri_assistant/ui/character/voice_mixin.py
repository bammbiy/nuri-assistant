"""Speaking lines aloud through VOICEVOX and the voice settings window.

Mixed into ``MascotApp``; relies on its ``speaker``, ``companion``, settings and ``say``.
"""

from __future__ import annotations

import random

from ...voice import VoiceSpeaker, VoicevoxClient
from ..windows.voice_settings import VoiceSettingsWindow


class VoiceMixin:
    """Bubble plus voice (``talk``) and the voice helpers."""

    # ----- voice ----------------------------------------------------------------------

    def talk(self, text: str, expression: str | None = None) -> None:
        """Say a line in the bubble and, when voice is on, out loud."""

        self.say(text, expression)
        self.speak(text)

    def speak(self, text: str, japanese: str = "") -> None:
        if not self._voice_on() or not (text.strip() or japanese.strip()):
            return
        self.voice.speak(self._voice_id(), japanese=japanese, korean="" if japanese else text)

    def _voice_id(self) -> int:
        return self.settings.voice_ids.get(self.persona.id, self.persona.voice_id)

    def _to_japanese(self, text: str) -> str:
        key = f"{self.persona.id}:{text}"
        if key not in self._ja_cache:
            self._ja_cache[key] = self.companion.to_japanese(text)
        return self._ja_cache[key]

    def open_voice_settings(self) -> None:
        def preview(url: str, voice_id: int) -> None:
            speaker = VoiceSpeaker(
                client=lambda: VoicevoxClient(url), translate=self._to_japanese,
                on_start=lambda: self.events.put(("voice", True)), on_end=lambda: self.events.put(("voice", False)),
                on_error=lambda message: self.events.put(("notice", message, "sad")),
            )
            line = random.choice(self.persona.greetings)
            self.say(line, "happy")
            speaker.speak(voice_id, korean=line)

        def save(**changes: object) -> None:
            self._voice_error_shown = False
            self._update_settings(**changes)
            if self.settings.voice_enabled and self.settings.light_mode:
                self.say("가벼운 모드라 지금은 목소리를 내지 않아요. AI 설정에서 끌 수 있어요.", "neutral")

        VoiceSettingsWindow(self, self.settings, self.persona, save, preview)
