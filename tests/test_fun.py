import random
import unittest
from datetime import date, datetime

from src.nuri_assistant.fun import (CHOICES, FunTools, Occasion, fortune_text, normalize,
                                    occasion_today, parse_birthday, play, today_fortune)
from src.nuri_assistant.fun.seasons import Holiday, holiday_today


class FortuneTests(unittest.TestCase):
    def test_deterministic_and_varies(self):
        d = date(2026, 10, 14)
        self.assertEqual(today_fortune(d, "nuri"), today_fortune(d, "nuri"))
        results = {today_fortune(date(2026, 1, 1 + i), p) for i in range(20) for p in ("nuri", "sera")}
        self.assertGreater(len(results), 10)
        self.assertEqual(len({today_fortune(d, p).stars for p in
                              ("nuri", "sera", "yuki", "akane", "shizuku", "hinata", "sakura", "reika")} |
                             {today_fortune(date(2026, 3, i + 1), "nuri").stars for i in range(28)}) > 1, True)

    def test_range_and_text(self):
        for i in range(100):
            f = today_fortune(date(2026, 1, 1).fromordinal(date(2026, 1, 1).toordinal() + i), "nuri")
            self.assertTrue(1 <= f.stars <= 5)
            self.assertTrue(f.advice)
        f = today_fortune(date(2026, 10, 14), "nuri")
        text = fortune_text(f)
        first, second = text.split("\n")
        self.assertEqual(first, f"운세 {'★' * f.stars}{'☆' * (5 - f.stars)} · 행운의 색 {f.color} · 행운의 물건 {f.item}")
        self.assertEqual(second, f.advice)


class RpsTests(unittest.TestCase):
    def test_normalize(self):
        for text, want in [("가위", "가위"), ("주먹", "바위"), ("빠", "보"), ("찌", "가위"), (" Rock ", "바위"),
                           ("paper", "보"), ("scissors", "가위"), ("바위", "바위"), ("보", "보")]:
            self.assertEqual(normalize(text), want)
        self.assertIsNone(normalize("돌"))
        self.assertIsNone(normalize(None))

    def test_all_outcomes(self):
        table = {("가위", "가위"): "draw", ("가위", "바위"): "lose", ("가위", "보"): "win",
                 ("바위", "가위"): "win", ("바위", "바위"): "draw", ("바위", "보"): "lose",
                 ("보", "가위"): "lose", ("보", "바위"): "win", ("보", "보"): "draw"}

        class Fixed:
            def __init__(self, value):
                self.value = value

            def choice(self, seq):
                return self.value

        for (user, computer), result in table.items():
            self.assertEqual(play(user, Fixed(computer)), (computer, result))
        self.assertIn(play("보", random.Random(1))[0], CHOICES)


class AnniversaryTests(unittest.TestCase):
    def test_birthday(self):
        self.assertEqual(occasion_today(date(2026, 3, 14), "03-14", ""), Occasion("birthday"))
        self.assertIsNone(occasion_today(date(2026, 3, 15), "03-14", ""))
        self.assertIsNone(occasion_today(date(2026, 3, 14), "", ""))

    def test_leap_birthday(self):
        self.assertEqual(occasion_today(date(2026, 2, 28), "02-29", ""), Occasion("birthday"))
        self.assertIsNone(occasion_today(date(2028, 2, 28), "02-29", ""))
        self.assertEqual(occasion_today(date(2028, 2, 29), "02-29", ""), Occasion("birthday"))

    def test_milestones(self):
        met = date(2026, 1, 1)
        for n in (100, 200, 300, 500, 1000):
            from datetime import timedelta
            self.assertEqual(occasion_today(met + timedelta(days=n), "", met.isoformat()), Occasion("together", n))
        self.assertIsNone(occasion_today(met + timedelta(days=101), "", met.isoformat()))
        self.assertIsNone(occasion_today(met, "", met.isoformat()))

    def test_yearly(self):
        self.assertEqual(occasion_today(date(2025, 6, 10), "", "2024-06-10"), Occasion("together", 365))
        self.assertEqual(occasion_today(date(2026, 6, 10), "", "2024-06-10"), Occasion("together", 730))
        self.assertIsNone(occasion_today(date(2025, 6, 11), "", "2024-06-10"))

    def test_both_and_invalid(self):
        self.assertEqual(occasion_today(date(2025, 6, 10), "06-10", "2024-06-10"), Occasion("birthday"))
        self.assertIsNone(occasion_today(date(2025, 6, 10), "abc", "bad"))

    def test_parse_birthday(self):
        for text in ("3월 14일", "03-14", "3/14", "0314", "3월14일", "3.14"):
            self.assertEqual(parse_birthday(text), "03-14")
        self.assertEqual(parse_birthday("2월 29일"), "02-29")
        for text in ("", "13월 1일", "2월 30일", "hello", "314"):
            self.assertIsNone(parse_birthday(text))


class FunToolsTests(unittest.TestCase):
    def make(self):
        return FunTools(lambda: "nuri", clock=lambda: datetime(2026, 10, 14, 9, 0), rng=random.Random(3))

    def test_fortune(self):
        result = self.make().execute("today_fortune", {})
        expected = today_fortune(date(2026, 10, 14), "nuri")
        self.assertTrue(result["ok"])
        self.assertEqual(result["stars"], expected.stars)
        self.assertEqual(result["text"], fortune_text(expected))

    def test_rps(self):
        tools = self.make()
        computer, outcome = play("바위", random.Random(3))
        result = tools.execute("play_rps", {"choice": "주먹"})
        self.assertEqual(result, {"ok": True, "user": "바위", "computer": computer, "result": outcome})
        self.assertFalse(tools.execute("play_rps", {"choice": "돌"})["ok"])

    def test_plumbing(self):
        tools = self.make()
        self.assertEqual(tools.take_pending(), [])
        self.assertFalse(tools.owns(object()))
        with self.assertRaises(ValueError):
            tools.confirm(object())
        self.assertFalse(tools.execute("nope", {}).get("ok", False))


class SeasonsTests(unittest.TestCase):
    def test_fixed_dates(self):
        cases = {(1, 1): "새해", (2, 14): "밸런타인데이", (3, 14): "화이트데이", (10, 31): "핼러윈",
                 (11, 11): "빼빼로데이", (12, 24): "크리스마스 이브", (12, 25): "크리스마스",
                 (12, 31): "한 해 마지막 날"}
        for (m, d), name in cases.items():
            self.assertEqual(holiday_today(date(2026, m, d)), Holiday("holiday", name), name)

    def test_lunar_table(self):
        self.assertEqual(holiday_today(date(2026, 2, 17)), Holiday("holiday", "설날"))
        self.assertEqual(holiday_today(date(2030, 2, 3)), Holiday("holiday", "설날"))
        self.assertEqual(holiday_today(date(2026, 9, 25)), Holiday("holiday", "추석"))
        self.assertEqual(holiday_today(date(2030, 9, 12)), Holiday("holiday", "추석"))

    def test_seasons_and_ordinary(self):
        for (m, d), name in {(3, 1): "봄", (6, 1): "여름", (9, 1): "가을", (12, 1): "겨울"}.items():
            self.assertEqual(holiday_today(date(2026, m, d)), Holiday("season", name))
        self.assertIsNone(holiday_today(date(2026, 10, 14)))
        self.assertIsNone(holiday_today(date(2031, 2, 17)))

    def test_holiday_beats_season(self):
        # no fixed holiday shares a date with a season start today; a lunar one would still win
        self.assertEqual(holiday_today(date(2026, 3, 14)).kind, "holiday")


if __name__ == "__main__":
    unittest.main()
