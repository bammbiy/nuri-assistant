"""UI smoke test: start the character app and open every window once.

The unit tests never import ``ui/``, so a broken import or a renamed argument in a window
only showed up when a person opened it. This test needs tkinter and a display, and is skipped
without them (Linux CI runs it under xvfb, Windows runners have a desktop).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import tkinter as tk
except ImportError:  # the plain unit tests still run on a Python without tkinter
    tk = None


def _display_available() -> bool:
    if tk is None:
        return False
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        return False
    try:
        root = tk.Tk()
    except tk.TclError:
        return False
    root.destroy()
    return True


# Menu entries that open a window (or change the view) without asking a question.
# Left out on purpose: "내 이름 설정" and "이 캐릭터의 기억 지우기" (modal dialogs), "종료".
MENU_WINDOWS = [
    "AI 설정…", "일정 보기", "할 일", "집중 타이머…", "최저가 알림", "가격 알림 설정…", "음성 설정…",
    "생활 알림 설정…", "대화 기록 보기", "기억 수첩", "개인정보 안내", "파일 정리 도구", "파일 정리 설정…",
    "파일/구매 비서", "비서 선택…",
]
MENU_ACTIONS = ["오늘 일정 브리핑", "오늘 하루 정리", "우리 사이", "오늘의 운세", "전신으로 보기", "전신으로 보기",
                "선명하게 보기 (고배율 화면)", "선명하게 보기 (고배율 화면)"]


@unittest.skipUnless(_display_available(), "tkinter와 화면(DISPLAY)이 있어야 하는 테스트")
class UiSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        from src.nuri_assistant.ui.character.mascot import MascotApp

        self.tmp = tempfile.TemporaryDirectory()
        app_dir = Path(self.tmp.name)
        # Nothing may leave the machine: closed local ports, voice off, no start-up picker.
        (app_dir / "companion.json").write_text(json.dumps({
            "ollama_url": "http://127.0.0.1:9", "voice_url": "http://127.0.0.1:9", "voice_enabled": False,
            "pick_on_start": False, "privacy_shown": True, "weather_city": "",
        }), encoding="utf-8")
        self.errors: list[str] = []
        self.app = MascotApp(app_dir)
        self.app.report_callback_exception = lambda exc, value, tb: self.errors.append(f"{exc.__name__}: {value}")
        self.app.update()

    def tearDown(self) -> None:
        try:
            self.app.destroy()
        except tk.TclError:
            pass
        self.tmp.cleanup()

    def _invoke(self, label: str) -> None:
        menu = self.app.menu
        for index in range(menu.index("end") + 1):
            if menu.type(index) in ("command", "checkbutton") and menu.entrycget(index, "label") == label:
                menu.invoke(index)
                self.app.update()
                return
        self.fail(f"메뉴에 '{label}' 항목이 없음")

    def _toplevels(self) -> list:
        return [w for w in self.app.winfo_children() if isinstance(w, tk.Toplevel) and w.winfo_exists()]

    def test_every_menu_window_opens(self) -> None:
        for label in MENU_WINDOWS:
            with self.subTest(label):
                before = set(self._toplevels())
                self._invoke(label)
                opened = [w for w in self._toplevels() if w not in before]
                self.assertTrue(opened, f"'{label}'을 눌러도 창이 열리지 않음")
                for window in opened:
                    window.destroy()
                self.app.update()
        self.assertEqual(self.errors, [])

    def test_menu_actions_run(self) -> None:
        for label in MENU_ACTIONS:
            self._invoke(label)
        self.assertEqual(self.errors, [])

    def test_menu_list_is_complete(self) -> None:
        # A new menu entry must be added to one of the lists above (or to the skipped ones).
        skipped = {"내 이름 설정", "이 캐릭터의 기억 지우기", "종료", "윈도우 시작할 때 켜기"}
        menu = self.app.menu
        labels = {menu.entrycget(i, "label") for i in range(menu.index("end") + 1) if menu.type(i) != "separator"}
        self.assertEqual(labels - set(MENU_WINDOWS) - set(MENU_ACTIONS) - skipped, set())


if __name__ == "__main__":
    unittest.main()
