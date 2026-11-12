"""Opt-in PC watching: Downloads file count and copied text, turned into confirm cards.

Mixed into ``MascotApp``; relies on its settings, tool box, ``pending_actions`` and
``_show_next_card``.
"""

from __future__ import annotations

import hashlib
import time
import tkinter as tk
from datetime import datetime

from ...announcements import clipboard_line, downloads_line
from ...classic.core import rule_pattern
from ...classic.tools import resolve_folder
from ...pcwatch import count_waiting, suggest
from ...services import rename_options
from .timing import CLIPBOARD_GAP_S, CLIPBOARD_POLL_MS, DAY_WORDS_ONLY, DOWNLOADS_POLL_MS


class WatchMixin:
    """Opt-in Downloads and clipboard suggestions."""

    # ----- opt-in PC watching (file names in Downloads; copied text, never stored) ---

    def _downloads_loop(self) -> None:
        try:
            self._downloads_step()
        finally:
            self.after(DOWNLOADS_POLL_MS, self._downloads_loop)

    def _downloads_step(self) -> None:
        if not self.settings.downloads_watch or not self._optional_ok():
            return
        folder = resolve_folder("다운로드")
        if folder is None:
            return
        options = rename_options(self.settings)
        named = rule_pattern(options.rule) if options.skip_named else None
        waiting = count_waiting(folder, options.extensions, named)
        now = datetime.now()
        self.downloads_nudge.threshold = self.settings.downloads_threshold
        if self.settings.last_downloads_nudge == now.date().isoformat() or not self.downloads_nudge.due(now, waiting):
            return
        self.downloads_nudge.mark(now)
        self._update_settings(last_downloads_nudge=now.date().isoformat())
        result = self.toolbox.execute("rename_files", {"folder": "다운로드", "request": ""})
        self.talk(downloads_line(waiting, bool(result.get("ok"))), "thinking")
        self._show_tool_cards()

    def _clipboard_loop(self) -> None:
        try:
            self._clipboard_step()
        finally:
            self.after(CLIPBOARD_POLL_MS, self._clipboard_loop)

    def _clipboard_step(self) -> None:
        if not self.settings.clipboard_watch:
            return
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return  # empty clipboard or not text
        digest = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()  # only a fingerprint is kept
        if digest == self._last_clip:
            return
        now = time.monotonic()
        if not self._optional_ok() or now - self._last_clip_offer < CLIPBOARD_GAP_S:
            return  # looked at again on a later poll
        self._last_clip = digest
        found = suggest(text, datetime.now())
        del text
        if found is None or (found.kind == "event" and found.when_text in DAY_WORDS_ONLY):
            return  # "오늘 날씨 좋다" is not an appointment
        self._last_clip_offer = now
        if found.kind == "price":
            result = self.toolbox.execute("add_price_watch", {"url": found.url})
        else:
            result = self.toolbox.execute("add_event", {"title": found.title, "when": found.when_text})
        if result.get("ok"):
            self.say(clipboard_line(found.kind, found.title, found.when_text), "thinking")
            self._show_tool_cards()

    def _show_tool_cards(self) -> None:
        """Show confirm cards for actions a tool queued outside a chat turn (Downloads, clipboard)."""

        actions = self.toolbox.take_pending()
        if actions:
            self.pending_actions = list(actions)
            self._show_next_card()
