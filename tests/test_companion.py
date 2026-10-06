from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from src.nuri_assistant import HistoryStore, RenameError, RenameInput, apply_batch_rename, preview_batch, undo_last_batch
from src.nuri_assistant.companion import (
    EXPRESSIONS,
    PERSONAS,
    Companion,
    CompanionSettings,
    ConversationStore,
    OllamaClient,
    OllamaError,
    ReplyParser,
    get_persona,
    load_settings,
    save_settings,
)


class FakeStreamResponse:
    def __init__(self, events: list[dict]) -> None:
        self._lines = [json.dumps(event, ensure_ascii=False).encode("utf-8") + b"\n" for event in events]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        return iter(self._lines)

    def read(self) -> bytes:
        return b"".join(self._lines)


def _chunks(*parts: str) -> list[dict]:
    events = [{"message": {"role": "assistant", "content": part}, "done": False} for part in parts]
    return events + [{"message": {"role": "assistant", "content": ""}, "done": True}]


class NoClobberTest(unittest.TestCase):
    def test_batch_rename_refuses_target_created_after_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first, second = root / "first.pdf", root / "second.pdf"
            first.write_text("first", encoding="utf-8")
            second.write_text("second", encoding="utf-8")
            history = HistoryStore(root / "history.sqlite3")
            previews = preview_batch(
                [RenameInput(first, "20260628", "ja00", "001"), RenameInput(second, "20260628", "ja00", "002")]
            )
            # Another program creates the second target between preview and execution.
            (root / "20260628_ja00_002.pdf").write_text("someone else's file", encoding="utf-8")

            with self.assertRaises(RenameError):
                apply_batch_rename(previews, history)

            self.assertEqual((root / "20260628_ja00_002.pdf").read_text(encoding="utf-8"), "someone else's file")
            self.assertEqual(first.read_text(encoding="utf-8"), "first")
            self.assertEqual(second.read_text(encoding="utf-8"), "second")
            self.assertFalse((root / "20260628_ja00_001.pdf").exists())

    def test_undo_refuses_to_overwrite_recreated_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "raw.pdf"
            source.write_text("original", encoding="utf-8")
            history = HistoryStore(root / "history.sqlite3")
            apply_batch_rename(preview_batch([RenameInput(source, "20260628", "ja00", "001")]), history)
            source.write_text("new file with the old name", encoding="utf-8")

            with self.assertRaises(RenameError):
                undo_last_batch(history)

            self.assertEqual(source.read_text(encoding="utf-8"), "new file with the old name")
            self.assertTrue((root / "20260628_ja00_001.pdf").exists())


class PersonaTest(unittest.TestCase):
    def test_every_persona_is_complete(self) -> None:
        self.assertGreaterEqual(len(PERSONAS), 5)
        for persona_id, persona in PERSONAS.items():
            with self.subTest(persona=persona_id):
                self.assertEqual(persona.id, persona_id)
                self.assertTrue(persona.greetings and persona.pokes)
                self.assertIn(persona.look.hairstyle, {"twintails", "short", "ponytail", "long", "drills"})
                prompt = persona.system_prompt("민수", "2026-10-06 (화) 09:00")
                self.assertIn(persona.name, prompt)
                self.assertIn("민수", prompt)
                for expression in EXPRESSIONS:
                    self.assertIn(f"[{expression}]", prompt)

    def test_unknown_persona_falls_back_to_default(self) -> None:
        self.assertEqual(get_persona("missing").id, "sakura")


class ReplyParserTest(unittest.TestCase):
    def test_strips_tag_split_across_chunks(self) -> None:
        parser = ReplyParser()
        seen = [parser.feed(chunk) for chunk in ("[ha", "ppy] 좋아", ", 같이 해보자!")]

        self.assertEqual(seen, ["", "좋아", "좋아, 같이 해보자!"])
        self.assertEqual(parser.expression, "happy")

    def test_hides_think_block_and_korean_alias(self) -> None:
        parser = ReplyParser()
        parser.feed("<think>사용자가 인사")
        self.assertEqual(parser.feed("함</think>\n[부끄럼] 바, 바보!"), "바, 바보!")
        self.assertEqual(parser.expression, "shy")

    def test_keeps_unknown_brackets_and_tracks_last_tag(self) -> None:
        parser = ReplyParser()
        parser.feed("[neutral] 할 일 [중요] 확인했어. [angry] 미루지 마")

        self.assertEqual(parser.finish(), "할 일 [중요] 확인했어. 미루지 마")
        self.assertEqual(parser.expression, "angry")


