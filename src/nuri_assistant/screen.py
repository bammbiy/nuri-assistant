"""Where the character window may sit: the work area (screen minus taskbar) and all monitors.

Tk only knows the primary screen's full size, which puts the default spot under a tall or
moved taskbar and pulls a window parked on a second monitor back to the first. On Windows
the real rectangles come from the Win32 API; elsewhere the caller's screen size is used.
No Tk here, so the arithmetic is unit-tested.
"""
from __future__ import annotations

import sys
from typing import NamedTuple

EDGE_MARGIN = 16  # gap between the window and the taskbar / screen edge at the default spot
MIN_VISIBLE = 80  # px of the window that must stay on some screen, else it is brought back


class Rect(NamedTuple):
    left: int
    top: int
    right: int
    bottom: int


def work_area(screen_w: int, screen_h: int) -> Rect:
    """Primary monitor minus the taskbar (Windows); the whole screen elsewhere."""

    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            rect = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
                return Rect(rect.left, rect.top, rect.right, rect.bottom)
        except (AttributeError, OSError):
            pass
    return Rect(0, 0, screen_w, screen_h)


def all_monitors(screen_w: int, screen_h: int) -> Rect:
    """Bounding box of every monitor (Windows virtual screen); the screen elsewhere."""

    if sys.platform == "win32":
        try:
            import ctypes

            metric = ctypes.windll.user32.GetSystemMetrics
            left, top, width, height = (metric(index) for index in (76, 77, 78, 79))  # SM_*VIRTUALSCREEN
            if width > 0 and height > 0:
                return Rect(left, top, left + width, top + height)
        except (AttributeError, OSError):
            pass
    return Rect(0, 0, screen_w, screen_h)


def default_position(area: Rect, width: int, height: int, margin: int = EDGE_MARGIN) -> tuple[int, int]:
    """Bottom-right corner of the work area, just above the taskbar."""

    return area.right - width - margin, area.bottom - height - margin


def is_reachable(x: int, y: int, width: int, height: int, bounds: Rect, min_visible: int = MIN_VISIBLE) -> bool:
    """True if enough of the window is on some monitor to see it and drag it back."""

    visible_w = min(x + width, bounds.right) - max(x, bounds.left)
    visible_h = min(y + height, bounds.bottom) - max(y, bounds.top)
    return visible_w >= min(min_visible, width) and visible_h >= min(min_visible, height) and y >= bounds.top
