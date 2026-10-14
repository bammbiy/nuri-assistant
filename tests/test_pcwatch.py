import re
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from src.nuri_assistant.pcwatch import DownloadNudge, count_waiting, find_when, suggest


NOW = datetime(2026, 10, 14, 9, 0)


class CountWaitingTests(unittest.TestCase):
    def test_counts_only_waiting_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ["a.pdf", "B.PDF", "c.crdownload", "d.pdf.part", ".e.pdf", "~$f.pdf",
                         "g.txt", "20261001-한겨레-01.pdf", "h.pdf.tmp"]:
                (root / name).write_bytes(b"x")
            (root / "sub").mkdir()
            (root / "sub" / "z.pdf").write_bytes(b"x")
            (root / "dir.pdf").mkdir()
            named = re.compile(r"\d{8}-.+-\d+")
            self.assertEqual(count_waiting(root, (".pdf",), named), 2)
            self.assertEqual(count_waiting(root, (".pdf", ".txt"), None), 4)

    def test_missing_folder(self):
        self.assertEqual(count_waiting(Path("/no/such/folder/xyz"), (".pdf",), None), 0)


class DownloadNudgeTests(unittest.TestCase):
    def test_threshold_and_gap(self):
        nudge = DownloadNudge(threshold=10, gap=timedelta(hours=24))
        self.assertFalse(nudge.due(NOW, 9))
        self.assertTrue(nudge.due(NOW, 10))
        nudge.mark(NOW)
        self.assertFalse(nudge.due(NOW + timedelta(hours=23), 20))
        self.assertTrue(nudge.due(NOW + timedelta(hours=24), 20))

    def test_disabled(self):
        self.assertFalse(DownloadNudge(threshold=0).due(NOW, 100))


class SuggestTests(unittest.TestCase):
    def test_event_with_date_and_time(self):
        s = suggest("10월 20일 오후 3시 치과 예약", NOW)
        self.assertEqual(s.kind, "event")
        self.assertEqual(s.when_text, "10월 20일 오후 3시")
        self.assertEqual(s.title, "치과 예약")

    def test_tomorrow_half_hour(self):
        s = suggest("내일 7시 반 팀 회식", NOW)
        self.assertEqual(s.kind, "event")
        self.assertEqual(s.when_text, "내일 7시 반")
        self.assertEqual(s.title, "팀 회식")

    def test_iso_date(self):
        s = suggest("2026-11-02 정기검진", NOW)
        self.assertEqual(s.kind, "event")
        self.assertEqual(s.when_text, "2026-11-02")
        self.assertEqual(s.title, "정기검진")

    def test_particle_after_expression(self):
        s = suggest("금요일에 병원", NOW)
        self.assertEqual(s.when_text, "금요일")
        self.assertEqual(s.title, "병원")

    def test_shop_url(self):
        url = "https://www.coupang.com/vp/products/123456?itemId=1"
        s = suggest(url, NOW)
        self.assertEqual((s.kind, s.url, s.title), ("price", url, ""))

    def test_other_url(self):
        self.assertIsNone(suggest("https://example.com/page/2026-11-02", NOW))

    def test_rejected_texts(self):
        self.assertIsNone(suggest("", NOW))
        self.assertIsNone(suggest("내일 3시 회의 " + "가" * 200, NOW))
        self.assertIsNone(suggest("내일\n모레\n글피\n오늘 회의", NOW))
        self.assertIsNone(suggest("abcd1234efgh5678ijkl", NOW))
        self.assertIsNone(suggest("password: 내일 3시", NOW))
        self.assertIsNone(suggest("날씨 좋다 점심 뭐 먹지", NOW))

    def test_date_only_no_title(self):
        self.assertIsNone(suggest("내일", NOW))

    def test_find_when(self):
        text = "회의는 다음 주 화요일 오후 2시에 합니다"
        expr, start, end = find_when(text, NOW)
        self.assertEqual(expr, "다음 주 화요일 오후 2시")
        self.assertEqual(text[start:end], expr)
        self.assertIsNone(find_when("3시간 걸림", NOW))


if __name__ == "__main__":
    unittest.main()
