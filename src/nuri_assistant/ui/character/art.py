from __future__ import annotations

import math
import tkinter as tk
from pathlib import Path


class CharacterArt:
    """Finds and caches character frames: personal images first, then the bundled assets."""

    def __init__(self, master: tk.Misc, user_dir: Path, assets_dir: Path) -> None:
        self.master = master
        self.user_dir = user_dir
        self.assets_dir = assets_dir
        self._images: dict[tuple[Path, tuple[int, int]], tk.PhotoImage | None] = {}

    def art_dirs(self, persona_id: str, full: bool) -> list[Path]:
        """Where frames are looked up; full-body art is used only when it exists, never mixed."""

        bases = [self.user_dir / persona_id, self.assets_dir / persona_id]
        if full and any((base / "full" / "neutral.png").exists() for base in bases):
            return [base / "full" for base in bases]
        return bases

    def image_path(self, name: str, persona_id: str, full: bool) -> Path | None:
        for folder in self.art_dirs(persona_id, full):
            path = folder / f"{name}.png"
            if path.exists():
                return path
        return None

    def frame(self, persona_id: str, expression: str, talking: bool, blinking: bool, full: bool,
              box: tuple[int, int]) -> tuple[tk.PhotoImage | None, bool]:
        """Return the frame to show and whether the expression itself has art.

        A missing expression falls back to neutral; its talk/blink variants still
        animate, and the caller adds an emote mark so the mood stays readable.
        """

        has_expression = self.image_path(expression, persona_id, full) is not None
        base = expression if has_expression else "neutral"
        names = ([f"{base}_talk"] if talking else []) + ([f"{base}_blink"] if blinking else []) + [base]
        for name in names:
            path = self.image_path(name, persona_id, full)
            if path is not None:
                image = self.load(path, box)
                if image is not None:
                    return image, has_expression
        return None, False

    def load(self, path: Path, box: tuple[int, int]) -> tk.PhotoImage | None:
        if (path, box) in self._images:
            return self._images[(path, box)]
        image: tk.PhotoImage | None
        try:
            from PIL import Image, ImageTk  # optional: smoother resizing when Pillow is installed

            picture = Image.open(path).convert("RGBA")
            picture.thumbnail(box, Image.LANCZOS)
            image = ImageTk.PhotoImage(picture, master=self.master)
        except ImportError:
            try:
                image = _fit_photo(tk.PhotoImage(master=self.master, file=str(path)), box)
            except (tk.TclError, ValueError):
                image = None
        except (OSError, ValueError):  # unreadable or broken personal images fall back to the placeholder
            image = None
        self._images[(path, box)] = image
        return image


def _fit_photo(image: tk.PhotoImage, box: tuple[int, int]) -> tk.PhotoImage:
    """Scale into box with Tk's integer zoom/subsample (used when Pillow is absent)."""

    target = min(box[0] / image.width(), box[1] / image.height(), 1.0)
    if target >= 1.0:
        return image
    ratios = [(z, s) for s in range(1, 7) for z in range(1, s + 1) if z / s <= target]
    if not ratios:  # shrinking more than 6x: plain subsample
        return image.subsample(math.ceil(1 / target))
    zoom, sub = max(ratios, key=lambda pair: pair[0] / pair[1])
    if zoom > 1:
        image = image.zoom(zoom)
    return image.subsample(sub) if sub > 1 else image