class OllamaClientTest(unittest.TestCase):
    def test_chat_stream_sends_local_request_and_yields_content(self) -> None:
        with patch("src.nuri_assistant.companion.llm.urlopen", return_value=FakeStreamResponse(_chunks("[happy]", " 안녕!"))) as urlopen:
            chunks = list(OllamaClient().chat_stream("qwen3:8b", [{"role": "user", "content": "hi"}]))

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        self.assertEqual(chunks, ["[happy]", " 안녕!"])
        self.assertTrue(payload["stream"])
        self.assertFalse(payload["think"])

    def test_stream_error_event_raises(self) -> None:
        with patch("src.nuri_assistant.companion.llm.urlopen", return_value=FakeStreamResponse([{"error": "out of memory"}])):
            with self.assertRaises(OllamaError):
                list(OllamaClient().chat_stream("qwen3:8b", []))

    def test_connection_failure_is_friendly(self) -> None:
        with patch("src.nuri_assistant.companion.llm.urlopen", side_effect=URLError("refused")):
            with self.assertRaisesRegex(OllamaError, "Ollama"):
                OllamaClient().list_models()


class FakeClient:
    def __init__(self, parts: list[str]) -> None:
        self.parts = parts
        self.messages: list[dict[str, str]] = []

    def chat_stream(self, _model, messages, options=None):
        self.messages = messages
        yield from self.parts


class FailingClient:
    def chat_stream(self, _model, _messages, options=None):
        raise OllamaError("down")
        yield  # pragma: no cover


class CompanionTest(unittest.TestCase):
    def test_reply_streams_and_remembers_conversation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ConversationStore(Path(tmp) / "companion.sqlite3")
            client = FakeClient(["[happy] 네", ", 주인님!"])
            companion = Companion(get_persona("sakura"), client, store, "qwen3:8b", user_name="민수",
                                  clock=lambda: datetime(2026, 10, 6, 9, 30))
            updates: list[tuple[str, str]] = []

            reply = companion.reply("안녕", on_update=lambda text, expression: updates.append((text, expression)))

            self.assertEqual(reply.text, "네, 주인님!")
            self.assertEqual(reply.expression, "happy")
            self.assertEqual(updates[-1], ("네, 주인님!", "happy"))
            self.assertIn("2026-10-06 (화) 09:30", client.messages[0]["content"])
            self.assertEqual(
                [(row["role"], row["content"]) for row in store.recent("sakura")],
                [("user", "안녕"), ("assistant", "[happy] 네, 주인님!")],
            )

            client.parts = ["[neutral] 기억하고 있어요."]
            companion.reply("내가 뭐라고 했지?")
            self.assertEqual([message["role"] for message in client.messages], ["system", "user", "assistant", "user"])
            self.assertEqual(store.recent("akane"), [])

    def test_failed_reply_is_not_saved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ConversationStore(Path(tmp) / "companion.sqlite3")
            companion = Companion(get_persona("akane"), FailingClient(), store, "qwen3:8b")

            with self.assertRaises(OllamaError):
                companion.reply("안녕")

            self.assertEqual(store.recent("akane"), [])

    def test_history_limit_and_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ConversationStore(Path(tmp) / "companion.sqlite3")
            for index in range(5):
                store.add("hinata", "user", f"m{index}")

            self.assertEqual([row["content"] for row in store.recent("hinata", limit=2)], ["m3", "m4"])
            self.assertEqual(store.clear("hinata"), 5)


class SettingsTest(unittest.TestCase):
    def test_round_trip_and_ignore_unknown_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "companion.json"
            save_settings(path, CompanionSettings(persona_id="reika", user_name="민수", x=10, y=20))
            data = json.loads(path.read_text(encoding="utf-8"))
            data["removed_option"] = True
            path.write_text(json.dumps(data), encoding="utf-8")

            settings = load_settings(path)

            self.assertEqual((settings.persona_id, settings.user_name, settings.x, settings.y), ("reika", "민수", 10, 20))

    def test_broken_file_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "companion.json"
            path.write_text("{broken", encoding="utf-8")

            self.assertEqual(load_settings(path), CompanionSettings())


if __name__ == "__main__":
    unittest.main()
