from __future__ import annotations

import unittest
from datetime import datetime, time, timedelta

from src.nuri_assistant.routine import daily_due, duration_text, hourly_key, parse_clock


class ParseClockTest(unittest.TestCase):
    def test_valid(self) -> None:
        cases = {"8:30": time(8, 30), "08:30": time(8, 30), "18시": time(18, 0), "18시 30분": time(18, 30)}
        for text, expected in cases.items():
            self.assertEqual(parse_clock(text), expected, text)

    def test_invalid(self) -> None:
        for text in ["", "25:00", "abc", "10:75"]:
            self.assertIsNone(parse_clock(text), text)


class DailyDueTest(unittest.TestCase):
    NOW = datetime(2026, 10, 6, 9, 0)

    def test_rules(self) -> None:
        self.assertFalse(daily_due(self.NOW, None, ""))
        self.assertFalse(daily_due(self.NOW, time(9, 30), ""))
        self.assertTrue(daily_due(self.NOW, time(9, 0), ""))
        self.assertTrue(daily_due(self.NOW, time(8, 0), "2026-10-05"))
        self.assertFalse(daily_due(self.NOW, time(8, 0), "2026-10-06"))


class DailyDueWindowTest(unittest.TestCase):
    def test_window_skips_late_start(self) -> None:
        clock, window = time(18, 0), timedelta(hours=3)
        self.assertTrue(daily_due(datetime(2026, 10, 13, 20, 59), clock, "", window))
        self.assertFalse(daily_due(datetime(2026, 10, 13, 21, 0), clock, "", window))
        self.assertFalse(daily_due(datetime(2026, 10, 13, 23, 30), clock, "2026-10-12", window))
        self.assertTrue(daily_due(datetime(2026, 10, 13, 23, 30), clock, "2026-10-12"))  # no window: still due


class DurationTextTest(unittest.TestCase):
    def test_wording(self) -> None:
        for minutes, expected in [(40, "40분"), (60, "1시간"), (80, "1시간 20분"), (0, "0분"), (120, "2시간")]:
            self.assertEqual(duration_text(minutes), expected)


class HourlyKeyTest(unittest.TestCase):
    def test_window_and_hours(self) -> None:
        self.assertEqual(hourly_key(datetime(2026, 10, 6, 15, 2), ""), "2026-10-06T15")
        self.assertIsNone(hourly_key(datetime(2026, 10, 6, 15, 3), ""))
        self.assertIsNone(hourly_key(datetime(2026, 10, 6, 7, 0), ""))
        self.assertEqual(hourly_key(datetime(2026, 10, 6, 8, 0), ""), "2026-10-06T08")
        self.assertEqual(hourly_key(datetime(2026, 10, 6, 23, 1), ""), "2026-10-06T23")

    def test_only_once_per_hour(self) -> None:
        key = hourly_key(datetime(2026, 10, 6, 9, 0), "")
        self.assertIsNone(hourly_key(datetime(2026, 10, 6, 9, 1), key))
        self.assertEqual(hourly_key(datetime(2026, 10, 6, 10, 0), key), "2026-10-06T10")
        self.assertEqual(hourly_key(datetime(2026, 10, 7, 9, 0), key), "2026-10-07T09")


if __name__ == "__main__":
    unittest.main()
