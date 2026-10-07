"""Lines the app says on its own: reminders, nags, the morning briefing, timer and price alerts.

These are time-critical, so they are filled from the persona's templates and never go
through the model (CLAUDE.md principle 5). Kept free of Tk so they can be unit-tested.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from .pricewatch.checker import won

if TYPE_CHECKING:
    from .companion.personas import Persona
    from .focus.timer import FocusTimer
    from .pricewatch.checker import CheckResult
    from .schedule.store import Event
    from .todo.store import Todo

BRIEFING_MAX_EVENTS = 4
BRIEFING_MAX_TODOS = 3


def until_text(event: Event, now: datetime) -> str:
    """'10분 뒤에', '1시간 뒤에', '지금', or '오늘' for all-day events."""

    if event.all_day:
        return "오늘"
    minutes = max(round((event.start - now).total_seconds() / 60), 0)
    if minutes == 0:
        return "지금"
    if minutes < 60:
        return f"{minutes}분 뒤에"
    hours, rest = divmod(minutes, 60)
    return f"{hours}시간 {rest}분 뒤에" if rest else f"{hours}시간 뒤에"


def reminder_line(persona: Persona, event: Event, now: datetime) -> str:
    return persona.reminder.format(when=until_text(event, now), title=event.title)


def nag_line(persona: Persona, todo: Todo, kind: str) -> tuple[str, str]:
    """(text, expression) for a todo nag; kind is "eve" (day before) or "day" (due today)."""

    when = "내일까지" if kind == "eve" else "오늘까지"
    return persona.todo_nag.format(title=todo.title, when=when), "angry" if kind == "day" else "thinking"


def compose_briefing(persona: Persona, events: list[Event], urgent: list[Todo], today: date) -> tuple[str, str] | None:
    """(bubble text, spoken headline) for today's briefing, or None when there is nothing to say."""

    if not events and not urgent:
        return None
    parts, headline = [], ""
    if events:
        headline = persona.briefing.format(count=len(events))
        parts.append(headline)
        parts += [f"· {'하루 종일' if e.all_day else e.start.strftime('%H:%M')} {e.title}" for e in events[:BRIEFING_MAX_EVENTS]]
        if len(events) > BRIEFING_MAX_EVENTS:
            parts.append(f"· 외 {len(events) - BRIEFING_MAX_EVENTS}개")
    if urgent:
        if not headline:
            headline = "오늘 챙겨야 할 일이 있어요."
            parts.append(headline)
        parts.append("할 일: " + ", ".join(f"{t.title}({t.d_day(today)})" for t in urgent[:BRIEFING_MAX_TODOS])
                     + (f" 외 {len(urgent) - BRIEFING_MAX_TODOS}개" if len(urgent) > BRIEFING_MAX_TODOS else ""))
    return "\n".join(parts), headline


def timer_line(persona: Persona, timer: FocusTimer, event: str) -> tuple[str, str]:
    """(text, expression) for a focus timer phase change ("focus_done", "break_done", "all_done")."""

    line = {
        "focus_done": lambda: persona.focus_done.format(minutes=timer.break_minutes),
        "break_done": lambda: persona.break_done.format(minutes=timer.focus_minutes),
        "all_done": lambda: persona.all_done,
    }[event]()
    return line, "happy" if event != "break_done" else "neutral"


def price_alert_line(persona: Persona, result: CheckResult) -> str:
    offer = result.offer  # callers announce only results that have an offer
    return persona.price_alert.format(title=result.watch.label, price=won(offer.price), mall=offer.mall)
