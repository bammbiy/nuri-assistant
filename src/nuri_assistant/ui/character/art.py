from __future__ import annotations

import math
import tkinter as tk
from pathlib import Path

ALPHA_CUT = 110  # same cut as tools/key_alpha.py
FACE_CENTER = (202, 187)  # eye midpoint in every bust frame (tools/build_frames.py EYE_OUT)
FACE_HALF = 92


class CharacterArt:
    """Finds and caches character frames: personal images first, then the bundled assets."""

    def __init__(self, master: tk.Misc, user_dir: Path, assets_dir: Path, hard_edges: bool = False) -> None:
        # hard_edges: on the Windows colour-key window a half-transparent pixel is blended with
        # the near-black key colour (dark halo), so character frames get alpha 0/255 only.
        # Bundled frames already are (tools/key_alpha.py); this covers personal art.
        self.hard_edges = hard_edges
        self.master = master
        self.user_dir = user_dir
        self.assets_dir = assets_dir
        self._images: dict[tuple[Path, tuple[int, int], bool], tk.PhotoImage | None] = {}
        self._faces: dict[tuple[str, int, str], tk.PhotoImage | None] = {}
        self._bottoms: dict[str, int] = {}

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
                image = self.load(path, box, self.hard_edges)
                if image is not None:
                    return image, has_expression
        return None, False

    def load(self, path: Path, box: tuple[int, int], hard_edges: bool = False) -> tk.PhotoImage | None:
        if (path, box, hard_edges) in self._images:
            return self._images[(path, box, hard_edges)]
        image: tk.PhotoImage | None
        try:
            from PIL import Image, ImageTk  # optional: smoother resizing when Pillow is installed

            picture = Image.open(path).convert("RGBA")
            picture.thumbnail(box, Image.LANCZOS)
            if hard_edges:
                picture.putalpha(picture.getchannel("A").point(lambda value: 255 if value >= ALPHA_CUT else 0))
            image = ImageTk.PhotoImage(picture, master=self.master)
        except ImportError:
            try:
                image = _fit_photo(tk.PhotoImage(master=self.master, file=str(path)), box)
            except (tk.TclError, ValueError):
                image = None
        except (OSError, ValueError):  # unreadable or broken personal images fall back to the placeholder
            image = None
        self._images[(path, box, hard_edges)] = image
        return image

    def content_bottom(self, image: tk.PhotoImage) -> int:
        """Height down to the lowest row with a visible pixel (bust frames end above their
        transparent bottom strip), so the caller can seat the art right on the chat box."""

        key = str(image)
        if key not in self._bottoms:
            # Raw Tcl call: works for tk.PhotoImage and Pillow's ImageTk.PhotoImage alike.
            transparent = lambda x, y: self.master.tk.getboolean(self.master.tk.call(key, "transparency", "get", x, y))
            width, height = image.width(), image.height()
            bottom = height
            for y in range(height - 1, -1, -1):
                if any(not transparent(x, y) for x in range(0, width, 3)):
                    bottom = y + 1
                    break
            self._bottoms[key] = bottom
        return self._bottoms[key]

    def face(self, persona_id: str, size: int, background: str) -> tk.PhotoImage | None:
        """Round face icon (MomoTalk style) cut from the neutral bust frame, or None.

        Bust frames put the midpoint between the eyes at FACE_CENTER, so the same square works
        for every character. Needs Pillow for the round mask; without it the log shows names only.
        """

        key = (persona_id, size, background)
        if key in self._faces:
            return self._faces[key]
        image = None
        path = self.image_path("neutral", persona_id, full=False)
        if path is not None:
            try:
                from PIL import Image, ImageDraw, ImageTk

                cx, cy, half = FACE_CENTER[0], FACE_CENTER[1] - 8, FACE_HALF
                picture = Image.open(path).convert("RGBA").crop((cx - half, cy - half, cx + half, cy + half))
                tile = Image.new("RGBA", picture.size, background)
                tile.alpha_composite(picture)
                scale = 4  # draw the circle large, then shrink: smooth edge on any Tk
                mask = Image.new("L", (size * scale, size * scale), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, size * scale - 1, size * scale - 1), fill=255)
                tile = tile.resize((size, size), Image.LANCZOS)
                tile.putalpha(mask.resize((size, size), Image.LANCZOS))
                image = ImageTk.PhotoImage(tile, master=self.master)
            except (ImportError, OSError, ValueError):
                image = None
        self._faces[key] = image
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
