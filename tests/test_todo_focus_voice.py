from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import URLError

from src.nuri_assistant.companion import Companion, ConversationStore, ReplyParser, get_persona
from src.nuri_assistant.focus import FocusLog, FocusTimer, FocusTools
from src.nuri_assistant.todo import TodoStore, TodoTools
from src.nuri_assistant.voice import VoiceError, VoiceSpeaker, VoicevoxClient

NOW = datetime(2026, 10, 6, 14, 30)  # Tuesday


class TodoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = TodoStore(Path(self.tmp.name) / "companion.sqlite3")
        self.tools = TodoTools(self.store, clock=lambda: NOW)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_add_with_due_needs_confirmation(self) -> None:
        result = self.tools.execute("add_todo", {"title": "보고서 제출", "due": "금요일까지"})

        self.assertEqual(result["due"], "10/9(금)까지")
        self.assertEqual(self.store.open(), [])
        (action,) = self.tools.take_pending()
        self.assertEqual(action.heading, "할 일 추가")
        self.tools.confirm(action)
        (todo,) = self.store.open()
        self.assertEqual((todo.title, todo.due, todo.d_day(NOW.date())), ("보고서 제출", datetime(2026, 10, 9), "D-3"))

    def test_bad_due_is_reported(self) -> None:
        self.assertFalse(self.tools.execute("add_todo", {"title": "x", "due": "언젠가"})["ok"])

    def test_complete_and_delete(self) -> None:
        self.store.add("장보기")
        self.store.add("운동 루틴 짜기")
        self.tools.execute("complete_todo", {"keyword": "장보기"})
        self.tools.confirm(self.tools.take_pending()[0])
        self.assertEqual([t.title for t in self.store.open()], ["운동 루틴 짜기"])
        self.assertEqual([t.title for t in self.store.recently_done()], ["장보기"])
        self.tools.execute("delete_todo", {"keyword": "운동"})
        self.tools.confirm(self.tools.take_pending()[0])
        self.assertEqual(self.store.open(), [])

    def test_open_orders_by_due_with_undated_last(self) -> None:
        self.store.add("기한 없음")
        self.store.add("나중", datetime(2026, 10, 20))
        self.store.add("먼저", datetime(2026, 10, 7))
        self.assertEqual([t.title for t in self.store.open()], ["먼저", "나중", "기한 없음"])

    def test_nags_eve_and_day_once(self) -> None:
        report = self.store.add("보고서", datetime(2026, 10, 7))
        self.assertEqual(self.store.due_nags(NOW), [])  # 14:30, before the 19:00 evening nag
        evening = NOW.replace(hour=19, minute=5)
        self.assertEqual(self.store.due_nags(evening), [(report, "eve")])
        self.store.mark_nagged(report.id, "eve")
        self.assertEqual(self.store.due_nags(evening), [])
        morning = datetime(2026, 10, 7, 9, 0)
        self.assertEqual(self.store.due_nags(morning), [(report, "day")])
        self.store.set_done(report.id)
        self.assertEqual(self.store.due_nags(morning), [])


class FocusTimerTest(unittest.TestCase):
    def run_minutes(self, timer: FocusTimer, start: datetime, minutes: int) -> list[tuple[int, str]]:
        events = []
        for minute in range(minutes + 1):
            events += [(minute, event) for event in timer.tick(start + timedelta(minutes=minute))]
        return events

    def test_cycles_with_breaks(self) -> None:
        timer = FocusTimer()
        timer.start(NOW, 25, 5, 2)
        self.assertEqual(self.run_minutes(timer, NOW, 70),
                         [(25, "focus_done"), (30, "break_done"), (55, "focus_done"), (60, "all_done")])

    def test_without_break_and_stop(self) -> None:
        timer = FocusTimer()
        timer.start(NOW, 10, 0, 1)
        self.assertEqual(timer.state(NOW + timedelta(minutes=3)).clock, "07:00")
        self.assertTrue(timer.stop())
        self.assertEqual(self.run_minutes(timer, NOW, 20), [])

    def test_tools(self) -> None:
        tools = FocusTools(FocusTimer(), clock=lambda: NOW)
        self.assertEqual(tools.execute("start_focus_timer", {"focus_minutes": 50, "break_minutes": 10})["focus_minutes"], 50)
        self.assertEqual(tools.execute("focus_timer_status", {})["remaining"], "50:00")
        self.assertEqual(tools.execute("stop_focus_timer", {})["status"], "멈춤")
        self.assertEqual(tools.take_pending(), [])


