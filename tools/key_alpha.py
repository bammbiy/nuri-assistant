"""Make character frames safe for the Windows colour-key window (no dark halo).

    python tools/key_alpha.py              # every frame under assets/characters/
    python tools/key_alpha.py some/folder  # or one folder (e.g. personal art)

The character window is made transparent on Windows with -transparentcolor: one colour
(#010203, almost black) is punched out and everything else is drawn opaque. A pixel that
is only partly transparent is blended with that near-black first, so soft edges become a
dark halo and the bust's bottom fade becomes a black gradient. Here alpha becomes 0 or
255: edges are cut at ALPHA_CUT (they stay crisp), and the bust's bottom fade rows are cut
off so the bust ends in one clean line (the app sits that line just above the chat box; a
dithered fade looked dirty there). Running it again changes nothing. build_frames.py applies
it to new frames.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "characters"
ALPHA_CUT = 110
FADE_ROWS = 40  # matches build_frames.clean(fade=40); full-body frames have no fade


def key_alpha(img: Image.Image, fade_rows: int = 0) -> Image.Image:
    a = np.array(img.convert("RGBA"))
    alpha = a[..., 3].astype(int)
    h, w = alpha.shape
    hard = np.where(alpha >= ALPHA_CUT, 255, 0)
    if fade_rows:
        hard[h - fade_rows:] = 0
    a[..., 3] = hard.astype(np.uint8)
    return Image.fromarray(a)


def convert_folder(folder: Path) -> int:
    count = 0
    for path in sorted(folder.rglob("*.png")):
        fade = 0 if path.parent.name == "full" else FADE_ROWS
        result = key_alpha(Image.open(path), fade)
        result.save(path, optimize=True)
        count += 1
    return count


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ASSETS
    print(f"{convert_folder(target)} frames converted in {target}")
