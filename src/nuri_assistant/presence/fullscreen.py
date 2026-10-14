"""Is a full-screen app in front? Windows only, window geometry and class name only (never titles)."""

from __future__ import annotations

import sys

Rect = tuple[int, int, int, int]  # left, top, right, bottom

MONITOR_DEFAULTTONEAREST = 2
GA_ROOT = 2
GWL_STYLE = -16
WS_CAPTION = 0x00C00000
SHELL_CLASSES = frozenset({"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"})


def covers(window: Rect, monitor: Rect, tolerance: int = 2) -> bool:
    """True when the window covers the whole monitor (each edge within tolerance or beyond)."""
    return (window[0] <= monitor[0] + tolerance
            and window[1] <= monitor[1] + tolerance
            and window[2] >= monitor[2] - tolerance
            and window[3] >= monitor[3] - tolerance)


def looks_fullscreen(window: Rect, monitor: Rect, style: int, tolerance: int = 2) -> bool:
    """Covers the monitor and has no title bar (a maximized normal window keeps its caption)."""
    return covers(window, monitor, tolerance) and not (style & WS_CAPTION)


def foreground_fullscreen(own_windows: set[int] = frozenset()) -> bool | None:
    """Whether the foreground window fills its monitor; None when unknown (non-Windows or API error)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetAncestor.restype = wintypes.HWND
        user32.MonitorFromWindow.restype = wintypes.HANDLE
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        handle = int(hwnd)
        root = user32.GetAncestor(hwnd, GA_ROOT)
        if handle in own_windows or (root and int(root) in own_windows):
            return False
        name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, name, 256)
        if name.value in SHELL_CLASSES:
            return False
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not monitor or not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        m = info.rcMonitor
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        style = user32.GetWindowLongW(hwnd, GWL_STYLE) & 0xFFFFFFFF
        return looks_fullscreen((rect.left, rect.top, rect.right, rect.bottom),
                                (m.left, m.top, m.right, m.bottom), style)
    except (OSError, AttributeError, ValueError):
        return None
