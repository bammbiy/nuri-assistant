"""Start-up readiness check: is Ollama running, is the model installed, is the voice engine up. No Tk."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Step:
    key: str  # "ollama" | "model" | "voice"
    ok: bool
    title: str
    detail: str  # one Korean line: what is wrong and what to do, or what was found
    optional: bool = False


def has_model(installed: list[str], model: str) -> bool:
    """True when ``model`` is installed (a bare name matches its ":latest" tag)."""

    names = set(installed) | {name.removesuffix(":latest") for name in installed}
    return model in names


def check_setup(settings: Any, client: Any, voice_ok: Callable[[], bool] | None = None) -> list[Step]:
    """Run the checks in order. ``client`` needs ``list_models()``; ``voice_ok`` is only used when voice is on."""

    steps: list[Step] = []
    installed: list[str] | None
    try:
        installed = list(client.list_models())
    except Exception:  # noqa: BLE001 - any failure just means "not reachable"
        installed = None
    if installed is None:
        steps.append(Step("ollama", False, "Ollama 실행", "Ollama가 켜져 있지 않아요. 설치했다면 실행해 주세요."))
        steps.append(Step("model", False, f"모델 {settings.model}", "Ollama가 켜지면 확인할 수 있어요"))
    else:
        steps.append(Step("ollama", True, "Ollama 실행", "Ollama가 잘 켜져 있어요."))
        if has_model(installed, settings.model):
            steps.append(Step("model", True, f"모델 {settings.model}", "모델이 설치되어 있어요."))
        else:
            steps.append(Step("model", False, f"모델 {settings.model}", "아직 설치되지 않았어요. 아래 버튼으로 받을 수 있어요(몇 GB라 시간이 걸려요)."))
    if voice_ok is not None and settings.voice_enabled:
        try:
            alive = bool(voice_ok())
        except Exception:  # noqa: BLE001
            alive = False
        steps.append(Step(
            "voice", alive, "음성 엔진",
            "VOICEVOX가 켜져 있어요." if alive else "VOICEVOX가 꺼져 있어요. 없어도 말풍선으로 대화할 수 있어요.",
            optional=True,
        ))
    return steps


def ready(steps: list[Step]) -> bool:
    """Every non-optional step is ok."""

    return all(step.ok for step in steps if not step.optional)
