from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from src.nuri_assistant.announcements import (
    compose_briefing,
    nag_line,
    price_alert_line,
    reminder_line,
    timer_line,
    until_text,
)
from src.nuri_assistant.companion import get_persona
from src.nuri_assistant.companion import parse_confirmation
from src.nuri_assistant.focus import FocusTimer
from src.nuri_assistant.pricewatch.checker import CheckResult
from src.nuri_assistant.pricewatch.sources import Offer
from src.nuri_assistant.pricewatch.store import Watch
from src.nuri_assistant.schedule.store import Event
from src.nuri_assistant.todo.store import Todo

NOW = datetime(2026, 10, 6, 14, 30)
PERSONA = get_persona("nuri")


def event(title: str, start: datetime, all_day: bool = False) -> Event:
    return Event(1, title, start, all_day, None, False)


class UntilTextTest(unittest.TestCase):
    def test_wording(self) -> None:
        cases = [
            (event("x", NOW, all_day=True), "오늘"),
            (event("x", NOW - timedelta(minutes=5)), "지금"),
            (event("x", NOW + timedelta(minutes=10)), "10분 뒤에"),
            (event("x", NOW + timedelta(hours=1)), "1시간 뒤에"),
            (event("x", NOW + timedelta(minutes=65)), "1시간 5분 뒤에"),
        ]
        for item, expected in cases:
            self.assertEqual(until_text(item, NOW), expected)

    def test_reminder_uses_persona_template(self) -> None:
        line = reminder_line(PERSONA, event("치과", NOW + timedelta(minutes=10)), NOW)
        self.assertEqual(line, PERSONA.reminder.format(when="10분 뒤에", title="치과"))


class NagAndTimerTest(unittest.TestCase):
    def test_nag_kinds(self) -> None:
        todo = Todo(1, "보고서", datetime(2026, 10, 7), True, False)
        self.assertEqual(nag_line(PERSONA, todo, "eve"), (PERSONA.todo_nag.format(title="보고서", when="내일까지"), "thinking"))
        self.assertEqual(nag_line(PERSONA, todo, "day"), (PERSONA.todo_nag.format(title="보고서", when="오늘까지"), "angry"))

    def test_timer_lines(self) -> None:
        timer = FocusTimer()
        timer.start(NOW, 50, 10)
        self.assertEqual(timer_line(PERSONA, timer, "focus_done"), (PERSONA.focus_done.format(minutes=10), "happy"))
        self.assertEqual(timer_line(PERSONA, timer, "break_done"), (PERSONA.break_done.format(minutes=50), "neutral"))
        self.assertEqual(timer_line(PERSONA, timer, "all_done"), (PERSONA.all_done, "happy"))

    def test_price_alert(self) -> None:
        watch = Watch(1, "에어팟", "", None, None, None, "", "", None, None, "")
        result = CheckResult(watch, Offer("에어팟 프로", 299000, "쿠팡", "https://example.com"), True, "new_low")
        self.assertEqual(price_alert_line(PERSONA, result), PERSONA.price_alert.format(title=watch.label, price="299,000원", mall="쿠팡"))


class BriefingTest(unittest.TestCase):
    def test_nothing_to_say(self) -> None:
        self.assertIsNone(compose_briefing(PERSONA, [], [], NOW.date()))

    def test_events_are_capped_at_four(self) -> None:
        events = [event(f"일정{i}", NOW.replace(hour=9 + i)) for i in range(5)] + [event("휴가", NOW, all_day=True)]
        text, headline = compose_briefing(PERSONA, events, [], NOW.date())
        self.assertEqual(headline, PERSONA.briefing.format(count=6))
        lines = text.split("\n")
        self.assertEqual(lines[1:], ["· 09:30 일정0", "· 10:30 일정1", "· 11:30 일정2", "· 12:30 일정3", "· 외 2개"])

    def test_todos_only(self) -> None:
        todos = [Todo(i, f"할일{i}", datetime(2026, 10, 6), True, False) for i in range(4)]
        text, headline = compose_briefing(PERSONA, [], todos, NOW.date())
        self.assertEqual(headline, "오늘 챙겨야 할 일이 있어요.")
        self.assertEqual(text, "오늘 챙겨야 할 일이 있어요.\n할 일: 할일0(오늘), 할일1(오늘), 할일2(오늘) 외 1개")


class ConfirmationTest(unittest.TestCase):
    def test_yes_no_and_chat(self) -> None:
        self.assertIs(parse_confirmation("응!"), True)
        self.assertIs(parse_confirmation(" OK. "), True)
        self.assertIs(parse_confirmation("아니요~"), False)
        self.assertIsNone(parse_confirmation("응 근데 시간 바꿔 줘"))


if __name__ == "__main__":
    unittest.main()
