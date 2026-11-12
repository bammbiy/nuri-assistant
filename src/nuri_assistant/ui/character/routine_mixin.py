"""Reminders, morning briefing, evening wrap-up, idle talk, presence lines, closeness and fortune.

Mixed into ``MascotApp``; relies on its stores, settings, ``events`` queue, ``say``/``talk``
and ``_optional_ok``.
"""

from __future__ import annotations

import random
import sys
import threading
import time
from datetime import datetime, timedelta

from ...announcements import (
    chime_line, compose_briefing, compose_wrapup, holiday_line, level_up_line, nag_line, occasion_line, presence_line,
    reminder_line, with_weather,
)
from ...crashlog import log_exception
from ...fun import fortune_text, holiday_today, occasion_today, today_fortune
from ...presence import idle_seconds
from ...routine import daily_due, hourly_key, parse_clock
from ...weather import Place, WeatherError, fetch_today, weather_line
from ..windows.privacy import PrivacyWindow
from .timing import (
    CHATTER_POLL_MS, GLANCE_GAP_S, GLANCE_MS, LEVEL_UP_DELAY_MS, PRESENCE_POLL_MS, PRIVACY_DELAY_MS, REMINDER_POLL_MS,
    ROUTINE_GAP_S, ROUTINE_POLL_MS, SECOND_LINE_GAP_MS, WRAPUP_WINDOW,
)


