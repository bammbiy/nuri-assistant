import random
import sys
import unittest
from datetime import datetime, timedelta

from src.nuri_assistant.presence import (CHATTER_MINUTES, ClickCombo, IdleChatter, PatDetector,
                                         covers, foreground_fullscreen, looks_fullscreen)

T0 = datetime(2026, 10, 14, 9, 0)
MON = (0, 0, 1920, 1080)


class CoversTests(unittest.TestCase):
    def test_exact_and_beyond(self):
        self.assertTrue(covers(MON, MON))
        self.assertTrue(covers((-8, -8, 1928, 1088), MON))

    def test_tolerance(self):
        self.assertTrue(covers((2, 2, 1918, 1078), MON))
        self.assertFalse(covers((3, 0, 1920, 1080), MON))
        self.assertTrue(covers((3, 0, 1920, 1080), MON, tolerance=3))

    def test_smaller_window(self):
        self.assertFalse(covers((100, 100, 900, 700), MON))
        self.assertFalse(covers((0, 0, 1920, 1040), MON))

    def test_foreground(self):
        result = foreground_fullscreen(set())
        if sys.platform == "win32":
            self.assertIn(result, (True, False, None))
        else:
            self.assertIsNone(result)


class LooksFullscreenTests(unittest.TestCase):
    CAPTION = 0x00C00000

    def test_no_caption_is_fullscreen(self):
        self.assertTrue(looks_fullscreen(MON, MON, 0x16000000))

    def test_caption_is_not(self):
        self.assertFalse(looks_fullscreen(MON, MON, 0x16000000 | self.CAPTION))

    def test_work_area_only_is_not(self):
        self.assertFalse(looks_fullscreen((0, 0, 1920, 1040), MON, 0))

    def test_second_monitor_negative_coordinates(self):
        second = (-1920, 0, 0, 1080)
        self.assertTrue(looks_fullscreen(second, second, 0))
        self.assertFalse(looks_fullscreen(second, second, self.CAPTION))


def rub(det, xs, step=0.1, t=0.0):
    hits = 0
    for x in xs:
        t += step
        if det.feed(x, t):
            hits += 1
    return hits


class PatTests(unittest.TestCase):
    def test_rubbing_triggers_once(self):
        xs = [0, 20, 0, 20, 0, 20, 0, 20, 0, 20]
        self.assertEqual(rub(PatDetector(), xs), 1)

    def test_slow_does_not(self):
        xs = [0, 20, 0, 20, 0, 20, 0, 20, 0, 20]
        self.assertEqual(rub(PatDetector(), xs, step=1.0), 0)

    def test_one_way_does_not(self):
        self.assertEqual(rub(PatDetector(), list(range(0, 400, 10))), 0)

    def test_jitter_ignored(self):
        xs = [0, 3, 0, 3, 0, 3, 0, 3, 0, 3, 0, 3]
        self.assertEqual(rub(PatDetector(), xs), 0)

    def test_cooldown(self):
        det = PatDetector()
        xs = [0, 20] * 5
        self.assertEqual(rub(det, xs), 1)
        self.assertEqual(rub(det, xs, t=1.0), 0)
        self.assertEqual(rub(det, xs, t=20.0), 1)

    def test_reset(self):
        det = PatDetector()
        t = 0.0
        for x in [0, 20, 0, 20]:
            t += 0.1
            self.assertFalse(det.feed(x, t))
        det.reset()
        for x in [0, 20, 0]:
            t += 0.1
            self.assertFalse(det.feed(x, t))


class ClickComboTests(unittest.TestCase):
    def test_combo_and_restart(self):
        c = ClickCombo()
        self.assertEqual([c.click(t) for t in (0, 0.5, 1.0, 1.5)], [False, False, False, True])
        self.assertFalse(c.click(2.0))

    def test_too_slow(self):
        c = ClickCombo()
        self.assertFalse(any(c.click(t * 2.0) for t in range(8)))


class ChatterTests(unittest.TestCase):
    def test_first_after_one_interval(self):
        c = IdleChatter("보통", random.Random(1))
        self.assertFalse(c.due(T0))
        self.assertFalse(c.due(T0 + timedelta(minutes=27)))
        self.assertTrue(c.due(T0 + timedelta(minutes=53)))

    def test_jitter_bounds(self):
        for level, minutes in CHATTER_MINUTES.items():
            if not minutes:
                continue
            for seed in range(20):
                c = IdleChatter(level, random.Random(seed))
                c.reset(T0)
                self.assertFalse(c.due(T0 + timedelta(minutes=minutes * 0.69)))
                self.assertTrue(c.due(T0 + timedelta(minutes=minutes * 1.31)))

    def test_off_never(self):
        c = IdleChatter("끄기", random.Random(1))
        self.assertFalse(c.due(T0))
        self.assertFalse(c.due(T0 + timedelta(days=30)))

    def test_spoke_and_reset(self):
        c = IdleChatter("많이", random.Random(2))
        c.reset(T0)
        later = T0 + timedelta(minutes=30)
        self.assertTrue(c.due(later))
        c.spoke(later)
        self.assertFalse(c.due(later))
        c.reset(later + timedelta(minutes=20))
        self.assertFalse(c.due(later + timedelta(minutes=30)))

    def test_unknown_level(self):
        c = IdleChatter("엉뚱", random.Random(3))
        self.assertEqual(c.level, "보통")
        c.set_level("없음")
        self.assertEqual(c.level, "보통")
        c.set_level("조금")
        self.assertEqual(c.level, "조금")


if __name__ == "__main__":
    unittest.main()
