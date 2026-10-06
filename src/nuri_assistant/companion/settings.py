from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

from .llm import DEFAULT_MODEL, DEFAULT_OLLAMA_URL
from .personas import DEFAULT_PERSONA_ID


@dataclass(frozen=True)
class CompanionSettings:
    persona_id: str = DEFAULT_PERSONA_ID
    model: str = DEFAULT_MODEL
    ollama_url: str = DEFAULT_OLLAMA_URL
    user_name: str = ""
    history_limit: int = 20
    x: int | None = None
    y: int | None = None


def load_settings(path: Path) -> CompanionSettings:
    if not path.exists():
        return CompanionSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return CompanionSettings()
    known = {field.name for field in fields(CompanionSettings)}
    return replace(CompanionSettings(), **{key: value for key, value in data.items() if key in known})


def save_settings(path: Path, settings: CompanionSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
