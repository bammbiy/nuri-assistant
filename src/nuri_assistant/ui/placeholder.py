from __future__ import annotations

import tkinter as tk

from ..companion.personas import Look


SKIN = "#ffe6d5"
LINE = "#4a3030"
BLUSH = "#ffb3c1"
MOUTH = "#c0505a"
TAG = "character"

# Drawing size: 260 x 330 pixels, anchored at the top center.
PLACEHOLDER_HEIGHT = 330


def draw_placeholder(
    canvas: tk.Canvas,
    cx: int,
    top: int,
    look: Look,
    expression: str,
    talking: bool = False,
    blinking: bool = False,
) -> None:
    """Draw a simple chibi stand-in so the app works before character art exists."""

    canvas.delete(TAG)
    _back_hair(canvas, cx, top, look)
    _body(canvas, cx, top, look)
    canvas.create_oval(cx - 76, top + 30, cx + 76, top + 196, fill=SKIN, outline=LINE, width=2, tags=TAG)
    _eyes(canvas, cx, top, look, expression, blinking)
    if expression in {"shy", "happy"}:
        for side in (-1, 1):
            x = cx + side * 48
            canvas.create_oval(x - 14, top + 150, x + 14, top + 160, fill=BLUSH, outline="", tags=TAG)
    _mouth(canvas, cx, top, expression, talking)
    _bangs(canvas, cx, top, look)
    # Anime convention: brows stay visible through the bangs.
    _brows(canvas, cx, top, look, expression)
    _accessory(canvas, cx, top, look)


def _back_hair(canvas: tk.Canvas, cx: int, top: int, look: Look) -> None:
    hair = look.hair
    style = look.hairstyle
    if style == "long":
        canvas.create_oval(cx - 96, top + 14, cx + 96, top + 320, fill=hair, outline=LINE, width=2, tags=TAG)
        return
    if style == "twintails":
        for side in (-1, 1):
            x = cx + side * 112
            canvas.create_oval(x - 30, top + 60, x + 30, top + 300, fill=hair, outline=LINE, width=2, tags=TAG)
    if style == "ponytail":
        canvas.create_oval(cx + 50, top + 30, cx + 122, top + 270, fill=hair, outline=LINE, width=2, tags=TAG)
    if style == "drills":
        for side in (-1, 1):
            x = cx + side * 100
            for index in range(4):
                y = top + 120 + index * 42
                canvas.create_oval(x - 22, y, x + 22, y + 50, fill=hair, outline=LINE, width=2, tags=TAG)
                canvas.create_arc(x - 16, y + 8, x + 16, y + 42, start=200, extent=140, style="arc", outline=LINE, tags=TAG)
    bottom = top + 215 if style == "short" else top + 190
    canvas.create_oval(cx - 90, top + 14, cx + 90, bottom, fill=hair, outline=LINE, width=2, tags=TAG)


def _body(canvas: tk.Canvas, cx: int, top: int, look: Look) -> None:
    canvas.create_rectangle(cx - 13, top + 185, cx + 13, top + 210, fill=SKIN, outline=LINE, tags=TAG)
    canvas.create_polygon(
        cx - 50, top + 205, cx + 50, top + 205, cx + 92, top + 330, cx - 92, top + 330,
        fill=look.outfit, outline=LINE, width=2, tags=TAG,
    )
    if look.accessory == "headdress":
        # Maid apron and collar.
        canvas.create_polygon(
            cx - 34, top + 240, cx + 34, top + 240, cx + 52, top + 330, cx - 52, top + 330,
            fill="#ffffff", outline=LINE, tags=TAG,
        )
    canvas.create_polygon(
        cx - 30, top + 205, cx, top + 232, cx + 30, top + 205,
        fill="#ffffff", outline=LINE, tags=TAG,
    )


def _eyes(canvas: tk.Canvas, cx: int, top: int, look: Look, expression: str, blinking: bool) -> None:
    eye_y = top + 122
    for side in (-1, 1):
        x = cx + side * 30
        if blinking or expression == "happy":
            if expression == "happy":
                canvas.create_line(x - 14, eye_y + 6, x, eye_y - 8, x + 14, eye_y + 6, width=3, fill=LINE, smooth=True, tags=TAG)
            else:
                canvas.create_line(x - 14, eye_y + 2, x, eye_y + 8, x + 14, eye_y + 2, width=3, fill=LINE, smooth=True, tags=TAG)
            continue
        white_rx, white_ry = (17, 23) if expression == "surprised" else (15, 20)
        canvas.create_oval(x - white_rx, eye_y - white_ry, x + white_rx, eye_y + white_ry, fill="#ffffff", outline=LINE, width=2, tags=TAG)
        dx, dy = {"thinking": (5, -5), "shy": (-6, 3), "sad": (0, 4)}.get(expression, (0, 0))
        iris_rx, iris_ry = (7, 10) if expression == "surprised" else (11, 16)
        ix, iy = x + dx, eye_y + dy + 2
        canvas.create_oval(ix - iris_rx, iy - iris_ry, ix + iris_rx, iy + iris_ry, fill=look.eyes, outline="", tags=TAG)
        canvas.create_oval(ix - 4, iy - 5, ix + 4, iy + 5, fill="#1d1420", outline="", tags=TAG)
        canvas.create_oval(ix - 7, iy - 11, ix - 1, iy - 5, fill="#ffffff", outline="", tags=TAG)
        canvas.create_line(x - white_rx - 2, eye_y - white_ry + 4, x, eye_y - white_ry - 2, x + white_rx + 2, eye_y - white_ry + 4,
                           width=4, fill=LINE, smooth=True, tags=TAG)


