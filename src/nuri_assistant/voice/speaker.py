from __future__ import annotations

import queue
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

    def stream(self, voice_id: int) -> "VoiceStream":
        """Start a line that is spoken part by part as the parts arrive."""

        self._generation += 1
        return VoiceStream(self, self._generation, voice_id)

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


_DONE = object()


class VoiceStream:
    """Japanese parts spoken in order: part n+1 is synthesized while part n plays."""

    def __init__(self, speaker: VoiceSpeaker, generation: int, voice_id: int) -> None:
        self._speaker = speaker
        self._generation = generation
        self._voice_id = voice_id
        self._texts: queue.Queue = queue.Queue()
        self._audio: queue.Queue = queue.Queue()
        self._count = 0
        self._count_lock = threading.Lock()
        self._closed = False
        self._synth_thread = threading.Thread(target=self._synthesize_loop, daemon=True)
        self._play_thread = threading.Thread(target=self._play_loop, daemon=True)
        self._synth_thread.start()
        self._play_thread.start()

    @property
    def count(self) -> int:
        return self._count

    @property
    def stale(self) -> bool:
        return self._generation != self._speaker._generation

    def add(self, japanese: str) -> None:
        text = japanese.strip()
        if not text:
            return
        with self._count_lock:
            if self._closed:
                return
            self._count += 1
            self._texts.put(text)

    def close(self) -> None:
        with self._count_lock:
            if self._closed:
                return
            self._closed = True
            self._texts.put(_DONE)

    def join(self, timeout: float | None = None) -> None:
        self._synth_thread.join(timeout)
        self._play_thread.join(timeout)

    def _synthesize_loop(self) -> None:
        speaker = self._speaker
        try:
            while True:
                text = self._texts.get()
                if text is _DONE or self.stale:
                    return
                try:
                    audio = speaker.client().synthesize(text, self._voice_id)
                except VoiceError as exc:
                    speaker.on_error(str(exc))
                    return
                except Exception as exc:  # noqa: BLE001
                    speaker.on_error(f"음성을 만들지 못했어요: {exc}")
                    return
                self._audio.put(audio)
        finally:
            self._audio.put(_DONE)

    def _play_loop(self) -> None:
        # on_start once before the first part and on_end once after the last, so the mouth keeps
        # moving across the short gaps while the next sentence is synthesized.
        speaker, started = self._speaker, False
        try:
            while True:
                audio = self._audio.get()
                if audio is _DONE:
                    return
                with speaker._lock:
                    if self.stale:
                        continue
                    if not started:
                        started = True
                        speaker.on_start()
                    speaker.player(audio)
        finally:
            if started:
                speaker.on_end()
