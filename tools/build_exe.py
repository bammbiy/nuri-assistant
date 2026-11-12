"""Build the Windows program folder with PyInstaller and check that it starts.

    pip install pyinstaller pillow
    python tools/build_exe.py

Result: dist/NuriAssistant/NuriAssistant.exe (with its _internal folder) and
dist/NuriAssistant-windows.zip. Python is inside, so the PC that runs it needs no Python;
Ollama (and VOICEVOX for voice) are still installed separately.
A folder instead of one big exe: a single-file exe unpacks itself to a temp folder on every
start (slow) and trips antivirus false alarms more often.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "NuriAssistant"
BUILD, DIST = ROOT / "build", ROOT / "dist"


def stage_assets() -> Path:
    """Copy what the app shows: frames and fonts, not the reference sheets the frames were cut from."""
    stage = BUILD / "assets"
    shutil.rmtree(stage, ignore_errors=True)
    shutil.copytree(ROOT / "assets", stage, ignore=shutil.ignore_patterns("reference_*", "README.md"))
    return stage


def main() -> None:
    for stream in (sys.stdout, sys.stderr):  # CI consoles are not Korean code pages
        stream.reconfigure(encoding="utf-8", errors="replace")
    stage = stage_assets()
    shutil.rmtree(DIST / NAME, ignore_errors=True)
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", NAME,
        "--paths", str(ROOT / "src"), "--add-data", f"{stage}{';' if sys.platform == 'win32' else ':'}assets",
        "--distpath", str(DIST), "--workpath", str(BUILD / "pyinstaller"), "--specpath", str(BUILD),
        str(ROOT / "src" / "run_nuri.py"),
    ], check=True)
    exe = DIST / NAME / (NAME + (".exe" if sys.platform == "win32" else ""))
    # The built program must open the character window with its art (exit code 1 and error.log if not).
    check = subprocess.run([str(exe), "--selfcheck"], timeout=180)
    if check.returncode != 0:
        sys.exit(f"빌드한 프로그램이 시작되지 않았습니다 (종료 코드 {check.returncode}). ~/.nuri-assistant/error.log를 보세요.")
    archive = shutil.make_archive(str(DIST / f"{NAME}-windows"), "zip", DIST, NAME)
    print(f"완료: {exe}\n압축: {archive}")


if __name__ == "__main__":
    main()
