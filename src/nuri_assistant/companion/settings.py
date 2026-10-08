from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

from ..classic.core.models import DEFAULT_RULE
from ..classic.core.scanner import DEFAULT_EXTENSIONS
from .llm import DEFAULT_MODEL, DEFAULT_OLLAMA_URL
from .personas import DEFAULT_PERSONA_ID


@dataclass(frozen=True)
class CompanionSettings:
    persona_id: str = DEFAULT_PERSONA_ID
    model: str = DEFAULT_MODEL
    ollama_url: str = DEFAULT_OLLAMA_URL
    user_name: str = ""
    history_limit: int = 20
    # Show the secretary picker every time the app starts.
    pick_on_start: bool = True
    # Date (YYYY-MM-DD) of the last morning briefing, so it runs once a day.
    last_briefing: str = ""
    # Price watching: API keys stay in this local file only.
    naver_client_id: str = ""
    naver_client_secret: str = ""
    price_check_minutes: int = 60
    # Japanese voice through a local VOICEVOX-compatible engine.
    voice_enabled: bool = False
    voice_url: str = "http://127.0.0.1:50021"
    voice_ids: dict = field(default_factory=dict)  # persona id -> engine style id
    # "bust" (upper body, default) or "full" (full body, taller window).
    display_mode: str = "bust"
    # File renaming from chat ("파일 정리 설정" window): name rule, default media code, file types,
    # and whether files already named by the rule are left alone (numbering continues after them).
    rename_rule: str = DEFAULT_RULE
    rename_media: str = ""
    rename_extensions: list = field(default_factory=lambda: list(DEFAULT_EXTENSIONS))
    rename_skip_named: bool = True
    x: int | None = None
    y: int | None = None


def load_settings(path: Path) -> CompanionSettings:
    """Read companion.json; an unreadable file is kept as companion.json.bak, not overwritten later."""

    if not path.exists():
        return CompanionSettings()
    data = None
    try:
        raw = path.read_bytes()
        # Notepad may save with a BOM or in the Korean ANSI code page (cp949).
        for encoding in ("utf-8-sig", "cp949"):
            try:
                data = json.loads(raw.decode(encoding))
                break
            except ValueError:
                continue
    except OSError:
        return CompanionSettings()
    if not isinstance(data, dict):
        _keep_backup(path)
        return CompanionSettings()
    known = {field.name for field in fields(CompanionSettings)}
    return replace(CompanionSettings(), **{key: value for key, value in data.items() if key in known})


def save_settings(path: Path, settings: CompanionSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")


def _keep_backup(path: Path) -> None:
    backup = path.with_name(path.name + ".bak")
    if not backup.exists():
        try:
            backup.write_bytes(path.read_bytes())
        except OSError:
            pass
