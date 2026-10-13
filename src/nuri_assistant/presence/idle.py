"""마지막 키보드·마우스 입력 이후 흐른 시간.

Windows의 GetLastInputInfo로 마지막 입력의 시각만 읽습니다.
어떤 키를 눌렀는지, 화면에 무엇이 있는지는 읽지 않습니다.
Windows가 아니거나 호출이 실패하면 None을 돌려주고, 이 기능은 꺼진 채로 둡니다.
"""

import sys


def idle_seconds():
    """입력이 없었던 시간(초). 알 수 없으면 None."""
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        tick = ctypes.windll.kernel32.GetTickCount()
        return ((tick - info.dwTime) & 0xFFFFFFFF) / 1000.0
    except (OSError, AttributeError):
        return None
