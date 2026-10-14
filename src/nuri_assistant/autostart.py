"""Start with Windows: one value under HKCU\\...\\Run, off by default, nothing else written."""
from __future__ import annotations

import sys
from pathlib import Path

from . import paths

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "NuriAssistant"


def supported() -> bool:
    return sys.platform == "win32"


def launch_command(python: Path, script: Path) -> str:
    """The command line for the Run key; pythonw.exe (no console window) when it sits next to python."""

    windowless = Path(python).with_name("pythonw.exe")
    exe = windowless if windowless.exists() else Path(python)
    return f'"{exe}" "{script}" --autostart'


def _winreg(reg):
    if reg is not None:
        return reg
    import winreg  # Windows only

    return winreg


def is_enabled(reg=None) -> bool:
    reg = _winreg(reg)
    try:
        with reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_READ) as key:
            reg.QueryValueEx(key, VALUE_NAME)
        return True
    except OSError:
        return False


def set_enabled(on: bool, python: Path | None = None, script: Path | None = None, reg=None) -> None:
    """Turn it on or off. Registry errors raise OSError for the caller to report."""

    reg = _winreg(reg)
    if on:
        command = launch_command(python or Path(sys.executable), script or paths.LAUNCHER)
        with reg.CreateKey(reg.HKEY_CURRENT_USER, RUN_KEY) as key:
            reg.SetValueEx(key, VALUE_NAME, 0, reg.REG_SZ, command)
        return
    try:
        with reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_SET_VALUE) as key:
            reg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        pass
