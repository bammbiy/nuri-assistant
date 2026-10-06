from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile


def play_wav(data: bytes) -> bool:
    """Play WAV bytes and block until done. Returns False when no audio player is available."""

    if sys.platform == "win32":
        import winsound

        winsound.PlaySound(data, winsound.SND_MEMORY)
        return True
    player = next((cmd for cmd in (["afplay"], ["paplay"], ["aplay", "-q"]) if shutil.which(cmd[0])), None)
    if player is None:
        return False
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as file:
        file.write(data)
        path = file.name
    try:
        subprocess.run([*player, path], check=False, timeout=120)
    finally:
        os.unlink(path)
    return True
