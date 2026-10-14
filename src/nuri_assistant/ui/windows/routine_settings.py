from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from typing import Callable

from ...companion import CompanionSettings
from ...fun import parse_birthday
from ...routine import parse_clock
from ...weather import WeatherError, geocode
from ..theme import BG, DANGER, FONT, SUBTLE, TEXT, button, entry

POLL_MS = 100
MAX_BODY_HEIGHT = 580
CHATTER_CHOICES = ("많이", "보통", "조금", "끄기")
NOTIFY_CHOICES = (
    ("notify_welcome", "돌아왔을 때 인사"),
    ("notify_level_up", "친해졌을 때 한마디"),
    ("notify_occasion", "생일·기념일 축하"),
    ("fullscreen_quiet", "전체 화면(게임·영상)일 때는 조용히, 위로 올라오지도 않기"),
)


class RoutineSettingsWindow(tk.Toplevel):
    """Morning briefing time and weather city, evening wrap-up time, and away / break / water reminders."""

    def __init__(self, master: tk.Misc, settings: CompanionSettings, on_save: Callable[..., None]) -> None:
        super().__init__(master)
        self.title("생활 알림 설정")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.settings = settings
        self.on_save = on_save
        self._results: queue.Queue = queue.Queue()

        # Scrollable middle so the window fits small screens; buttons stay pinned below.
        outer = tk.Frame(self, bg=BG)
        outer.pack(side="bottom", fill="x", padx=24, pady=(0, 16))
        self._canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._bar = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._bar.set)
        body = tk.Frame(self._canvas, bg=BG)
        self._canvas.create_window((24, 20), window=body, anchor="nw")
        body.bind("<Configure>", self._fit_body)
        tk.Label(body, text="생활 알림 설정", font=(FONT, 16, "bold"), bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(body, text="비서가 먼저 말을 거는 때를 정해요. 시각은 08:30처럼 적어요.",
                 font=(FONT, 9), bg=BG, fg=SUBTLE).pack(anchor="w", pady=(2, 6))

        self._section(body, "하루 루틴")
        self.briefing = self._row(body, "아침 브리핑", settings.briefing_time, "비우면 앱을 켤 때")
        self.wrapup = self._row(body, "하루 정리", settings.wrapup_time, "비우면 끔")
        self.city = self._row(body, "날씨 도시", settings.weather_city, "예: 서울, 부산 (비우면 날씨 없음)", width=14)
        month, _, day = settings.user_birthday.partition("-")
        birthday = f"{int(month)}월 {int(day)}일" if month.isdigit() and day.isdigit() else ""
        self.birthday = self._row(body, "내 생일", birthday, "예: 3월 14일 (그날 비서가 축하해요)", width=10)

        self._section(body, "먼저 말 걸기")
        chatter_row = tk.Frame(body, bg=BG)
        chatter_row.pack(fill="x", pady=3)
        tk.Label(chatter_row, text="혼잣말 빈도", width=12, anchor="w", font=(FONT, 10), bg=BG, fg=TEXT).pack(side="left")
        self.chatter = tk.StringVar(value=settings.chatter)
        for label in CHATTER_CHOICES:
            tk.Radiobutton(chatter_row, text=label, value=label, variable=self.chatter, font=(FONT, 10), bg=BG, fg=TEXT,
                           activebackground=BG, selectcolor="#ffffff", highlightthickness=0, bd=0).pack(side="left", padx=(0, 8))
        tk.Label(body, text="가만히 있을 때 가끔 혼잣말을 해요. 일정·할 일·타이머 알림은 빈도와 상관없이 꼭 알려요.",
                 font=(FONT, 9), bg=BG, fg=SUBTLE, wraplength=460, justify="left").pack(anchor="w", pady=(0, 4))
        self.notify_vars: dict[str, tk.BooleanVar] = {}
        for key, text in NOTIFY_CHOICES:
            var = tk.BooleanVar(value=bool(getattr(settings, key)))
            self.notify_vars[key] = var
            tk.Checkbutton(body, text=text, variable=var, font=(FONT, 10), bg=BG, fg=TEXT, activebackground=BG,
                           selectcolor="#ffffff", highlightthickness=0, bd=0, anchor="w").pack(fill="x")

        self._section(body, "자리 비움·건강")
        self.presence = tk.BooleanVar(value=settings.presence_enabled)
        tk.Checkbutton(body, text="자리 비움과 오래 앉아 있는 것을 알아채기", variable=self.presence, font=(FONT, 10),
                       bg=BG, fg=TEXT, activebackground=BG, selectcolor="#ffffff", highlightthickness=0, bd=0,
                       anchor="w").pack(fill="x")
        note = "키보드·마우스를 마지막으로 쓴 시각만 봐요. 무엇을 입력했는지는 읽지 않아요."
        if sys.platform != "win32":
            note += " (Windows에서만 동작)"
        tk.Label(body, text=note, font=(FONT, 9), bg=BG, fg=SUBTLE).pack(anchor="w", pady=(0, 4))
        self.away = self._row(body, "돌아오면 인사", str(settings.away_minutes), "분 넘게 비웠을 때", width=5)
        self.rest = self._row(body, "쉬는 시간 알림", str(settings.break_reminder_minutes), "분 계속 쓰면 (0이면 끔)", width=5)
        self.water = self._row(body, "물 마시기 알림", str(settings.water_reminder_minutes), "분마다 (0이면 끔)", width=5)
        tk.Label(body, text="집중 타이머가 도는 동안에는 쉬는 시간·물 알림을 미뤄요.",
                 font=(FONT, 9), bg=BG, fg=SUBTLE).pack(anchor="w", pady=(4, 0))

        self._section(body, "복사한 글 도우미")
        self.clipboard = tk.BooleanVar(value=settings.clipboard_watch)
        tk.Checkbutton(body, text="날짜가 든 글·쇼핑 링크를 복사하면 일정·가격 알림을 제안하기", variable=self.clipboard,
                       font=(FONT, 10), bg=BG, fg=TEXT, activebackground=BG, selectcolor="#ffffff",
                       highlightthickness=0, bd=0, anchor="w").pack(fill="x")
        tk.Label(body, text="복사한 글은 저장하지 않고, 확인 카드를 눌러야 등록돼요. 긴 글·비밀번호 같은 글은 보지 않아요.",
                 font=(FONT, 9), bg=BG, fg=SUBTLE).pack(anchor="w")

        self.notice = tk.Label(outer, text="", font=(FONT, 9), bg=BG, fg=DANGER, anchor="w", justify="left")
        self.notice.pack(fill="x", pady=(6, 0))
        actions = tk.Frame(outer, bg=BG)
        actions.pack(fill="x", pady=(6, 0))
        self.save_button = button(actions, "저장", self._save)
        self.save_button.pack(side="right")
        button(actions, "취소", self.destroy, primary=False).pack(side="right", padx=6)
        self.bind("<Escape>", lambda _event: self.destroy())
        self._bind_wheel(self._canvas)
        self._bind_wheel(body)

    def _fit_body(self, _event: object = None) -> None:
        body = self._canvas.winfo_children()[0]
        width, height = body.winfo_reqwidth() + 48, body.winfo_reqheight() + 40
        shown = min(height, MAX_BODY_HEIGHT)
        self._canvas.configure(width=width, height=shown, scrollregion=(0, 0, width, height))
        if height > shown:
            self._bar.pack(side="right", fill="y", before=self._canvas)
        else:
            self._bar.pack_forget()

    def _bind_wheel(self, widget: tk.Misc) -> None:
        """Wheel scrolling on the widget and every descendant (labels and entries would otherwise swallow it)."""
        widget.bind("<MouseWheel>", lambda e: self._scroll(-1 if e.delta > 0 else 1), add="+")
        widget.bind("<Button-4>", lambda _e: self._scroll(-1), add="+")
        widget.bind("<Button-5>", lambda _e: self._scroll(1), add="+")
        for child in widget.winfo_children():
            self._bind_wheel(child)

    def _scroll(self, step: int) -> None:
        body = self._canvas.winfo_children()[0]
        if body.winfo_reqheight() + 40 > self._canvas.winfo_height():
            self._canvas.yview_scroll(step, "units")

    def _section(self, parent: tk.Misc, title: str) -> None:
        tk.Label(parent, text=title, font=(FONT, 11, "bold"), bg=BG, fg=TEXT).pack(anchor="w", pady=(14, 4))

    def _row(self, parent: tk.Misc, label: str, value: str, hint: str, width: int = 8) -> tk.Entry:
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, width=12, anchor="w", font=(FONT, 10), bg=BG, fg=TEXT).pack(side="left")
        widget = entry(row, width=width)
        widget.insert(0, value)
        widget.pack(side="left", ipady=4)
        tk.Label(row, text=hint, font=(FONT, 9), bg=BG, fg=SUBTLE).pack(side="left", padx=(8, 0))
        return widget

    # ----- saving -------------------------------------------------------------------

    def _clock(self, widget: tk.Entry, name: str) -> str:
        text = widget.get().strip()
        if not text:
            return ""
        clock = parse_clock(text)
        if clock is None:
            raise ValueError(f"{name} 시각을 08:30처럼 적어 주세요.")
        return clock.strftime("%H:%M")

    def _birthday(self) -> str:
        text = self.birthday.get().strip()
        if not text:
            return ""
        birthday = parse_birthday(text)
        if birthday is None:
            raise ValueError("생일은 3월 14일처럼 적어 주세요.")
        return birthday

    def _minutes(self, widget: tk.Entry, name: str) -> int:
        try:
            value = int(widget.get().strip() or 0)
        except ValueError:
            raise ValueError(f"{name}은(는) 숫자로 적어 주세요.") from None
        if not 0 <= value <= 600:
            raise ValueError(f"{name}은(는) 0~600분 사이로 적어 주세요.")
        return value

    def _save(self) -> None:
        try:
            changes = dict(
                briefing_time=self._clock(self.briefing, "아침 브리핑"),
                wrapup_time=self._clock(self.wrapup, "하루 정리"),
                presence_enabled=self.presence.get(),
                away_minutes=max(self._minutes(self.away, "돌아오면 인사"), 1),
                break_reminder_minutes=self._minutes(self.rest, "쉬는 시간 알림"),
                water_reminder_minutes=self._minutes(self.water, "물 마시기 알림"),
                clipboard_watch=self.clipboard.get(),
                user_birthday=self._birthday(),
                chatter=self.chatter.get(),
                **{key: var.get() for key, var in self.notify_vars.items()},
            )
        except ValueError as exc:
            self.notice.configure(text=str(exc))
            return
        city = self.city.get().strip()
        if not city:
            self._finish(changes | dict(weather_city="", weather_lat=None, weather_lon=None))
        elif city == self.settings.weather_city and self.settings.weather_lat is not None:
            self._finish(changes)
        else:
            # Finding the city is a network call: run it off the Tk thread and poll for the answer.
            self.notice.configure(text=f"'{city}' 위치를 찾는 중…", fg=SUBTLE)
            threading.Thread(target=self._find_city, args=(city,), daemon=True).start()
            self.after(POLL_MS, lambda: self._wait_city(changes))

    def _find_city(self, city: str) -> None:
        try:
            self._results.put(geocode(city))
        except WeatherError as exc:
            self._results.put(exc)

    def _wait_city(self, changes: dict) -> None:
        if not self.winfo_exists():
            return
        try:
            result = self._results.get_nowait()
        except queue.Empty:
            self.after(POLL_MS, lambda: self._wait_city(changes))
            return
        if isinstance(result, WeatherError):
            self.notice.configure(text=str(result), fg=DANGER)
            return
        self._finish(changes | dict(weather_city=result.name, weather_lat=result.latitude, weather_lon=result.longitude))

    def _finish(self, changes: dict) -> None:
        self.on_save(**changes)
        self.destroy()
