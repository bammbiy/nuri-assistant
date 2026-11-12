"""Calendar import: periodic background sync of iCal sources and the settings window.

Mixed into ``MascotApp``; relies on its ``schedule`` store, ``settings``, ``events`` queue and ``_update_settings``.
"""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime

from ...schedule import CalendarError, sync_calendars
from ..windows.calendar_settings import CalendarSettingsWindow
from .timing import CALENDAR_POLL_MS


class CalendarMixin:
    """Read-only calendar sync."""

    def _calendar_loop(self) -> None:
        try:
            self._calendar_step()
        finally:
            self.after(CALENDAR_POLL_MS, self._calendar_loop)

    def _calendar_step(self) -> None:
        """Sync on a worker thread; failures are ignored silently (no bubble for periodic syncs)."""

        urls = list(self.settings.calendar_urls)
        if self._calendar_syncing or not urls:
            return
        self._calendar_syncing = True

        def work() -> None:
            try:
                sync_calendars(self.schedule, urls, datetime.now())
            except (CalendarError, OSError, ValueError):
                pass
            finally:
                self.events.put(("calendar_done",))

        threading.Thread(target=work, daemon=True).start()

    def _on_calendar_done(self) -> None:
        self._calendar_syncing = False

    def open_calendar_settings(self) -> None:
        window = self._calendar_window
        try:
            if window is not None and window.winfo_exists():
                window.deiconify()
                window.lift()
                return
        except tk.TclError:
            pass
        self._calendar_window = CalendarSettingsWindow(
            self, list(self.settings.calendar_urls), self._save_calendar_urls, self._sync_calendars_now)

    def _sync_calendars_now(self, urls: list[str]) -> int:
        """Called on the window's worker thread; raises CalendarError for the window to show."""

        return sync_calendars(self.schedule, urls, datetime.now())

    def _save_calendar_urls(self, urls: list[str]) -> None:
        self._update_settings(calendar_urls=list(urls))
        if urls:
            self._calendar_step()
        else:
            self.schedule.clear_imported("ical")
