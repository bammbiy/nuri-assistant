from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# VOICEVOX and AivisSpeech serve the same HTTP API on different ports.
ENGINES = {
    "VOICEVOX": "http://127.0.0.1:50021",
    "AivisSpeech": "http://127.0.0.1:10101",
}


class VoiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Voice:
    id: int
    speaker: str
    style: str

    @property
    def label(self) -> str:
        return f"{self.speaker} ({self.style})"


Opener = Callable[[Request], Any]


def _default_opener(request: Request) -> Any:
    return urlopen(request, timeout=30)  # noqa: S310 - local TTS engine


class VoicevoxClient:
    """Minimal client for a local VOICEVOX-compatible engine (Japanese text in, WAV out)."""

    def __init__(self, base_url: str = ENGINES["VOICEVOX"], opener: Opener = _default_opener) -> None:
        self.base_url = base_url.rstrip("/")
        self.opener = opener

    def _call(self, method: str, path: str, params: dict[str, Any] | None = None, body: bytes | None = None) -> bytes:
        query = f"?{urlencode(params)}" if params else ""
        request = Request(f"{self.base_url}{path}{query}", data=body, method=method,
                          headers={"Content-Type": "application/json"} if body is not None else {})
        try:
            with self.opener(request) as response:
                return response.read()
        except HTTPError as exc:
            raise VoiceError(f"음성 엔진 오류 ({exc.code})") from exc
        except (URLError, TimeoutError) as exc:
            raise VoiceError(f"음성 엔진({self.base_url})에 연결하지 못했어요. VOICEVOX를 켜 주세요.") from exc

    def voices(self) -> list[Voice]:
        speakers = json.loads(self._call("GET", "/speakers").decode("utf-8"))
        return [
            Voice(int(style["id"]), str(speaker.get("name", "")), str(style.get("name", "")))
            for speaker in speakers
            for style in speaker.get("styles", [])
        ]

    def synthesize(self, text: str, voice_id: int, speed: float = 1.05) -> bytes:
        query = json.loads(self._call("POST", "/audio_query", {"text": text, "speaker": voice_id}).decode("utf-8"))
        query["speedScale"] = speed
        return self._call("POST", "/synthesis", {"speaker": voice_id}, json.dumps(query).encode("utf-8"))