class FocusFinishedTest(unittest.TestCase):
    def test_cycles_with_breaks_each_once(self) -> None:
        timer = FocusTimer()
        timer.start(NOW, 25, 5, 2)
        timer.tick(NOW + timedelta(minutes=24))
        self.assertEqual(timer.take_finished(), [])
        timer.tick(NOW + timedelta(minutes=25))
        self.assertEqual(timer.take_finished(), [25])
        self.assertEqual(timer.take_finished(), [])
        timer.tick(NOW + timedelta(minutes=60))  # break, second focus and its break all passed
        self.assertEqual(timer.take_finished(), [25])

    def test_no_break_and_several_cycles_in_one_tick(self) -> None:
        timer = FocusTimer()
        timer.start(NOW, 10, 0, 3)
        timer.tick(NOW + timedelta(minutes=45))
        self.assertEqual(timer.take_finished(), [10, 10, 10])
        self.assertIsNone(timer.phase)

    def test_stop_mid_focus_records_nothing(self) -> None:
        timer = FocusTimer()
        timer.start(NOW, 25, 5, 1)
        timer.tick(NOW + timedelta(minutes=10))
        timer.stop()
        timer.tick(NOW + timedelta(minutes=60))
        self.assertEqual(timer.take_finished(), [])


class FocusLogAndDoneTest(unittest.TestCase):
    def test_summary_half_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = FocusLog(Path(tmp) / "c.sqlite3")
            day = datetime(2026, 10, 6)
            self.assertEqual(log.summary(day, day + timedelta(days=1)), (0, 0))
            log.add(day, 25)  # start is included
            log.add(day.replace(hour=15), 50)
            log.add(day + timedelta(days=1), 30)  # end is excluded
            log.add(day - timedelta(seconds=1), 40)
            self.assertEqual(log.summary(day, day + timedelta(days=1)), (2, 75))

    def test_done_between(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = TodoStore(Path(tmp) / "c.sqlite3")
            first, second, third, open_one = (store.add(name) for name in ["a", "b", "c", "d"])
            stamps = {first.id: "2026-10-06T18:00:00", second.id: "2026-10-06T09:00:00", third.id: "2026-10-07T00:00:00"}
            for todo_id, stamp in stamps.items():
                store.set_done(todo_id)
                with store._connect() as conn:
                    conn.execute("UPDATE todos SET done_at = ? WHERE id = ?", (stamp, todo_id))
            result = store.done_between(datetime(2026, 10, 6), datetime(2026, 10, 7))
            self.assertEqual([t.title for t in result], ["b", "a"])
            self.assertNotIn(open_one.id, [t.id for t in result])


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class VoiceTest(unittest.TestCase):
    def test_voicevox_query_then_synthesis(self) -> None:
        calls = []

        def opener(request):
            calls.append((request.get_method(), request.full_url, request.data))
            if "/audio_query" in request.full_url:
                return FakeResponse(json.dumps({"speedScale": 1.0, "accent_phrases": []}).encode())
            if "/speakers" in request.full_url:
                return FakeResponse(json.dumps([{"name": "春日部つむぎ", "styles": [{"name": "ノーマル", "id": 8}]}]).encode())
            return FakeResponse(b"RIFFwav")

        client = VoicevoxClient(opener=opener)

        self.assertEqual(client.synthesize("こんにちは", 8), b"RIFFwav")
        self.assertIn("/audio_query?text=%E3%81%93", calls[0][1])
        self.assertEqual(json.loads(calls[1][2])["speedScale"], 1.05)
        self.assertEqual(client.voices()[0].label, "春日部つむぎ (ノーマル)")

    def test_engine_down_is_friendly(self) -> None:
        def opener(request):
            raise URLError("refused")

        with self.assertRaisesRegex(VoiceError, "VOICEVOX"):
            VoicevoxClient(opener=opener).voices()

    def test_speaker_translates_korean_and_plays(self) -> None:
        played, events = [], []

        class Client:
            def synthesize(self, text, voice_id):
                return f"{voice_id}:{text}".encode()

        speaker = VoiceSpeaker(lambda: Client(), translate=lambda ko: "日本語:" + ko,
                               on_start=lambda: events.append("start"), on_end=lambda: events.append("end"),
                               player=lambda audio: played.append(audio) or True)
        speaker.speak(8, korean="안녕").join(2)
        speaker.speak(6, japanese="ふん！").join(2)

        self.assertEqual(played, ["8:日本語:안녕".encode(), "6:ふん！".encode()])
        self.assertEqual(events, ["start", "end", "start", "end"])

    def test_newer_line_cancels_older_one(self) -> None:
        played = []
        gate = threading.Event()

        def slow_translate(ko):
            gate.wait(2)
            return "古い"

        class Client:
            def synthesize(self, text, voice_id):
                return text.encode()

        speaker = VoiceSpeaker(lambda: Client(), translate=slow_translate, player=lambda audio: played.append(audio) or True)
        old = speaker.speak(8, korean="옛날")
        new = speaker.speak(8, japanese="新しい")
        new.join(2)
        gate.set()
        old.join(2)
        self.assertEqual(played, ["新しい".encode()])


class JapaneseLineTest(unittest.TestCase):
    def test_parser_hides_japanese_from_bubble(self) -> None:
        parser = ReplyParser()
        shown = [parser.feed(chunk) for chunk in ["[happy] 좋아! ", "<j", "a>よし", "、やろう！</", "ja>"]]

        self.assertEqual(set(shown), {"좋아!"})
        self.assertEqual(parser.voice, "よし、やろう！")

    def test_companion_returns_voice_and_prompts_for_it(self) -> None:
        class Client:
            def __init__(self):
                self.messages = []

            def chat_stream(self, _model, messages, options=None, tools=None):
                self.messages.append(messages)
                yield "[shy] 고, 고마워요 <ja>あ、ありがとうございます</ja>"

        with tempfile.TemporaryDirectory() as tmp:
            client = Client()
            companion = Companion(get_persona("nuri"), client, ConversationStore(Path(tmp) / "c.sqlite3"), "m", voice=True)
            reply = companion.reply("고마워")

            self.assertEqual((reply.text, reply.voice), ("고, 고마워요", "あ、ありがとうございます"))
            self.assertIn("<ja>", client.messages[0][0]["content"])
            self.assertEqual(companion.store.recent("nuri")[-1]["content"], "[shy] 고, 고마워요")


class VoiceStreamingTest(unittest.TestCase):
    def test_take_voice_char_by_char(self) -> None:
        parser = ReplyParser()
        got: list[str] = []
        for ch in "[happy] 좋아! <ja>よし。一緒にやろう！」ね</ja>":
            parser.feed(ch)
            got.extend(parser.take_voice())
        self.assertEqual(got, ["よし。", "一緒にやろう！」"])
        self.assertEqual(parser.take_voice(final=True), ["ね"])
        self.assertEqual(parser.take_voice(final=True), [])

    def test_take_voice_never_leaks_partial_tags(self) -> None:
        parser = ReplyParser()
        for ch in "<ja>あ</":
            parser.feed(ch)
            self.assertEqual(parser.take_voice(), [])
        self.assertEqual(parser.take_voice(final=True), ["あ"])

    def test_take_voice_open_block_and_two_blocks(self) -> None:
        parser = ReplyParser()
        parser.feed("네 <ja>はい。いいよ")
        self.assertEqual(parser.take_voice(), ["はい。"])
        parser.feed("</ja> 그리고 <ja>またね！</ja>")
        self.assertEqual(parser.take_voice(), ["いいよ"])
        self.assertEqual(parser.take_voice(final=True), ["またね！"])

    def test_take_voice_without_ja(self) -> None:
        parser = ReplyParser()
        parser.feed("[happy] 안녕하세요.")
        self.assertEqual(parser.take_voice(final=True), [])

    def test_companion_reply_calls_on_voice_and_passes_options(self) -> None:
        seen = []

        class Client:
            def chat_stream(self, _model, messages, options=None, tools=None):
                seen.append(options)
                for ch in "[happy] 좋아 <ja>よし。いこう！</ja>":
                    yield ch

        voices: list[str] = []

        def on_voice(text: str) -> None:
            voices.append(text)
            raise RuntimeError("ignored")

        with tempfile.TemporaryDirectory() as tmp:
            companion = Companion(get_persona("nuri"), Client(), ConversationStore(Path(tmp) / "c.sqlite3"), "m",
                                  voice=True, options={"num_predict": 7})
            reply = companion.reply("go", on_voice=on_voice)
            companion.to_japanese("x")
        self.assertEqual(voices, ["よし。", "いこう！"])
        self.assertEqual(reply.text, "좋아")
        self.assertEqual(seen, [{"num_predict": 7}, {"num_predict": 7}])

    def _speaker(self, played, events=None, fail_on=None):
        class Client:
            def synthesize(self, text, voice_id):
                if text == fail_on:
                    raise VoiceError("boom")
                return text.encode()

        return VoiceSpeaker(lambda: Client(), translate=lambda ko: ko,
                            on_start=lambda: events is not None and events.append("start"),
                            on_end=lambda: events is not None and events.append("end"),
                            on_error=lambda m: events is not None and events.append("error"),
                            player=lambda audio: played.append(audio) or True)

    def test_stream_plays_in_order(self) -> None:
        played: list[bytes] = []
        events: list[str] = []
        stream = self._speaker(played, events).stream(1)
        stream.add("a")
        stream.add(" ")
        stream.add("b")
        stream.close()
        stream.join(5)
        self.assertEqual(played, [b"a", b"b"])
        self.assertEqual(stream.count, 2)
        self.assertEqual(events, ["start", "end", "start", "end"])

    def test_stale_stream_drops_parts(self) -> None:
        played: list[bytes] = []
        speaker = self._speaker(played)
        stream = speaker.stream(1)
        speaker.speak(1, japanese="new").join(5)
        stream.add("old")
        stream.close()
        stream.join(5)
        self.assertEqual(played, [b"new"])

    def test_stream_synth_error_reports_once(self) -> None:
        played: list[bytes] = []
        events: list[str] = []
        stream = self._speaker(played, events, fail_on="b").stream(1)
        for part in ("a", "b", "c"):
            stream.add(part)
        stream.close()
        stream.join(5)
        self.assertEqual(events.count("error"), 1)
        self.assertNotIn(b"c", played)


if __name__ == "__main__":
    unittest.main()
