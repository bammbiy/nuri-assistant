"""Where the app keeps its files. User data lives in ~/.nuri-assistant; art ships in the repo.

MascotApp accepts another app_dir (tests and UI checks pass a temp folder), so callers that
honour that take only the file names from here and join them onto their own folder.
"""
from __future__ import annotations

from pathlib import Path

APP_DIR = Path.home() / ".nuri-assistant"
SETTINGS_PATH = APP_DIR / "companion.json"
MEMORY_DB = APP_DIR / "companion.sqlite3"  # conversations, schedule, todos, price watches
HISTORY_DB = APP_DIR / "history.sqlite3"  # file-rename history of the classic tool
PROFILES_PATH = APP_DIR / "profiles.json"
ERROR_LOG = APP_DIR / "error.log"
USER_CHARACTERS = APP_DIR / "characters"  # personal art, preferred over the bundled frames

ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets" / "characters"
FONTS_DIR = ASSETS_DIR.parent / "fonts"  # bundled UI font (NanumSquareRound, OFL)
