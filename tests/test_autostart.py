from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.nuri_assistant import autostart, paths


class FakeReg:
    HKEY_CURRENT_USER = "HKCU"
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def _key(self, root, sub):
        class Key:
            def __enter__(s):
                return (root, sub)

            def __exit__(s, *a):
                return False

        return Key()

    def CreateKey(self, root, sub):
        return self._key(root, sub)

    def OpenKey(self, root, sub, reserved=0, access=0):
        if not any(k[0] == sub for k in self.values) and access == self.KEY_SET_VALUE:
            raise FileNotFoundError(sub)
        return self._key(root, sub)

    def SetValueEx(self, key, name, reserved, kind, value):
        self.values[(key[1], name)] = value

    def QueryValueEx(self, key, name):
        if (key[1], name) not in self.values:
            raise FileNotFoundError(name)
        return self.values[(key[1], name)], self.REG_SZ

    def DeleteValue(self, key, name):
        if (key[1], name) not in self.values:
            raise FileNotFoundError(name)
        del self.values[(key[1], name)]


class AutostartTest(unittest.TestCase):
    def test_launcher_exists(self) -> None:
        self.assertTrue(paths.LAUNCHER.exists())

    def test_enable_disable(self) -> None:
        reg = FakeReg()
        self.assertFalse(autostart.is_enabled(reg))
        autostart.set_enabled(True, Path("C:/Py/python.exe"), Path("C:/n/run_nuri.py"), reg)
        self.assertTrue(autostart.is_enabled(reg))
        command = reg.values[(autostart.RUN_KEY, autostart.VALUE_NAME)]
        self.assertEqual(command, autostart.launch_command(Path("C:/Py/python.exe"), Path("C:/n/run_nuri.py")))
        self.assertEqual(len(reg.values), 1)
        autostart.set_enabled(False, reg=reg)
        self.assertFalse(autostart.is_enabled(reg))
        autostart.set_enabled(False, reg=reg)  # already gone is fine

    def test_launch_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "my python"
            folder.mkdir()
            python = folder / "python.exe"
            script = folder / "run nuri.py"
            plain = autostart.launch_command(python, script)
            self.assertEqual(plain, f'"{python}" "{script}" --autostart')
            (folder / "pythonw.exe").write_text("", encoding="utf-8")
            windowless = autostart.launch_command(python, script)
            self.assertEqual(windowless, f'"{folder / "pythonw.exe"}" "{script}" --autostart')


if __name__ == "__main__":
    unittest.main()
