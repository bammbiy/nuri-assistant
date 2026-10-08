"""The character app's stores, background helpers and model tools, wired together without Tk.

MascotApp owns one Services; keeping the wiring here lets it be built (and tested) headless.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .classic.storage import HistoryStore
from .classic.tools import FileTools, RenameOptions
from .companion import CompanionSettings, ConversationStore, ToolBox
from .focus import FocusTimer, FocusTools
from .paths import HISTORY_DB, MEMORY_DB
from .pricewatch import NaverShopping, PriceChecker, PriceTools, WatchStore
from .schedule import ScheduleStore, ScheduleTools
from .todo import TodoStore, TodoTools


def rename_options(settings: CompanionSettings) -> RenameOptions:
    return RenameOptions(settings.rename_rule, settings.rename_media,
                         tuple(settings.rename_extensions) or RenameOptions.extensions, settings.rename_skip_named)


def price_sources(settings: CompanionSettings) -> list:
    """Search APIs the user has keys for (only Naver Shopping today)."""

    sources = []
    if settings.naver_client_id and settings.naver_client_secret:
        sources.append(NaverShopping(settings.naver_client_id, settings.naver_client_secret))
    return sources


class Services:
    def __init__(self, app_dir: Path, settings: Callable[[], CompanionSettings]) -> None:
        # Settings change at runtime (API keys), so sources are looked up on every check.
        self.price_sources: Callable[[], list] = lambda: price_sources(settings())
        db = app_dir / MEMORY_DB.name
        self.store = ConversationStore(db)
        self.schedule = ScheduleStore(db)
        self.watches = WatchStore(db)
        self.price_checker = PriceChecker(self.watches, self.price_sources)
        self.todos = TodoStore(db)
        self.focus_timer = FocusTimer()
        self.history = HistoryStore(app_dir / HISTORY_DB.name)
        self.toolbox = ToolBox([
            ScheduleTools(self.schedule),
            TodoTools(self.todos),
            PriceTools(self.watches, self.price_checker),
            FocusTools(self.focus_timer),
            FileTools(self.history, lambda: rename_options(settings())),
        ])