class RoutineMixin:
    """Lines the app says on its own schedule (design principle 5)."""

    def _check_reminders(self) -> None:
        try:
            self._remind_due()
        finally:
            self.after(REMINDER_POLL_MS, self._check_reminders)

    def _remind_due(self) -> None:
        if self.state() != "withdrawn" and not self.busy:
            now = datetime.now()
            due = self.schedule.due_reminders(now)
            if due:
                # One per poll so bubbles do not overwrite each other; the rest stay due.
                event = due[0]
                self.schedule.mark_reminded(event.id)
                self.talk(reminder_line(self.persona, event, now), "surprised")
                self.bell()
            elif nags := self.todos.due_nags(now):
                todo, kind = nags[0]
                self.todos.mark_nagged(todo.id, kind)
                self.talk(*nag_line(self.persona, todo, kind))
                self.bell()

    def brief_today(self, force: bool = False) -> None:
        """Once a day (at start-up, or from the set time on) or on request: today's events and weather."""

        now = datetime.now()
        today = now.date().isoformat()
        if not force:
            clock = parse_clock(self.settings.briefing_time)
            due = daily_due(now, clock, self.settings.last_briefing) if clock else self.settings.last_briefing != today
            if not due or self._fullscreen:  # behind a game: _routine_step brings it later
                return
            self._update_settings(last_briefing=today)
        if self.settings.weather_lat is not None and self.settings.weather_lon is not None:
            place = Place(self.settings.weather_city, self.settings.weather_lat, self.settings.weather_lon)
            threading.Thread(target=self._fetch_weather, args=(place, force), daemon=True).start()
        else:
            self._on_briefing(None, force)

    def _fetch_weather(self, place: Place, force: bool) -> None:
        try:
            line = weather_line(place.name, fetch_today(place, datetime.now()))
        except WeatherError:
            line = None  # no weather today; the schedule part of the briefing still comes
        self.events.put(("briefing", line, force))

    def _on_briefing(self, weather: str | None, force: bool) -> None:
        now = datetime.now()
        start = datetime.combine(now.date(), datetime.min.time())
        events = self.schedule.between(start, start + timedelta(days=1))
        urgent = [todo for todo in self.todos.open() if todo.due and todo.due.date() <= now.date()]
        briefing = with_weather(compose_briefing(self.persona, events, urgent, now.date()), weather)
        if briefing is None:
            if force:
                self.say("오늘은 일정도 급한 할 일도 없어요.", "neutral")
            return
        text, headline = briefing
        self.say(text, "happy")
        self.speak(headline)
        self._last_routine_line = time.monotonic()

    def wrap_up(self, force: bool = False) -> None:
        """Evening wrap-up: focus blocks and finished to-dos today, and tomorrow's first event."""

        now = datetime.now()
        if not force:
            self._update_settings(last_wrapup=now.date().isoformat())
        start = datetime.combine(now.date(), datetime.min.time())
        tomorrow = start + timedelta(days=1)
        text, headline = compose_wrapup(self.persona, self.focus_log.summary(start, tomorrow),
                                        self.todos.done_between(start, tomorrow),
                                        self.schedule.between(tomorrow, tomorrow + timedelta(days=1)))
        self.say(text, "happy")
        self.speak(headline)
        self._last_routine_line = time.monotonic()

    def _routine_loop(self) -> None:
        try:
            self._routine_step()
        finally:
            self.after(ROUTINE_POLL_MS, self._routine_loop)

    def _routine_step(self) -> None:
        # Full screen: wait, so the briefing and wrap-up are not used up behind a game.
        if not self._optional_ok():
            return
        now = datetime.now()
        clock = parse_clock(self.settings.briefing_time)
        # One routine line per poll, so a late start does not put the wrap-up over the briefing.
        briefing_due = (daily_due(now, clock, self.settings.last_briefing) if clock
                        else self.settings.last_briefing != now.date().isoformat())
        if briefing_due:
            self.brief_today()
        elif daily_due(now, parse_clock(self.settings.wrapup_time), self.settings.last_wrapup, WRAPUP_WINDOW):
            self.wrap_up()
        elif (self.settings.notify_occasion and self.settings.last_occasion != now.date().isoformat()
              and time.monotonic() - self._last_routine_line >= ROUTINE_GAP_S):
            self._update_settings(last_occasion=now.date().isoformat())
            occasion = occasion_today(now.date(), self.settings.user_birthday, self.settings.first_met)
            holiday = None if occasion else holiday_today(now.date())
            if occasion:
                self.talk(*occasion_line(self.persona, occasion.kind, occasion.days))
            elif holiday:
                self.talk(*holiday_line(self.persona, holiday))
            self._last_routine_line = time.monotonic()
        elif (self.settings.hourly_chime and time.monotonic() - self._last_routine_line >= ROUTINE_GAP_S
              and self.focus_timer.state(now).phase is None):  # not over a focus block
            key = hourly_key(now, self.settings.last_chime)
            if key:
                self._update_settings(last_chime=key)
                self.talk(*chime_line(self.persona, now))
                self._last_routine_line = time.monotonic()

    # ----- idle talk and glances ------------------------------------------------------

    def _chatter_loop(self) -> None:
        try:
            self._chatter_step()
        finally:
            self.after(CHATTER_POLL_MS, self._chatter_loop)

    def _chatter_step(self) -> None:
        if not self._optional_ok() or self.talking or self.chat.focused():
            return
        now = datetime.now()
        if self.chatter.due(now):
            self.talk(random.choice(self.persona.idle_talk), random.choice(("happy", "neutral", "thinking")))
            self.chatter.spoke(now)
        elif time.monotonic() >= self._next_glance and self.expression == "neutral" and not self.settings.light_mode:
            self._next_glance = time.monotonic() + random.uniform(*GLANCE_GAP_S)
            self.set_expression(random.choice(("happy", "thinking", "shy")))
            self._relax_later(GLANCE_MS)

    def _first_privacy_notice(self) -> None:
        if self.state() == "withdrawn":  # still picking a character
            self.after(PRIVACY_DELAY_MS, self._first_privacy_notice)
            return
        PrivacyWindow(self, lambda: self._update_settings(privacy_shown=True))

    # ----- closeness, fortune --------------------------------------------------------

    def gain(self, reason: str) -> None:
        """Closeness points for the current character; a level-up gets its own line after the reply."""

        try:
            level = self.affection.add(self.persona.id, reason, datetime.now())
        except Exception:  # noqa: BLE001 - points are a bonus; never block the chat or the card flow
            log_exception(*sys.exc_info())
            return
        if level:
            self.after(LEVEL_UP_DELAY_MS, lambda persona=self.persona: self._say_level_up(persona, level))

    def _say_level_up(self, persona, level: int) -> None:
        if persona is not self.persona:
            return  # switched characters meanwhile
        if not self.settings.notify_level_up:
            return
        if not self._optional_ok():
            self.after(LEVEL_UP_DELAY_MS, lambda: self._say_level_up(persona, level))
            return
        self.talk(*level_up_line(persona, level))

    def show_closeness(self) -> None:
        pid = self.persona.id
        index, name = self.affection.level(pid)
        nxt = self.affection.next_threshold(pid)
        rest = f" · 다음 단계까지 {nxt - self.affection.points(pid)}점" if nxt is not None else " · 최고 단계예요!"
        self.say(f"{self.persona.name}와의 사이: {name} {self.affection.hearts(pid)}{rest}", "shy" if index else "neutral")

    def tell_fortune(self) -> None:
        self.talk(f"오늘의 운세예요!\n{fortune_text(today_fortune(datetime.now().date(), self.persona.id))}", "happy")

    # ----- presence (Windows: time since the last input only) -----------------------

    def _presence_loop(self) -> None:
        try:
            self._presence_step()
        finally:
            self.after(PRESENCE_POLL_MS, self._presence_loop)

    def _presence_step(self) -> None:
        if not self.settings.presence_enabled:
            return
        idle = idle_seconds()
        if idle is None:
            return
        now = datetime.now()
        focusing = self.focus_timer.state(now).phase == "focus"
        quiet = not self._optional_ok() or focusing
        for index, (kind, minutes) in enumerate(self.presence.update(now, idle, quiet)):
            if kind == "welcome_back" and not self.settings.notify_welcome:
                continue
            line = presence_line(self.persona, kind, minutes)
            self.after(index * SECOND_LINE_GAP_MS, lambda line=line: self.talk(*line))
