from __future__ import annotations

import unittest

from src.nuri_assistant.screen import Rect, all_monitors, default_position, is_reachable, work_area


class ScreenTest(unittest.TestCase):
    def test_default_spot_is_bottom_right_above_the_taskbar(self) -> None:
        area = Rect(0, 0, 1920, 1032)  # 1080p with a 48px taskbar at the bottom

        x, y = default_position(area, 415, 382)

        self.assertEqual((x + 415, y + 382), (1920 - 16, 1032 - 16))

    def test_taskbar_on_the_left_or_top_is_respected(self) -> None:
        self.assertEqual(default_position(Rect(0, 48, 1920, 1080), 400, 300), (1504, 764))
        self.assertEqual(default_position(Rect(62, 0, 1920, 1080), 400, 300), (1504, 764))

    def test_second_monitor_spot_is_kept(self) -> None:
        both = Rect(0, 0, 3840, 1080)  # second 1080p monitor to the right

        self.assertTrue(is_reachable(3300, 600, 415, 382, both))
        self.assertFalse(is_reachable(3300, 600, 415, 382, Rect(0, 0, 1920, 1080)), "monitor unplugged")

    def test_mostly_off_screen_window_is_brought_back(self) -> None:
        screen = Rect(0, 0, 1920, 1080)

        self.assertTrue(is_reachable(1600, 900, 415, 382, screen), "partly outside is fine")
        self.assertFalse(is_reachable(1890, 900, 415, 382, screen))
        self.assertFalse(is_reachable(500, -50, 415, 382, screen), "title area above the screen")
        self.assertFalse(is_reachable(500, 1060, 415, 382, screen))

    def test_non_windows_falls_back_to_the_screen(self) -> None:
        import sys

        if sys.platform != "win32":
            self.assertEqual(work_area(1280, 1000), Rect(0, 0, 1280, 1000))
            self.assertEqual(all_monitors(1280, 1000), Rect(0, 0, 1280, 1000))


if __name__ == "__main__":
    unittest.main()
