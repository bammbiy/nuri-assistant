from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from src.nuri_assistant import __version__
from src.nuri_assistant.app import main
from src.nuri_assistant.paths import ASSETS_DIR

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}  # Korean help text on a cp949 Windows console
    return subprocess.run([sys.executable, *args], cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)


class EntryPointTest(unittest.TestCase):
    def test_bundled_art_is_found(self) -> None:
        # paths.py climbs a fixed number of folders to reach assets/; this breaks if it moves.
        self.assertTrue(callable(main))
        self.assertTrue((ASSETS_DIR / "nuri").is_dir(), ASSETS_DIR)

    def test_version_matches_pyproject(self) -> None:
        self.assertIn(f'version = "{__version__}"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    def test_launchers_parse_arguments_without_tkinter(self) -> None:
        # --help exits before tkinter or any window is touched, so this runs headless.
        for args, cwd in ((["src/run_nuri.py", "--help"], ROOT), (["-m", "nuri_assistant", "--help"], ROOT / "src")):
            with self.subTest(args=args):
                result = _run(*args, cwd=cwd)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("--classic", result.stdout)

    def test_importing_the_entry_module_does_not_load_the_ui(self) -> None:
        code = "import sys, nuri_assistant.app; print(any(m.startswith(('tkinter', 'nuri_assistant.ui')) for m in sys.modules))"
        result = _run("-c", code, cwd=ROOT / "src")
        self.assertEqual(result.stdout.strip(), "False", result.stderr)


if __name__ == "__main__":
    unittest.main()
