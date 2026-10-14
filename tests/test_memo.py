import tempfile
import unittest
from pathlib import Path

from src.nuri_assistant.memo import MemoAction, MemoStore, MemoTools


class MemoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = MemoStore(Path(self.tmp.name) / "c.sqlite3")
        self.tools = MemoTools(self.store)

    def test_store_crud(self) -> None:
        a = self.store.add(" 고양이 알레르기 ")
        b = self.store.add("생일은 3월 2일")
        self.assertEqual(a.text, "고양이 알레르기")
        self.assertEqual([m.text for m in self.store.all()], ["고양이 알레르기", "생일은 3월 2일"])
        self.assertEqual([m.id for m in self.store.find("생일")], [b.id])
        self.assertEqual(self.store.find(""), [])
        self.assertTrue(self.store.delete(a.id))
        self.assertFalse(self.store.delete(a.id))
        self.assertEqual(len(self.store.all()), 1)

    def test_remember_waits_for_confirmation(self) -> None:
        result = self.tools.execute("remember_fact", {"fact": "새우 알레르기가 있음"})
        self.assertTrue(result["ok"])
        self.assertEqual(self.store.all(), [])
        (action,) = self.tools.take_pending()
        self.assertTrue(self.tools.owns(action))
        self.assertEqual((action.heading, action.when, action.title), ("기억해 둘게요", "기억 수첩", "새우 알레르기가 있음"))
        self.assertEqual(self.tools.confirm(action), "기억해 둘게요: 새우 알레르기가 있음")
        self.assertEqual(len(self.store.all()), 1)

    def test_remember_rejects_empty_long_and_duplicate(self) -> None:
        self.assertFalse(self.tools.execute("remember_fact", {"fact": "  "})["ok"])
        self.assertFalse(self.tools.execute("remember_fact", {"fact": "가" * 121})["ok"])
        self.store.add("Likes Tea")
        result = self.tools.execute("remember_fact", {"fact": "likes tea"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "이미 기억하고 있어요")
        self.assertEqual(self.tools.take_pending(), [])

    def test_remember_rejects_duplicate_of_pending(self) -> None:
        self.assertTrue(self.tools.execute("remember_fact", {"fact": "Likes Tea"})["ok"])
        self.assertFalse(self.tools.execute("remember_fact", {"fact": " likes tea "})["ok"])
        self.assertEqual(len(self.tools.take_pending()), 1)

    def test_forget_single_multiple_none(self) -> None:
        self.store.add("고양이를 키움")
        self.store.add("고양이 알레르기")
        self.store.add("커피를 좋아함")
        many = self.tools.execute("forget_fact", {"keyword": "고양이"})
        self.assertFalse(many["ok"])
        self.assertEqual(len(many["candidates"]), 2)
        self.assertFalse(self.tools.execute("forget_fact", {"keyword": "강아지"})["ok"])
        self.assertTrue(self.tools.execute("forget_fact", {"keyword": "커피"})["ok"])
        (action,) = self.tools.take_pending()
        self.assertEqual(action.heading, "기억 지우기")
        self.assertEqual(self.tools.confirm(action), "잊어버릴게요: 커피를 좋아함")
        self.assertEqual(self.tools.confirm(action), "이미 없는 기억이에요.")
        self.assertEqual(len(self.store.all()), 2)

    def test_list_and_unknown(self) -> None:
        self.store.add("a")
        self.store.add("b")
        result = self.tools.execute("list_facts", {})
        self.assertEqual((result["count"], result["facts"]), (2, ["a", "b"]))
        self.assertFalse(self.tools.execute("nope", {})["ok"])
        self.assertFalse(self.tools.owns(object()))
        self.assertIsInstance(MemoAction("add", "x"), MemoAction)


if __name__ == "__main__":
    unittest.main()
