import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from src.nuri_assistant.companion.affection import DAILY_CAP, DAILY_CHAT_CAP, LEVELS, AffectionStore


NOW = datetime(2026, 10, 14, 12, 0)


class AffectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = AffectionStore(Path(self.tmp.name) / "c.sqlite3")

    def test_starts_at_first_level(self) -> None:
        self.assertEqual(self.store.points("nuri"), 0)
        self.assertEqual(self.store.level("nuri"), (0, "처음"))
        self.assertEqual(self.store.hearts("nuri"), "♥♡♡♡")
        self.assertEqual(self.store.next_threshold("nuri"), 30)

    def test_crossing_returns_new_level_once(self) -> None:
        results = [self.store.add("nuri", "todo_done", NOW) for _ in range(10)]
        self.assertEqual(results[:9], [None] * 9)
        self.assertEqual(results[9], 1)  # 30 points
        self.assertIsNone(self.store.add("nuri", "todo_done", NOW))
        self.assertEqual(self.store.level("nuri"), (1, "친근"))
        self.assertEqual(self.store.hearts("nuri"), "♥♥♡♡")
        self.assertEqual(self.store.next_threshold("nuri"), 100)

    def test_personas_are_separate(self) -> None:
        self.store.add("nuri", "approved", NOW)
        self.assertEqual(self.store.points("sera"), 0)

    def test_daily_chat_cap_resets_next_day(self) -> None:
        for _ in range(DAILY_CHAT_CAP + 5):
            self.store.add("nuri", "chat", NOW)
        self.assertEqual(self.store.points("nuri"), DAILY_CHAT_CAP)
        self.store.add("nuri", "approved", NOW)  # other reasons are not under the chat cap
        self.assertEqual(self.store.points("nuri"), DAILY_CHAT_CAP + 1)
        self.store.add("nuri", "chat", NOW + timedelta(days=1))
        self.assertEqual(self.store.points("nuri"), DAILY_CHAT_CAP + 2)

    def test_daily_total_cap_across_reasons_and_reset(self) -> None:
        for _ in range(DAILY_CHAT_CAP):
            self.store.add("nuri", "chat", NOW)
        for _ in range(10):
            self.store.add("nuri", "approved", NOW)
        self.assertEqual(self.store.points("nuri"), DAILY_CAP)
        self.assertIsNone(self.store.add("nuri", "todo_done", NOW))
        self.assertEqual(self.store.points("nuri"), DAILY_CAP)
        self.assertEqual(self.store.points("sera"), 0)
        self.store.add("nuri", "todo_done", NOW + timedelta(days=1))
        self.assertEqual(self.store.points("nuri"), DAILY_CAP + 3)

    def test_migrates_table_without_day_total(self) -> None:
        path = Path(self.tmp.name) / "old.sqlite3"
        conn = sqlite3.connect(path)
        try:
            conn.execute("CREATE TABLE affection (persona_id TEXT PRIMARY KEY, points INTEGER NOT NULL DEFAULT 0, "
                         "chat_date TEXT, chat_count INTEGER NOT NULL DEFAULT 0)")
            conn.execute("INSERT INTO affection VALUES ('nuri', 20, '2026-10-14', 5)")
            conn.commit()
        finally:
            conn.close()
        store = AffectionStore(path)
        self.assertEqual(store.points("nuri"), 20)
        store.add("nuri", "todo_done", NOW)
        self.assertEqual(store.points("nuri"), 23)

    def test_top_level_and_never_decreases(self) -> None:
        for day in range(40):
            for _ in range(DAILY_CAP // 3):
                self.store.add("nuri", "focus_done", NOW + timedelta(days=day))
        self.assertEqual(self.store.level("nuri"), (len(LEVELS) - 1, "단짝"))
        self.assertEqual(self.store.hearts("nuri"), "♥♥♥♥")
        self.assertIsNone(self.store.next_threshold("nuri"))
        before = self.store.points("nuri")
        self.store.add("nuri", "chat", NOW + timedelta(days=100))
        self.assertGreater(self.store.points("nuri"), before)

    def test_unknown_reason_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.store.add("nuri", "bogus", NOW)


if __name__ == "__main__":
    unittest.main()