def _brows(canvas: tk.Canvas, cx: int, top: int, look: Look, expression: str) -> None:
    y = top + 92
    for side in (-1, 1):
        inner, outer = cx + side * 14, cx + side * 44
        inner_dy, outer_dy = {
            "angry": (8, -4),
            "sad": (-6, 4),
            "surprised": (-6, -6),
            "thinking": (-6, 0) if side > 0 else (2, 2),
        }.get(expression, (0, 0))
        canvas.create_line(inner, y + inner_dy, outer, y + outer_dy, width=3, fill=LINE, tags=TAG)


def _mouth(canvas: tk.Canvas, cx: int, top: int, expression: str, talking: bool) -> None:
    y = top + 165
    if talking:
        canvas.create_oval(cx - 8, y - 6, cx + 8, y + 8, fill=MOUTH, outline=LINE, width=2, tags=TAG)
        return
    if expression == "happy":
        canvas.create_arc(cx - 14, y - 12, cx + 14, y + 12, start=180, extent=180, style="chord", fill=MOUTH, outline=LINE, width=2, tags=TAG)
    elif expression == "surprised":
        canvas.create_oval(cx - 6, y - 6, cx + 6, y + 8, fill=MOUTH, outline=LINE, width=2, tags=TAG)
    elif expression == "sad":
        canvas.create_arc(cx - 10, y, cx + 10, y + 14, start=20, extent=140, style="arc", outline=LINE, width=2, tags=TAG)
    elif expression == "angry":
        canvas.create_line(cx - 10, y + 4, cx - 4, y, cx + 2, y + 4, cx + 10, y, width=2, fill=LINE, tags=TAG)
    elif expression == "shy":
        canvas.create_line(cx - 10, y + 2, cx - 4, y - 2, cx + 2, y + 2, cx + 8, y - 2, width=2, fill=LINE, smooth=True, tags=TAG)
    elif expression == "thinking":
        canvas.create_line(cx - 6, y + 2, cx + 8, y - 2, width=2, fill=LINE, tags=TAG)
    else:
        canvas.create_arc(cx - 9, y - 8, cx + 9, y + 6, start=200, extent=140, style="arc", outline=LINE, width=2, tags=TAG)


def _bangs(canvas: tk.Canvas, cx: int, top: int, look: Look) -> None:
    points = (
        cx - 82, top + 120, cx - 84, top + 70, cx - 58, top + 32, cx - 20, top + 16, cx + 20, top + 16,
        cx + 58, top + 32, cx + 84, top + 70, cx + 82, top + 120, cx + 66, top + 82, cx + 52, top + 100,
        cx + 38, top + 66, cx + 16, top + 94, cx, top + 62, cx - 16, top + 94, cx - 38, top + 66,
        cx - 52, top + 100, cx - 66, top + 82,
    )
    canvas.create_polygon(*points, fill=look.hair, outline=LINE, width=2, tags=TAG)
    if look.hairstyle in {"long", "short"}:
        for side in (-1, 1):
            canvas.create_polygon(
                cx + side * 82, top + 80, cx + side * 72, top + 205, cx + side * 62, top + 110,
                fill=look.hair, outline=LINE, width=2, tags=TAG,
            )


def _accessory(canvas: tk.Canvas, cx: int, top: int, look: Look) -> None:
    kind = look.accessory
    if kind == "ribbon":
        for side in (-1, 1):
            x = cx + side * 100
            canvas.create_polygon(x, top + 66, x - 22, top + 50, x - 22, top + 82, fill="#222244", outline=LINE, tags=TAG)
            canvas.create_polygon(x, top + 66, x + 22, top + 50, x + 22, top + 82, fill="#222244", outline=LINE, tags=TAG)
    elif kind == "hairpin":
        canvas.create_line(cx - 62, top + 52, cx - 36, top + 40, width=4, fill="#f2d16b", tags=TAG)
        canvas.create_line(cx - 60, top + 60, cx - 34, top + 48, width=4, fill="#f2d16b", tags=TAG)
    elif kind == "scrunchie":
        canvas.create_oval(cx + 66, top + 30, cx + 96, top + 58, fill="#ff6f91", outline=LINE, width=2, tags=TAG)
    elif kind == "headdress":
        canvas.create_polygon(cx - 70, top + 34, cx + 70, top + 34, cx + 60, top + 18, cx - 60, top + 18,
                              fill="#ffffff", outline=LINE, tags=TAG)
        for index in range(7):
            x = cx - 60 + index * 20
            canvas.create_oval(x - 10, top + 8, x + 10, top + 24, fill="#ffffff", outline=LINE, tags=TAG)
    elif kind == "tiara":
        canvas.create_polygon(
            cx - 40, top + 26, cx - 30, top + 4, cx - 15, top + 20, cx, top - 4, cx + 15, top + 20, cx + 30, top + 4, cx + 40, top + 26,
            fill="#f5d061", outline=LINE, width=2, tags=TAG,
        )
        canvas.create_oval(cx - 5, top + 8, cx + 5, top + 18, fill="#e0457b", outline="", tags=TAG)
