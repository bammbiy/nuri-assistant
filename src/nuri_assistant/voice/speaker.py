from __future__ import annotations

import threading
from typing import Callable

from .player import play_wav
from .voicevox import VoiceError, VoicevoxClient


class VoiceSpeaker:
    """Speaks lines on a background thread; a newer line makes older pending ones stale.

    Japanese text is synthesized as-is. Korean-only lines (app messages) go through
    `translate` first, which uses the local model.
    """

    def __init__(
        self,
        client: Callable[[], VoicevoxClient],
        translate: Callable[[str], str],
        on_start: Callable[[], None] = lambda: None,
        on_end: Callable[[], None] = lambda: None,
        on_error: Callable[[str], None] = lambda _message: None,
        player: Callable[[bytes], bool] = play_wav,
    ) -> None:
        self.client = client
        self.translate = translate
        self.on_start, self.on_end, self.on_error = on_start, on_end, on_error
        self.player = player
        self._generation = 0
        self._lock = threading.Lock()  # one line plays at a time

    def speak(self, voice_id: int, japanese: str = "", korean: str = "") -> threading.Thread:
        self._generation += 1
        generation = self._generation
        thread = threading.Thread(target=self._run, args=(generation, voice_id, japanese, korean), daemon=True)
        thread.start()
        return thread

    def _run(self, generation: int, voice_id: int, japanese: str, korean: str) -> None:
        try:
            text = japanese.strip() or (self.translate(korean) if korean.strip() else "")
            if not text or generation != self._generation:
                return
            audio = self.client().synthesize(text, voice_id)
        except VoiceError as exc:
            self.on_error(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - a failed translation must never break the chat
            self.on_error(f"음성을 만들지 못했어요: {exc}")
            return
        with self._lock:
            if generation != self._generation:
                return
            self.on_start()
            try:
                self.player(audio)
            finally:
                self.on_end()
