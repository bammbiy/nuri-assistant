from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont

from ..paths import FONTS_DIR

BUNDLED_FONT = "NanumSquareRound"  # rounded gothic shipped in assets/fonts (OFL 1.1)


def _register_bundled_font() -> bool:
    """Make the bundled TTFs usable by name for this process only (nothing is installed).

    Windows: AddFontResourceEx with FR_PRIVATE, before any Tk font is created. Elsewhere Tk
    finds the font only if it is installed; fontconfig substitutes a similar one otherwise.
    """

    files = sorted(FONTS_DIR.glob("*.ttf"))
    if not files:
        return False
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        add = ctypes.windll.gdi32.AddFontResourceExW
        return sum(add(str(path), 0x10, 0) for path in files) > 0  # 0x10 = FR_PRIVATE
    except (AttributeError, OSError):
        return False


FONT = BUNDLED_FONT if _register_bundled_font() else ("Malgun Gothic" if sys.platform == "win32" else "TkDefaultFont")


def apply_default_fonts(root: tk.Misc) -> None:
    """Point Tk's named fonts at FONT so menus, dialogs and ttk widgets match the canvas text."""

    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont", "TkSmallCaptionFont", "TkTooltipFont"):
        try:
            tkfont.nametofont(name, root=root).configure(family=FONT)
        except tk.TclError:
            pass

BG = "#f6f2fb"
CARD = "#ffffff"
CARD_LINE = "#e6ddf4"
SHADOW = "#ebe4f6"
TEXT = "#2f2640"
SUBTLE = "#8a7d9c"
ACCENT = "#a68ae0"
ACCENT_DARK = "#8d6ad6"
TODAY = "#3fae94"
DANGER = "#e06c8a"
SOFT = "#f1ebfa"
SOFT_HOVER = "#e4d9f6"
# MomoTalk-style chat (Blue Archive's messenger): slate character bubbles, blue for the user.
MOMO_BUBBLE = "#4c5a6f"
MOMO_BUBBLE_LINE = "#3f4b5e"
MOMO_SHADOW = "#c9cfd8"
MOMO_USER = "#4a8fd4"
MOMO_PINK = "#f6849b"
MOMO_NAME = "#4c5a6f"


def round_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, r: int, **options: object) -> int:
    points = (
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
        x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    )
    return canvas.create_polygon(*points, smooth=True, **options)


def draw_pill(
    canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int,
    fill: str, outline: str = "", width: int = 1, *, tags: str | tuple[str, ...],
) -> None:
    """Fully rounded rectangle; fill parts and outline parts are separate items."""

    r = (y2 - y1) // 2
    for x, start in ((x1, 90), (x2 - 2 * r, 270)):
        canvas.create_arc(x, y1, x + 2 * r, y2, start=start, extent=180, style="pieslice", fill=fill, outline="", tags=tags)
    canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="", tags=tags)
    if not outline:
        return
    for x, start in ((x1, 90), (x2 - 2 * r, 270)):
        canvas.create_arc(x, y1, x + 2 * r, y2, start=start, extent=180, style="arc", outline=outline, width=width, tags=tags)
    for y in (y1, y2):
        canvas.create_line(x1 + r, y, x2 - r, y, fill=outline, width=width, tags=tags)


def fit(text: str, font: tuple, max_width: int) -> str:
    """Cut text to one line with an ellipsis so it never runs into the line below."""

    measure = tkfont.Font(font=font).measure
    if measure(text) <= max_width:
        return text
    while text and measure(text + "…") > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def entry(parent: tk.Misc, width: int = 20, show: str = "") -> tk.Entry:
    """Flat white input with a soft lilac border that darkens on focus."""

    return tk.Entry(
        parent, width=width, show=show, relief="flat", bd=0, font=(FONT, 10), bg=CARD, fg=TEXT,
        insertbackground=ACCENT_DARK, highlightthickness=1, highlightbackground=CARD_LINE, highlightcolor=ACCENT,
    )


def button(parent: tk.Misc, text: str, command, primary: bool = True) -> tk.Label:
    """Flat pill-ish button (a Label, so it renders the same on every platform)."""

    normal, hover, fg = (ACCENT, ACCENT_DARK, "#ffffff") if primary else (SOFT, SOFT_HOVER, TEXT)
    label = tk.Label(parent, text=text, font=(FONT, 10, "bold"), bg=normal, fg=fg, padx=14, pady=6, cursor="hand2")
    label.bind("<Button-1>", lambda _event: command())
    label.bind("<Enter>", lambda _event: label.configure(bg=hover))
    label.bind("<Leave>", lambda _event: label.configure(bg=normal))
    return label
