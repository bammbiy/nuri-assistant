from __future__ import annotations

import json
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
# Fits in 8GB VRAM (RTX 3060 Ti) at the default 4-bit quantization.
DEFAULT_MODEL = "qwen3:8b"


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    """Minimal client for a local Ollama server. Nothing leaves the machine."""

    def __init__(self, base_url: str = DEFAULT_OLLAMA_URL, timeout: float = 180) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def list_models(self) -> list[str]:
        data = json.loads(self._open("GET", "/api/tags").read().decode("utf-8"))
        return sorted(str(model.get("name", "")) for model in data.get("models", []) if model.get("name"))

    def chat_stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        options: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            # Reasoning models (qwen3 etc.) would otherwise think for seconds before each reply.
            "think": False,
            "keep_alive": "30m",
            "options": {"temperature": 0.8, "num_ctx": 4096, **(options or {})},
        }
        try:
            response = self._open("POST", "/api/chat", payload)
        except OllamaError as exc:
            if "think" not in str(exc).lower():
                raise
            # Models without thinking support may reject the flag; retry without it.
            payload.pop("think")
            response = self._open("POST", "/api/chat", payload)

        with response:
            for line in response:
                if not line.strip():
                    continue
                event = json.loads(line.decode("utf-8"))
                if event.get("error"):
                    raise OllamaError(str(event["error"]))
                content = event.get("message", {}).get("content", "")
                if content:
                    yield content
                if event.get("done"):
                    return

    def _open(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            return urlopen(request, timeout=self.timeout)  # noqa: S310 - user-configured local Ollama URL
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                detail = str(json.loads(detail).get("error", detail))
            except (ValueError, AttributeError):
                pass
            if exc.code == 404 and payload is not None:
                model = payload.get("model", "")
                raise OllamaError(f"'{model}' 모델이 설치되어 있지 않습니다. 터미널에서 `ollama pull {model}`을 실행하세요.") from exc
            raise OllamaError(f"Ollama 요청 실패 ({exc.code}): {detail[:300]}") from exc
        except URLError as exc:
            raise OllamaError(
                f"Ollama({self.base_url})에 연결하지 못했습니다. Ollama가 실행 중인지 확인하세요."
            ) from exc
