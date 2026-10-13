import unittest
from datetime import datetime, timedelta
from unittest import mock

from src.nuri_assistant.presence import PresenceTracker, idle_seconds

T0 = datetime(2026, 10, 13, 9, 0)


def run(tracker, start_min, end_min, idle=0.0, quiet=False):
    """분 단위로 폴링하며 (분, 종류, 값) 목록을 모은다."""
    out = []
    for m in range(start_min, end_min + 1):
        for kind, value in tracker.update(T0 + timedelta(minutes=m), idle, quiet):
            out.append((m, kind, value))
    return out


class PresenceTests(unittest.TestCase):
    def test_welcome_back_after_away(self):
        t = PresenceTracker(break_minutes=0, water_minutes=0)
        run(t, 0, 10)
        events = []
        for m in range(11, 51):
            events += t.update(T0 + timedelta(minutes=m), (m - 10) * 60.0)
        self.assertEqual(events, [])
        events = t.update(T0 + timedelta(minutes=51), 0.0)
        self.assertEqual(events, [("welcome_back", 41)])

    def test_no_welcome_under_threshold(self):
        t = PresenceTracker(break_minutes=0, water_minutes=0)
        run(t, 0, 5)
        t.update(T0 + timedelta(minutes=20), 900.0)
        self.assertEqual(t.update(T0 + timedelta(minutes=21), 0.0), [])

    def test_break_then_again(self):
        t = PresenceTracker(water_minutes=0)
        events = run(t, 0, 125)
        self.assertEqual([(m, k) for m, k, _ in events], [(60, "break"), (120, "break")])
        self.assertEqual(events[0][2], 60)

    def test_rest_resets_streak(self):
        t = PresenceTracker(water_minutes=0)
        run(t, 0, 50)
        t.update(T0 + timedelta(minutes=56), 360.0)
        events = run(t, 57, 100)
        self.assertEqual(events, [])
        events = run(t, 101, 120)
        self.assertEqual([k for _, k, _ in events], ["break"])

    def test_water_only_while_active(self):
        t = PresenceTracker(break_minutes=0)
        events = run(t, 0, 185)
        self.assertEqual([(m, k, v) for m, k, v in events],
                         [(90, "water", 90), (180, "water", 90)])
        t2 = PresenceTracker(break_minutes=0, away_minutes=0)
        t2.update(T0, 0.0)
        self.assertEqual(t2.update(T0 + timedelta(minutes=100), 600.0), [])

    def test_quiet_restarts_streak_and_defers_water(self):
        t = PresenceTracker()
        self.assertEqual(run(t, 0, 100, quiet=True), [])
        events = t.update(T0 + timedelta(minutes=101), 0.0)
        self.assertEqual([k for k, _ in events], ["water"])
        events = run(t, 102, 170)
        self.assertEqual([(m, k) for m, k, _ in events], [(160, "break")])

    def test_quiet_active_time_gives_no_break_afterwards(self):
        t = PresenceTracker(water_minutes=0)
        self.assertEqual(run(t, 0, 70, quiet=True), [])
        events = run(t, 71, 140)
        self.assertEqual([(m, k, v) for m, k, v in events], [(130, "break", 60)])

    def test_welcome_deferred_through_quiet(self):
        t = PresenceTracker(break_minutes=0, water_minutes=0)
        t.update(T0, 0.0)
        t.update(T0 + timedelta(minutes=40), 2400.0)
        for m in (41, 42, 43):
            self.assertEqual(t.update(T0 + timedelta(minutes=m), 0.0, quiet=True), [])
        self.assertEqual(t.update(T0 + timedelta(minutes=44), 0.0),
                         [("welcome_back", 41)])
        self.assertEqual(t.update(T0 + timedelta(minutes=45), 0.0), [])

    def test_zero_disables(self):
        t = PresenceTracker(away_minutes=0, break_minutes=0, water_minutes=0)
        self.assertEqual(run(t, 0, 200), [])
        t.update(T0 + timedelta(minutes=300), 7200.0)
        self.assertEqual(t.update(T0 + timedelta(minutes=301), 0.0), [])

    def test_idle_seconds_none_off_windows(self):
        with mock.patch("sys.platform", "linux"):
            self.assertIsNone(idle_seconds())


if __name__ == "__main__":
    unittest.main()
