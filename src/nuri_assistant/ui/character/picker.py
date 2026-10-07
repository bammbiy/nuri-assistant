from __future__ import annotations

import tkinter as tk
from typing import Callable, Iterable

from ...companion import Persona
from ..theme import ACCENT, ACCENT_DARK, BG, CARD, FONT, TEXT
from .placeholder import PLACEHOLDER_HEIGHT, TAG as PLACEHOLDER_TAG, draw_placeholder


# Slightly cooler than theme's CARD_LINE/SUBTLE; kept so the picker looks exactly as before.
CARD_LINE = "#e4dcf2"
SUBTLE = "#7d7090"
THUMB = (190, 150)
COLUMNS = 4


class CharacterPicker(tk.Toplevel):
    """Start-up screen for choosing which secretary to work with."""

    def __init__(
        self,
        master: tk.Misc,
        personas: Iterable[Persona],
        current_id: str,
        load_thumbnail: Callable[[Persona, tuple[int, int]], tk.PhotoImage | None],
        on_pick: Callable[[str, bool], None],
        remember: bool = False,
    ) -> None:
        super().__init__(master)
        # Registered first: if building the cards fails, closing still starts the app.
        self.protocol("WM_DELETE_WINDOW", lambda: self._pick(self.current_id))
        self.bind("<Escape>", lambda _event: self._pick(self.current_id))
        self.title("비서 선택")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.current_id = current_id
        self.on_pick = on_pick
        self.remember_var = tk.BooleanVar(value=remember)
        self._thumbnails: list[tk.PhotoImage] = []
        self._done = False

        tk.Label(self, text="오늘 함께할 비서를 골라 주세요", font=(FONT, 16, "bold"), bg=BG, fg=TEXT).pack(pady=(22, 2))
        tk.Label(self, text="카드를 누르면 바로 시작해요.", font=(FONT, 10), bg=BG, fg=SUBTLE).pack(pady=(0, 14))

        grid = tk.Frame(self, bg=BG)
        grid.pack(padx=22)
        for index, persona in enumerate(personas):
            card = self._card(grid, persona, load_thumbnail)
            card.grid(row=index // COLUMNS, column=index % COLUMNS, padx=7, pady=7, sticky="nsew")
        for column in range(COLUMNS):
            grid.columnconfigure(column, uniform="card")

        footer = tk.Frame(self, bg=BG)
        footer.pack(fill="x", padx=29, pady=(10, 20))
        tk.Checkbutton(
            footer, text="다음부터 이 화면 없이 마지막 비서로 바로 시작", variable=self.remember_var,
            font=(FONT, 10), bg=BG, fg=TEXT, activebackground=BG, selectcolor=CARD, highlightthickness=0,
        ).pack(side="left")
        tk.Label(footer, text="메뉴 ⋯ > 비서 선택에서 언제든 바꿀 수 있어요", font=(FONT, 9), bg=BG, fg=SUBTLE).pack(side="right")

        self._center()
        self.focus_force()

    def _card(self, parent: tk.Misc, persona: Persona, load_thumbnail) -> tk.Frame:
        card = tk.Frame(parent, bg=CARD, highlightthickness=2, highlightbackground=CARD_LINE, cursor="hand2")
        thumb = tk.Canvas(card, width=THUMB[0], height=THUMB[1], bg=CARD, highlightthickness=0)
        thumb.pack(padx=8, pady=(8, 4))
        image = load_thumbnail(persona, THUMB)
        if image is not None:
            self._thumbnails.append(image)
            thumb.create_image(THUMB[0] // 2, THUMB[1], anchor="s", image=image)
        else:
            scale = (THUMB[1] - 8) / PLACEHOLDER_HEIGHT
            draw_placeholder(thumb, round(THUMB[0] / 2 / scale), round(8 / scale), persona.look, "happy")
            thumb.scale(PLACEHOLDER_TAG, 0, 0, scale, scale)

        title = tk.Frame(card, bg=CARD)
        title.pack(fill="x", padx=12)
        tk.Label(title, text=persona.name, font=(FONT, 13, "bold"), bg=CARD, fg=TEXT).pack(side="left")
        if persona.id == self.current_id:
            tk.Label(title, text="지난번 비서", font=(FONT, 8, "bold"), bg="#efe8fb", fg=ACCENT_DARK, padx=6).pack(side="right")
        tk.Label(card, text=persona.archetype, font=(FONT, 10, "bold"), bg=CARD, fg=ACCENT_DARK, anchor="w").pack(fill="x", padx=12)
        tagline = persona.summary.split(". ")[0].rstrip(".") + "."
        tk.Label(
            card, text=tagline, font=(FONT, 9), bg=CARD, fg=SUBTLE, anchor="nw", justify="left",
            wraplength=THUMB[0], height=3,
        ).pack(fill="x", padx=12, pady=(2, 10))

        widgets = [card, *card.winfo_children(), *title.winfo_children()]
        for widget in widgets:
            widget.bind("<Button-1>", lambda _event, persona_id=persona.id: self._pick(persona_id))
            widget.bind("<Enter>", lambda _event: card.configure(highlightbackground=ACCENT))
            widget.bind("<Leave>", lambda _event: card.configure(highlightbackground=CARD_LINE))
        return card

    def _center(self) -> None:
        self.update_idletasks()
        width, height = self.winfo_reqwidth(), self.winfo_reqheight()
        x = max((self.winfo_screenwidth() - width) // 2, 0)
        y = max((self.winfo_screenheight() - height) // 2 - 20, 0)
        self.geometry(f"+{x}+{y}")

    def _pick(self, persona_id: str) -> None:
        if self._done:
            return
        self._done = True
        remember = self.remember_var.get()
        self.destroy()
        self.on_pick(persona_id, remember)
