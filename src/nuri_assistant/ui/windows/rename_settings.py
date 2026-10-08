from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path
from typing import Callable

from ...classic.core import (
    DEFAULT_EXTENSIONS, RULE_TOKENS, RenameError, RenameInput, build_file_name, normalize_media, rule_from_korean,
    rule_to_korean, rule_uses_media, validate_rule,
)
from ...companion import CompanionSettings
from ..theme import ACCENT_DARK, BG, DANGER, FONT, SOFT, SOFT_HOVER, SUBTLE, TEXT, TODAY, button, entry

PRESETS = ("{날짜}_{매체}_{페이지}", "{매체}-{날짜}-{페이지}", "{날짜}-{매체}-p{페이지}", "{연도}-{월}-{일}_{페이지}")
EXAMPLE_MEDIA = "ja00"


def parse_extensions(text: str) -> list[str]:
    """'pdf, .HWP  jpg' -> ['.pdf', '.hwp', '.jpg']"""

    words = text.replace(",", " ").split()
    return list(dict.fromkeys("." + word.lower().lstrip(".") for word in words if word.strip(".")))


class RenameSettingsWindow(tk.Toplevel):
    """Name rule, default media code, file types and skip-done option for renaming files from chat."""

    def __init__(self, master: tk.Misc, settings: CompanionSettings, on_save: Callable[..., None]) -> None:
        super().__init__(master)
        self.title("파일 정리 설정")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.on_save = on_save

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=20)
        tk.Label(body, text="파일 정리 설정", font=(FONT, 16, "bold"), bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(body, text="비서에게 \"다운로드 폴더 이름 정리해줘\"라고 할 때 쓰는 규칙이에요.",
                 font=(FONT, 9), bg=BG, fg=SUBTLE).pack(anchor="w", pady=(2, 12))

        self._label(body, "이름 형식", "칸을 눌러 넣거나 직접 고쳐 쓰세요. {페이지}는 꼭 있어야 해요.")
        self.rule = entry(body, width=44)
        self.rule.insert(0, rule_to_korean(settings.rename_rule))
        self.rule.pack(fill="x", ipady=5)
        self.rule.bind("<KeyRelease>", lambda _event: self._update_example())
        self._chips(body, [("{" + name + "}", self._insert) for name in RULE_TOKENS.values()])
        tk.Label(body, text="자주 쓰는 형식", font=(FONT, 9), bg=BG, fg=SUBTLE).pack(anchor="w", pady=(6, 0))
        self._chips(body, [(preset, self._use_preset) for preset in PRESETS])
        self.example = tk.Label(body, font=(FONT, 10, "bold"), bg=BG, anchor="w", justify="left", wraplength=420)
        self.example.pack(fill="x", pady=(8, 4))

        self._label(body, "기본 매체코드", "말로 안 하면 이 코드를 써요. 비워 두면 매번 물어봐요. (예: ja00)")
        self.media = entry(body, width=10)
        self.media.insert(0, settings.rename_media)
        self.media.pack(anchor="w", ipady=5)
        self.media.bind("<KeyRelease>", lambda _event: self._update_example())

        self._label(body, "정리할 파일 종류", "확장자를 쉼표나 띄어쓰기로 나눠 적어요.")
        self.extensions = entry(body, width=44)
        self.extensions.insert(0, ", ".join(ext.lstrip(".") for ext in settings.rename_extensions))
        self.extensions.pack(fill="x", ipady=5)

        self.skip_named = tk.BooleanVar(value=settings.rename_skip_named)
        tk.Checkbutton(body, text="이미 이 형식으로 된 파일은 그대로 두고, 번호는 그 뒤부터 이어 붙이기",
                       variable=self.skip_named, font=(FONT, 10), bg=BG, fg=TEXT, activebackground=BG,
                       selectcolor="#ffffff", highlightthickness=0, bd=0, anchor="w").pack(fill="x", pady=(14, 0))

        self.notice = tk.Label(body, text="", font=(FONT, 9), bg=BG, fg=DANGER, anchor="w")
        self.notice.pack(fill="x", pady=(8, 0))
        actions = tk.Frame(body, bg=BG)
        actions.pack(fill="x", pady=(8, 0))
        button(actions, "저장", self._save).pack(side="right")
        button(actions, "취소", self.destroy, primary=False).pack(side="right", padx=6)
        button(actions, "기본값", self._reset, primary=False).pack(side="left")
        self.bind("<Escape>", lambda _event: self.destroy())
        self._update_example()

    # ----- building blocks ------------------------------------------------------------

    def _label(self, parent: tk.Misc, title: str, hint: str) -> None:
        tk.Label(parent, text=title, font=(FONT, 11, "bold"), bg=BG, fg=TEXT).pack(anchor="w", pady=(12, 0))
        tk.Label(parent, text=hint, font=(FONT, 9), bg=BG, fg=SUBTLE).pack(anchor="w", pady=(0, 4))

    def _chips(self, parent: tk.Misc, items: list[tuple[str, Callable[[str], None]]]) -> None:
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=(4, 0))
        for text, command in items:
            chip = tk.Label(row, text=text, font=(FONT, 9), bg=SOFT, fg=ACCENT_DARK, padx=8, pady=3, cursor="hand2")
            chip.pack(side="left", padx=(0, 4))
            chip.bind("<Button-1>", lambda _event, value=text, run=command: run(value))
            chip.bind("<Enter>", lambda _event, widget=chip: widget.configure(bg=SOFT_HOVER))
            chip.bind("<Leave>", lambda _event, widget=chip: widget.configure(bg=SOFT))

    def _insert(self, token: str) -> None:
        self.rule.insert("insert", token)
        self.rule.focus_set()
        self._update_example()

    def _use_preset(self, preset: str) -> None:
        self.rule.delete(0, "end")
        self.rule.insert(0, preset)
        self._update_example()

    def _reset(self) -> None:
        defaults = CompanionSettings()
        self._use_preset(rule_to_korean(defaults.rename_rule))
        self.media.delete(0, "end")
        self.extensions.delete(0, "end")
        self.extensions.insert(0, ", ".join(ext.lstrip(".") for ext in DEFAULT_EXTENSIONS))
        self.skip_named.set(defaults.rename_skip_named)
        self._update_example()

    # ----- checking and saving --------------------------------------------------------

    def _check(self) -> tuple[str, str]:
        """(rule, media) as saved, or RenameError with a message for the user."""

        rule = rule_from_korean(self.rule.get())
        validate_rule(rule)
        media = self.media.get().strip()
        return rule, normalize_media(media) if media else ""

    def _update_example(self) -> None:
        try:
            rule, media = self._check()
            sample = RenameInput(Path("스캔.pdf"), datetime.now().strftime("%Y%m%d"), media or EXAMPLE_MEDIA, "1", rule)
            text, color = f"예: 스캔.pdf → {build_file_name(sample)}", TODAY
            if rule_uses_media(rule) and not media:
                text += f"  (매체코드 {EXAMPLE_MEDIA}는 예시)"
        except (RenameError, ValueError, KeyError, IndexError) as exc:
            text, color = str(exc) or "이름 형식을 확인해 주세요.", DANGER
        self.example.configure(text=text, fg=color)

    def _save(self) -> None:
        try:
            rule, media = self._check()
        except (RenameError, ValueError, KeyError, IndexError) as exc:
            self.notice.configure(text=str(exc) or "이름 형식을 확인해 주세요.")
            return
        extensions = parse_extensions(self.extensions.get())
        if not extensions:
            self.notice.configure(text="정리할 파일 종류를 하나 이상 적어 주세요.")
            return
        self.on_save(rename_rule=rule, rename_media=media, rename_extensions=extensions,
                     rename_skip_named=self.skip_named.get())
        self.destroy()
