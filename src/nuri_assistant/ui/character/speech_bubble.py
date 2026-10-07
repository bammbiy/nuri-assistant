from __future__ import annotations

import tkinter as tk

from ..theme import FONT, TEXT, draw_pill, round_rect

TAG = "bubble"
BUBBLE_FONT = (FONT, 11)
BUBBLE_LINE = "#c9b6ea"
BUBBLE_SHADOW = "#e7def5"
BUBBLE_PLATE = "#9b7fdc"
# Long text is trimmed from the front until the bubble's top stays below this y.
MIN_TOP = 34


class SpeechBubble:
    """Visual-novel style bubble above the character's head, with a name plate.

    A bubble may carry a link (price alerts); the owner opens take_link() when it is clicked.
    Showing different text drops the link.
    """

    def __init__(self, canvas: tk.Canvas, width: int) -> None:
        self.canvas = canvas
        self.width = width
        self.text = ""
        self.link = ""

    def take_link(self) -> str:
        link, self.link = self.link, ""
        return link

    def hide(self) -> None:
        self.canvas.delete(TAG)

    def show(self, text: str, head_top: int, name: str) -> None:
        self.hide()
        if text != self.text:
            self.link = ""
        self.text = text
        if not text:
            return
        canvas = self.canvas
        cx, bottom = self.width // 2, head_top - 18
        item = canvas.create_text(cx, bottom, text=text, width=self.width - 64, anchor="s", font=BUBBLE_FONT,
                                  fill=TEXT, justify="left", tags=TAG)
        # Long replies keep their latest part visible; the full text is in the chat log.
        shown = text
        while canvas.bbox(item)[1] < MIN_TOP and len(shown) > 20:
            shown = shown[max(len(shown) // 10, 1):]
            canvas.itemconfigure(item, text="…" + shown.lstrip())

        # Name plate on the top-left edge.
        plate = canvas.create_text(0, 0, text=name, font=(BUBBLE_FONT[0], 9, "bold"), fill="#ffffff", tags=TAG)
        plate_w = canvas.bbox(plate)[2] - canvas.bbox(plate)[0] + 22
        x1, y1, x2, y2 = canvas.bbox(item)
        pad_x, pad_top, pad_bottom = 16, 16, 12
        bx1, by1, bx2, by2 = x1 - pad_x, y1 - pad_top, x2 + pad_x, y2 + pad_bottom
        if bx2 - bx1 < plate_w + 40:
            grow = (plate_w + 40 - (bx2 - bx1)) // 2 + 1
            bx1, bx2 = bx1 - grow, bx2 + grow

        round_rect(canvas, bx1, by1 + 3, bx2, by2 + 3, 16, fill=BUBBLE_SHADOW, outline="", tags=TAG)
        canvas.create_polygon(cx - 9, by2 - 2, cx + 9, by2 - 2, cx + 3, head_top + 4,
                              fill="#ffffff", outline=BUBBLE_LINE, width=2, tags=TAG)
        round_rect(canvas, bx1, by1, bx2, by2, 16, fill="#ffffff", outline=BUBBLE_LINE, width=2, tags=TAG)
        # Open the outline where the tail joins the bubble.
        canvas.create_line(cx - 7, by2, cx + 8, by2, fill="#ffffff", width=3, tags=TAG)
        draw_pill(canvas, bx1 + 14, by1 - 11, bx1 + 14 + plate_w, by1 + 11, fill=BUBBLE_PLATE, tags=TAG)
        canvas.coords(plate, bx1 + 14 + plate_w / 2, by1)
        canvas.tag_raise(plate)
        canvas.tag_raise(item)
