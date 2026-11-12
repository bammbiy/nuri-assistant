"""Sharp display on scaled Windows screens (125%, 150%): opt-in, set before the first window.

By default the process is not DPI aware, so Windows stretches every window by the display scale:
the character keeps its physical size but turns blurry. With "sharp display" on, the process
declares itself DPI aware and Windows draws it 1:1. The frames are shown pixel for pixel, so
they are crisp but smaller on the screen (two thirds at 150%). Tk's point size is pinned to
96 dpi so text keeps the proportions the pixel layouts were made for.
"""
from __future__ import annotations

import sys

_sharp = False


def enable(windll=None) -> bool:
    """Declare the process system-DPI aware. Must run before any window exists. False if unsupported."""
    global _sharp
    if windll is None:
        if sys.platform != "win32":
            return False
        import ctypes
        windll = ctypes.windll
    try:
        windll.shcore.SetProcessDpiAwareness(1)  # system aware; per-monitor would rescale mid-drag
        _sharp = True
    except (AttributeError, OSError):
        try:
            _sharp = bool(windll.user32.SetProcessDPIAware())  # Windows 7 / awareness already set
        except (AttributeError, OSError):
            _sharp = False
    return _sharp


def active() -> bool:
    return _sharp


def pin_scaling(root) -> None:
    """Keep Tk at 96 dpi (1 point = 1/72 inch = 96/72 pixels) so fonts match the pixel layouts."""
    if _sharp:
        root.tk.call("tk", "scaling", 96 / 72)
