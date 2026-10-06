from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from src.nuri_assistant.companion import Companion, ConversationStore, OllamaClient, OllamaToolsUnsupported, ToolCall, get_persona
from src.nuri_assistant.schedule import ScheduleStore, ScheduleTools, WhenError, default_remind_at, parse_range, parse_when

# Tuesday afternoon
NOW = datetime(2026, 10, 6, 14, 30)


class ParseWhenTest(unittest.TestCase):
    def check(self, text: str, expected: datetime, all_day: bool = False) -> None:
        when = parse_when(text, NOW)
        self.assertEqual((when.start, when.all_day), (expected, all_day), text)

    def test_relative_days_and_periods(self) -> None:
        self.check("내일 오후 3시", datetime(2026, 10, 7, 15, 0))
        self.check("모레 아침", datetime(2026, 10, 8, 9, 0))
        self.check("내일모레 10시", datetime(2026, 10, 8, 10, 0))
        self.check("오늘 밤 9시", datetime(2026, 10, 6, 21, 0))
        self.check("새벽 2시", datetime(2026, 10, 7, 2, 0))

    def test_hour_without_am_pm_means_afternoon_and_rolls_to_tomorrow_when_past(self) -> None:
        self.check("4시", datetime(2026, 10, 6, 16, 0))
        self.check("1시", datetime(2026, 10, 7, 13, 0))
        self.check("9시", datetime(2026, 10, 7, 9, 0))

    def test_native_korean_numbers_and_half(self) -> None:
        self.check("세 시 반", datetime(2026, 10, 6, 15, 30))
        self.check("오후세시", datetime(2026, 10, 6, 15, 0))
        self.check("한 시간 반 뒤", datetime(2026, 10, 6, 16, 0))

    def test_weekdays_and_weeks(self) -> None:
        self.check("다음 주 화요일 10시", datetime(2026, 10, 13, 10, 0))
        self.check("담주 월요일", datetime(2026, 10, 12), all_day=True)
        self.check("금요일 저녁 7시 반", datetime(2026, 10, 9, 19, 30))
        self.check("이번 주 금요일 오전 11시", datetime(2026, 10, 9, 11, 0))
        self.check("주말", datetime(2026, 10, 10), all_day=True)

    def test_absolute_dates(self) -> None:
        self.check("10월 20일", datetime(2026, 10, 20), all_day=True)
        self.check("10/9 14:00", datetime(2026, 10, 9, 14, 0))
        self.check("2026-12-25", datetime(2026, 12, 25), all_day=True)
        self.check("1월 2일 9시", datetime(2027, 1, 2, 9, 0))
        self.check("15일", datetime(2026, 10, 15), all_day=True)
        self.check("3일", datetime(2026, 11, 3), all_day=True)
        self.check("다음 달 3일", datetime(2026, 11, 3), all_day=True)

    def test_offsets(self) -> None:
        self.check("30분 뒤", datetime(2026, 10, 6, 15, 0))
        self.check("2시간 후", datetime(2026, 10, 6, 16, 30))
        self.check("3일 뒤", datetime(2026, 10, 9), all_day=True)

    def test_midnight(self) -> None:
        self.check("오늘 밤 12시", datetime(2026, 10, 7, 0, 0))
        self.check("자정", datetime(2026, 10, 7, 0, 0))

    def test_rejects_past_and_unknown(self) -> None:
        with self.assertRaises(WhenError):
            parse_when("오늘 오전 9시", NOW)
        with self.assertRaises(WhenError):
            parse_when("회의", NOW)

    def test_ranges(self) -> None:
        self.assertEqual(parse_range("오늘", NOW)[:2], (datetime(2026, 10, 6), datetime(2026, 10, 7)))
        self.assertEqual(parse_range("다음 주", NOW)[:2], (datetime(2026, 10, 12), datetime(2026, 10, 19)))
        start, end, label = parse_range("", NOW)
        self.assertEqual((start, label), (NOW, "앞으로 일주일"))


class StoreAndToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ScheduleStore(Path(self.tmp.name) / "companion.sqlite3")
        self.tools = ScheduleTools(self.store, clock=lambda: NOW)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_add_waits_for_confirmation(self) -> None:
        result = self.tools.execute("add_event", {"title": "팀 회의", "when": "내일 오후 3시"})

        self.assertTrue(result["ok"])
        self.assertEqual(result["when"], "10/7(수) 15:00")
        self.assertEqual(self.store.between(NOW, NOW + timedelta(days=7)), [])
        (action,) = self.tools.take_pending()
        self.assertIn("등록", self.tools.confirm(action))
        (event,) = self.store.between(NOW, NOW + timedelta(days=7))
        self.assertEqual((event.title, event.remind_at), ("팀 회의", datetime(2026, 10, 7, 14, 50)))

    def test_add_with_bad_time_returns_error_for_the_model(self) -> None:
        result = self.tools.execute("add_event", {"title": "회의", "when": "언젠가"})

        self.assertFalse(result["ok"])
        self.assertEqual(self.tools.take_pending(), [])

    def test_custom_reminder_and_all_day(self) -> None:
        self.tools.execute("add_event", {"title": "치과", "when": "내일 10시", "remind_minutes_before": 60})
        self.tools.execute("add_event", {"title": "엄마 생신", "when": "모레"})
        for action in self.tools.take_pending():
            self.tools.confirm(action)
        dentist, birthday = self.store.between(NOW, NOW + timedelta(days=7))
        self.assertEqual(dentist.remind_at, datetime(2026, 10, 7, 9, 0))
        self.assertEqual(birthday.remind_at, datetime(2026, 10, 8, 9, 0))

    def test_list_events(self) -> None:
        self.store.add("회의", datetime(2026, 10, 7, 15, 0), False, None)
        self.store.add("운동", datetime(2026, 10, 7, 19, 0), False, None)
        self.store.add("여행", datetime(2026, 10, 7), True, None)

        result = self.tools.execute("list_events", {"range": "내일"})

        self.assertEqual(result["events"], ["10/7(수) 하루 종일 여행", "10/7(수) 15:00 회의", "10/7(수) 19:00 운동"])

    def test_cancel_needs_a_unique_match_and_confirmation(self) -> None:
        self.store.add("팀 회의", datetime(2026, 10, 7, 15, 0), False, None)
        self.store.add("고객 회의", datetime(2026, 10, 8, 15, 0), False, None)

        ambiguous = self.tools.execute("cancel_event", {"keyword": "회의"})
        self.assertFalse(ambiguous["ok"])
        self.assertEqual(len(ambiguous["candidates"]), 2)

        self.assertTrue(self.tools.execute("cancel_event", {"keyword": "회의", "when": "내일"})["ok"])
        (action,) = self.tools.take_pending()
        self.assertEqual(len(self.store.between(NOW, NOW + timedelta(days=7))), 2)
        self.tools.confirm(action)
        (left,) = self.store.between(NOW, NOW + timedelta(days=7))
        self.assertEqual(left.title, "고객 회의")

    def test_due_reminders_skip_long_missed_ones(self) -> None:
        soon = self.store.add("회의", datetime(2026, 10, 6, 14, 40), False, datetime(2026, 10, 6, 14, 30))
        self.store.add("어제 놓친 알림", datetime(2026, 10, 5, 15, 0), False, datetime(2026, 10, 5, 14, 50))

        self.assertEqual([e.id for e in self.store.due_reminders(NOW)], [soon.id])
        self.store.mark_reminded(soon.id)
        self.assertEqual(self.store.due_reminders(NOW), [])

    def test_default_remind_at(self) -> None:
        self.assertEqual(default_remind_at(NOW + timedelta(minutes=5), False, NOW), NOW)
        self.assertIsNone(default_remind_at(datetime(2026, 10, 6), True, NOW))


class ToolLoopClient:
    """Calls add_event first, then answers after seeing the tool result."""

    def __init__(self) -> None:
        self.requests: list[tuple[list, object]] = []

    def chat_stream(self, _model, messages, options=None, tools=None):
        self.requests.append(([dict(m) for m in messages], tools))
        if messages[-1]["role"] == "user":
            yield ToolCall("add_event", {"title": "치과", "when": "내일 오후 3시"})
        else:
            yield "[happy] 내일 3시 치과 맞죠? 아래에서 확인해 주세요!"


class NoToolsClient:
    def __init__(self) -> None:
        self.tools_seen: list[object] = []

    def chat_stream(self, _model, messages, options=None, tools=None):
        self.tools_seen.append(tools)
        if tools:
            raise OllamaToolsUnsupported("model does not support tools")
        yield "[sad] 지금 모델로는 일정을 못 다뤄요."


class CompanionToolLoopTest(unittest.TestCase):
    def test_tool_round_trip_returns_pending_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "companion.sqlite3"
            tools = ScheduleTools(ScheduleStore(db), clock=lambda: NOW)
            client = ToolLoopClient()
            companion = Companion(get_persona("nuri"), client, ConversationStore(db), "qwen3:8b", clock=lambda: NOW, tools=tools)

            reply = companion.reply("내일 오후 3시에 치과 잡아줘")

            self.assertEqual(reply.text, "내일 3시 치과 맞죠? 아래에서 확인해 주세요!")
            (action,) = reply.actions
            self.assertEqual((action.kind, action.title, action.when), ("add", "치과", "10/7(수) 15:00"))
            second_messages, sent_tools = client.requests[1]
            self.assertEqual(second_messages[-1]["role"], "tool")
            self.assertTrue(json.loads(second_messages[-1]["content"])["ok"])
            self.assertTrue(sent_tools)
            self.assertIn("도구", client.requests[0][0][0]["content"])

    def test_model_without_tools_falls_back_to_chat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "companion.sqlite3"
            client = NoToolsClient()
            companion = Companion(get_persona("nuri"), client, ConversationStore(db), "gemma", tools=ScheduleTools(ScheduleStore(db)))

            reply = companion.reply("일정 잡아줘")

            self.assertEqual(reply.text, "지금 모델로는 일정을 못 다뤄요.")
            self.assertEqual(client.tools_seen[-1], None)
            self.assertFalse(companion.tools_supported)


class OllamaToolCallTest(unittest.TestCase):
    def test_parses_tool_calls_and_sends_tools(self) -> None:
        lines = [
            {"message": {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "list_events", "arguments": {"range": "오늘"}}},
                {"function": {"name": "add_event", "arguments": "{\"title\": \"회의\", \"when\": \"내일\"}"}},
            ]}, "done": False},
            {"message": {"role": "assistant", "content": ""}, "done": True},
        ]

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def __iter__(self):
                return iter(json.dumps(line, ensure_ascii=False).encode("utf-8") + b"\n" for line in lines)

        with patch("src.nuri_assistant.companion.llm.urlopen", return_value=Response()) as urlopen:
            items = list(OllamaClient().chat_stream("qwen3:8b", [], tools=[{"type": "function"}]))

        payload = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["tools"], [{"type": "function"}])
        self.assertEqual(items, [ToolCall("list_events", {"range": "오늘"}), ToolCall("add_event", {"title": "회의", "when": "내일"})])


if __name__ == "__main__":
    unittest.main()
