from __future__ import annotations

import queue
import random
import sys
import threading
import time
import tkinter as tk
import webbrowser
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from ... import autostart
from ...classic.tools import RenameAction
from ...companion import (
    EXPRESSIONS, Companion, ConfirmableAction, OllamaClient, get_persona, has_model, load_settings,
    parse_confirmation, save_settings,
)
from ...crashlog import log_exception
from ...paths import APP_DIR, ASSETS_DIR, SETTINGS_PATH, USER_CHARACTERS
from ...pcwatch import DownloadNudge
from ...presence import ClickCombo, IdleChatter, PatDetector, PresenceTracker
from ...pricewatch import WatchAction
from ...services import Services
from ...todo import TodoAction
from ...voice import VoiceSpeaker, VoiceStream, VoicevoxClient
from ..classic.assistant import AssistantWindow
from ..classic.desktop import NuriAssistantApp
from ..theme import apply_default_fonts
from ..windows.memos import MemoWindow
from ..windows.privacy import PrivacyWindow
from ..windows.rename_preview import RenamePreviewWindow
from ..windows.rename_settings import RenameSettingsWindow
from ..windows.schedule import ScheduleWindow
from ..windows.todo import TodoWindow
from .art import CharacterArt
from .chatbox import ChatBox, subject_particle
from .confirm_card import HEIGHT as CARD_HEIGHT, ConfirmCard
from .calendar_mixin import CalendarMixin
from .menu_mixin import MenuMixin
from .placeholder import draw_emote, draw_placeholder
from .price_mixin import PriceMixin
from .routine_mixin import RoutineMixin
from .speech_bubble import SpeechBubble
from .timer_mixin import TimerMixin
from .timing import (
    BLINK_GAP_MS, BLINK_MS, BRIEFING_DELAY_MS, CALENDAR_FIRST_MS, CANVAS_HEIGHT, CHAR_BOTTOM, CHAR_BOX, CHAR_TOP, CHATTER_POLL_MS,
    CHAT_GAP, CLIPBOARD_GAP_S, CLIPBOARD_POLL_MS, DOWNLOADS_POLL_MS, EVENT_POLL_MS, FALLBACK_BG, FIRST_BLINK_MS,
    FIRST_PRICE_CHECK_MS, FIRST_REMINDER_CHECK_MS, FULL_EXTRA, GLANCE_GAP_S, KEEP_ON_TOP_MS, LIGHT_HISTORY,
    LIGHT_SLOWDOWN, MAX_FACTS, MOUTH_FLAP_MS, POINTER_POLL_MS, PRESENCE_POLL_MS, PRIVACY_DELAY_MS, RELAX_BASE_MS,
    RELAX_MAX_EXTRA_MS, RELAX_PER_CHAR_MS, RELAX_RETRY_MS, ROUTINE_POLL_MS, TIMER_TICK_MS, TRANSPARENT_KEY, WIDTH,
)
from .voice_mixin import VoiceMixin
from .watch_mixin import WatchMixin
from .window_mixin import WindowMixin


class MascotApp(WindowMixin, RoutineMixin, WatchMixin, TimerMixin, VoiceMixin, PriceMixin, CalendarMixin, MenuMixin, tk.Tk):
    """Desktop companion: an always-on-top character that chats through a local model."""

    def __init__(self, app_dir: Path = APP_DIR, with_windows: bool = False) -> None:
        super().__init__()
        apply_default_fonts(self)
        self.settings_path = app_dir / SETTINGS_PATH.name
        self.settings = load_settings(self.settings_path)
        services = Services(app_dir, lambda: self.settings)
        # Short names for what the windows, reminders and menus use.
        self.store, self.schedule, self.todos = services.store, services.schedule, services.todos
        self.watches, self.price_checker = services.watches, services.price_checker
        self.focus_timer, self.toolbox, self.history = services.focus_timer, services.toolbox, services.history
        self.focus_log, self.affection, self.memos = services.focus_log, services.affection, services.memos
        self._price_sources = services.price_sources
        self.voice = VoiceSpeaker(
            client=lambda: VoicevoxClient(self.settings.voice_url),
            translate=self._to_japanese,
            on_start=lambda: self.events.put(("voice", True)),
            on_end=lambda: self.events.put(("voice", False)),
            on_error=lambda message: self.events.put(("voice_error", message)),
        )
        self._ja_cache: dict[str, str] = {}
        self._held_notices: list[tuple[str, str]] = []
        self._setup_held = False  # setup window wanted while the picker is still open
        self._setup_check_window = None
        self._reporting_error = False
        self._voice_error_shown = False
        self._voice_playing = False
        self._price_checking = False
        self._calendar_syncing = False
        self._calendar_window = None
        self.pending_actions: list[ConfirmableAction] = []
        self._preview_window: RenamePreviewWindow | None = None
        self.art = CharacterArt(self, app_dir / USER_CHARACTERS.name, ASSETS_DIR, hard_edges=sys.platform == "win32")
        self.events: queue.Queue[tuple] = queue.Queue()
        self.companion = self._make_companion()

        self.expression = "neutral"
        self.full_mode = self.settings.display_mode == "full"
        self.extra = FULL_EXTRA if self.full_mode else 0
        self.head_top = CHAR_TOP + self.extra
        self._relax_token = 0
        self.talking = False
        self.mouth_open = False
        self.blinking = False
        self.busy = False
        self.chatter = IdleChatter(self.settings.chatter)
        self.chatter.reset(datetime.now())
        self.pat, self.combo = PatDetector(), ClickCombo()
        self._fullscreen = False
        self._next_glance = time.monotonic() + random.uniform(*GLANCE_GAP_S)
        self.downloads_nudge = DownloadNudge(self.settings.downloads_threshold)
        self._last_clip: str | None = None
        self._last_routine_line = time.monotonic()  # start-up greeting counts as one
        self._last_clip_offer = -CLIPBOARD_GAP_S * 1.0
        self.presence = PresenceTracker(self.settings.away_minutes, self.settings.break_reminder_minutes,
                                        self.settings.water_reminder_minutes)
        self._drag_start: tuple[int, int, int, int] | None = None
        self._dragged = False
        self._last_hover = 0.0

        self._setup_window()
        self._build()
        self._place_window()
        self._render_character()
        if self.settings.pick_on_start and not with_windows:  # started with Windows: no picker in the way
            self.withdraw()
            self.after(10, lambda: self.open_picker(startup=True))
        else:
            # Right after Windows starts, VOICEVOX is usually not up yet: greet in the bubble only.
            (self.say if with_windows else self.talk)(random.choice(self.persona.greetings), "happy")
            self.after(BRIEFING_DELAY_MS, self.brief_today)
        if not self.settings.first_met:
            self._update_settings(first_met=datetime.now().date().isoformat())
        self.after(EVENT_POLL_MS, self._drain_events)
        self.after(FIRST_REMINDER_CHECK_MS, self._check_reminders)
        self.after(TIMER_TICK_MS, self._tick_timer)
        self.after(PRESENCE_POLL_MS, self._presence_loop)
        self.after(ROUTINE_POLL_MS, self._routine_loop)
        self.after(DOWNLOADS_POLL_MS, self._downloads_loop)
        self.after(CLIPBOARD_POLL_MS, self._clipboard_loop)
        self.after(CHATTER_POLL_MS, self._chatter_loop)
        if not self.settings.privacy_shown:
            self.after(PRIVACY_DELAY_MS, self._first_privacy_notice)
        self.after(FIRST_PRICE_CHECK_MS, self._price_loop)
        self.after(CALENDAR_FIRST_MS, self._calendar_loop)
        self.after(FIRST_BLINK_MS, self._blink)
        self.after(POINTER_POLL_MS, self._watch_pointer)
        self.after(KEEP_ON_TOP_MS, self._keep_on_screen)
        threading.Thread(target=self._check_model, args=(not with_windows,), daemon=True).start()

    def report_callback_exception(self, exc_type, value, tb) -> None:
        """Errors inside Tk callbacks: log them and make sure the user still has a window.

        Tk's default prints to stderr (invisible without a console) and leaves a withdrawn
        window hidden, which looks exactly like "the app does not start".
        """

        path = log_exception(exc_type, value, tb)
        if self._reporting_error:
            return
        self._reporting_error = True
        try:
            if self.state() == "withdrawn":
                self._reveal()
            where = f"\n기록: {path}" if path else ""
            self.say(f"앗, 오류가 났어요.\n{value!r}{where}", "sad")
        except Exception as exc:  # noqa: BLE001 - reporting must never raise
            log_exception(type(exc), exc, exc.__traceback__)
        finally:
            self._reporting_error = False

    def _reveal(self) -> None:
        # Borderless windows need the flag re-applied after being withdrawn (Windows).
        self.overrideredirect(True)
        self.deiconify()
        self.attributes("-topmost", True)

    @property
    def persona(self):
        return self.companion.persona

    def _make_companion(self) -> Companion:
        settings = self.settings
        return Companion(
            persona=get_persona(settings.persona_id),
            client=OllamaClient(settings.ollama_url),
            store=self.store,
            model=settings.model,
            user_name=settings.user_name,
            history_limit=min(settings.history_limit, LIGHT_HISTORY) if settings.light_mode else settings.history_limit,
            tools=self.toolbox,
            voice=self._voice_on(),
            context=self._companion_context,
        )

    @staticmethod
    def _autostart_enabled() -> bool:
        try:
            return autostart.supported() and autostart.is_enabled()
        except OSError:
            return False

    def _toggle_autostart(self) -> None:
        on = self.autostart_var.get()
        try:
            autostart.set_enabled(on)
        except OSError as exc:
            self.autostart_var.set(not on)
            self.say(f"시작 프로그램 설정을 바꾸지 못했어요.\n{exc}", "sad")
            return
        self.say("이제 윈도우를 켜면 저도 같이 켜져요." if on else "윈도우를 켤 때 저절로 켜지지 않게 했어요.", "happy")

    def _voice_on(self) -> bool:
        return self.settings.voice_enabled and not self.settings.light_mode

    def _companion_context(self) -> tuple[str, tuple[str, ...]]:
        """Closeness name and remembered facts for the system prompt (read on the worker thread; SQLite only)."""

        return self.affection.level(self.settings.persona_id)[1], tuple(memo.text for memo in self.memos.all()[-MAX_FACTS:])

    def _update_settings(self, **changes: object) -> None:
        self.settings = replace(self.settings, **changes)
        save_settings(self.settings_path, self.settings)
        if all(key.startswith("last_") for key in changes):
            return  # bookkeeping only (hourly chime etc.): keep the companion and what it learned about tools
        self.companion = self._make_companion()

    # ----- window -----------------------------------------------------------------

    def _setup_window(self) -> None:
        self.title("Nuri Assistant")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.bg = FALLBACK_BG
        if sys.platform == "win32":
            self.bg = TRANSPARENT_KEY
            self.attributes("-transparentcolor", TRANSPARENT_KEY)
        elif sys.platform == "darwin":
            self.bg = "systemTransparent"
            self.attributes("-transparent", True)
        self.configure(bg=self.bg)

    def _build(self) -> None:
        self.canvas = tk.Canvas(self, width=WIDTH, height=CANVAS_HEIGHT + self.extra, bg=self.bg, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.bubble = SpeechBubble(self.canvas, WIDTH)
        self.canvas.tag_bind("character", "<ButtonPress-1>", self._on_press)
        self.canvas.tag_bind("character", "<B1-Motion>", self._on_drag)
        self.canvas.tag_bind("character", "<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Motion>", self._on_motion, add="+")
        self.canvas.tag_bind("bubble", "<Button-1>", lambda _event: self._bubble_clicked())
        self.canvas.bind("<Button-3>", self._show_menu)
        if sys.platform == "darwin":
            self.canvas.bind("<Button-2>", self._show_menu)

        self.chat = ChatBox(
            self.canvas, 20, self.char_bottom + 6, WIDTH - 40,
            on_send=self.send,
            on_menu=lambda x, y: self.menu.tk_popup(x, y),
        )
        self.chat.set_hint(self._idle_hint())
        # Confirm cards sit over the character's chest, just above the chat box.
        self.card = ConfirmCard(self.canvas, 20, self.char_bottom - CARD_HEIGHT - 4, WIDTH - 40)

        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label="비서 선택…", command=self.open_picker)
        self.full_var = tk.BooleanVar(value=self.full_mode)
        self.menu.add_checkbutton(label="전신으로 보기", variable=self.full_var,
                                  command=lambda: self.set_display_mode("full" if self.full_var.get() else "bust"))
        self.sharp_var = tk.BooleanVar(value=self.settings.sharp_display)
        self.menu.add_checkbutton(label="선명하게 보기 (고배율 화면)", variable=self.sharp_var, command=self.toggle_sharp)
        self.menu.add_command(label="내 이름 설정", command=self.ask_user_name)
        self.menu.add_command(label="AI 설정…", command=self.open_ai_settings)
        self.menu.add_command(label="준비 확인…", command=self.open_setup_check)
        self.menu.add_separator()
        self.menu.add_command(label="일정 보기", command=lambda: ScheduleWindow(self, self.schedule))
        self.menu.add_command(label="캘린더 연결…", command=self.open_calendar_settings)
        self.menu.add_command(label="오늘 일정 브리핑", command=lambda: self.brief_today(force=True))
        self.menu.add_command(label="오늘 하루 정리", command=lambda: self.wrap_up(force=True))
        self.menu.add_command(label="할 일", command=lambda: TodoWindow(self, self.todos))
        self.menu.add_command(label="집중 타이머…", command=self.open_focus_dialog)
        self.menu.add_command(label="최저가 알림", command=self.open_price_window)
        self.menu.add_separator()
        self.menu.add_command(label="가격 알림 설정…", command=self.open_price_settings)
        self.menu.add_command(label="음성 설정…", command=self.open_voice_settings)
        self.menu.add_command(label="생활 알림 설정…", command=self.open_routine_settings)
        self.autostart_var = tk.BooleanVar(value=self._autostart_enabled())
        self.menu.add_checkbutton(label="윈도우 시작할 때 켜기", variable=self.autostart_var, command=self._toggle_autostart,
                                  state="normal" if autostart.supported() else "disabled")
        self.menu.add_separator()
        self.menu.add_command(label="대화 기록 보기", command=self.show_log)
        self.menu.add_command(label="기억 수첩", command=lambda: MemoWindow(self, self.memos))
        self.menu.add_command(label="우리 사이", command=self.show_closeness)
        self.menu.add_command(label="개인정보 안내", command=lambda: PrivacyWindow(self))
        self.menu.add_command(label="오늘의 운세", command=self.tell_fortune)
        self.menu.add_command(label="이 캐릭터의 기억 지우기", command=self.clear_memory)
        self.menu.add_separator()
        self.menu.add_command(label="파일 정리 도구", command=lambda: NuriAssistantApp(self, history=self.history))
        self.menu.add_command(label="파일 정리 설정…", command=lambda: RenameSettingsWindow(self, self.settings, self._update_settings))
        self.menu.add_command(label="파일/구매 비서", command=lambda: AssistantWindow(self, self.history))
        self.menu.add_separator()
        self.menu.add_command(label="종료", command=self.quit_app)


    # ----- character --------------------------------------------------------------

    @property
    def char_bottom(self) -> int:
        return CHAR_BOTTOM + self.extra

    def _render_character(self) -> None:
        mouth = self.talking and self.mouth_open
        box = (CHAR_BOX[0], CHAR_BOX[1] + self.extra)
        image, has_expression = self.art.frame(self.persona.id, self.expression, mouth, self.blinking, self.full_mode, box)
        if image is None:
            head_top = CHAR_TOP + self.extra
            draw_placeholder(self.canvas, WIDTH // 2, head_top, self.persona.look, self.expression, mouth, self.blinking)
        else:
            # Seat the visible bottom (bust cut line / feet) just above the chat box.
            bottom = self.chat.top - CHAT_GAP + image.height() - self.art.content_bottom(image)
            top = bottom - image.height()
            head_top = top + 12
            self.canvas.delete("character")
            self.canvas.create_image(WIDTH // 2, bottom, anchor="s", image=image, tags="character")
            if not has_expression:
                draw_emote(self.canvas, WIDTH // 2 + int(image.width() * 0.3), top + int(image.height() * 0.2), self.expression)
        if head_top != self.head_top:
            # Art of a different height: keep the bubble tail touching the head.
            self.head_top = head_top
            self._show_bubble(self.bubble.text)
        # Freshly drawn character items would otherwise cover the overlays.
        for overlay in ("timer", "bubble", "confirm", "chat"):
            self.canvas.tag_raise(overlay)

    def set_expression(self, expression: str) -> None:
        if expression in EXPRESSIONS and expression != self.expression:
            self.expression = expression
            self._render_character()

    def _blink(self) -> None:
        # Eyes close briefly, then stay open for a random few seconds.
        self.blinking = not self.blinking
        try:
            self._render_character()
        finally:
            gap = random.randint(*BLINK_GAP_MS) * (LIGHT_SLOWDOWN if self.settings.light_mode else 1)
            self.after(BLINK_MS if self.blinking else gap, self._blink)

    def _start_talking(self) -> None:
        if not self.talking:
            self.talking = True
            self._flap()

    def _flap(self) -> None:
        if not self.talking:
            self.mouth_open = False
            self._render_character()
            return
        self.mouth_open = not self.mouth_open
        try:
            self._render_character()
        finally:
            self.after(MOUTH_FLAP_MS, self._flap)

    # ----- speech bubble ----------------------------------------------------------

    def say(self, text: str, expression: str | None = None) -> None:
        self.chatter.reset(datetime.now())  # idle talk never comes right after another line
        if expression:
            self.set_expression(expression)
            self._relax_later(RELAX_BASE_MS + min(len(text) * RELAX_PER_CHAR_MS, RELAX_MAX_EXTRA_MS))
        self._show_bubble(text)

    def _relax_later(self, delay_ms: int) -> None:
        """Return to the neutral face a while after speaking, so moods do not stick."""

        self._relax_token += 1
        token = self._relax_token

        def relax() -> None:
            if token != self._relax_token:
                return
            if self.busy:
                self._relax_later(RELAX_RETRY_MS)
            else:
                self.set_expression("neutral")

        self.after(delay_ms, relax)

    def _bubble_clicked(self) -> None:
        link = self.bubble.take_link()
        if link:
            webbrowser.open(link)
        self._show_bubble("")

    def _show_bubble(self, text: str) -> None:
        self.bubble.show(text, self.head_top, self.persona.name)

    # ----- conversation -----------------------------------------------------------

    def send(self) -> None:
        text = self.chat.text().strip()
        if not text or self.busy:
            return
        self.chat.clear()
        if self.card.visible:
            answer = parse_confirmation(text)
            if answer is not None:
                self._resolve_card(answer)
                return
        self._set_busy(True)
        self.say("…", "thinking")
        companion = self.companion
        # Japanese sentences start playing while the reply still streams (VoiceStream is thread-safe).
        stream = self.voice.stream(self._voice_id()) if self._voice_on() and companion.voice else None
        threading.Thread(target=self._ask, args=(companion, text, stream), daemon=True).start()

    def _ask(self, companion: Companion, text: str, stream: VoiceStream | None = None) -> None:
        try:
            reply = companion.reply(text, on_update=lambda visible, expression: self.events.put(("update", visible, expression)),
                                    on_voice=stream.add if stream else None)
        except Exception as exc:  # noqa: BLE001 - every failure must reach the bubble and re-enable input
            self.events.put(("error", str(exc)))
            return
        finally:
            if stream:
                stream.close()  # no more parts; its threads end once the queued ones are played
        self.events.put(("done", reply.text, reply.expression, reply.actions, reply.voice, reply.voiced))

    def _drain_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                try:
                    self._handle_event(*event)
                except Exception:  # noqa: BLE001 - one bad event must not stop the loop
                    self.report_callback_exception(*sys.exc_info())
                    if event[0] in ("done", "error"):
                        self.talking = False
                        self._set_busy(False)
        except queue.Empty:
            pass
        finally:
            self.after(EVENT_POLL_MS, self._drain_events)

    def _handle_event(self, kind: str, *values) -> None:
        # Event tuples are ("kind", *values), put on self.events by worker threads.
        handler = {
            "update": self._on_update,
            "done": self._on_done,
            "error": self._on_error,
            "voice": self._on_voice,
            "voice_error": self._on_voice_error,
            "prices": self._show_price_results,
            "calendar_done": self._on_calendar_done,
            "notice": self._on_notice,
            "briefing": self._on_briefing,
            "setup_needed": self._on_setup_needed,
        }.get(kind)
        if handler is not None:
            handler(*values)

    def _on_update(self, visible: str, expression: str | None) -> None:
        if visible:
            self._start_talking()
            self.say(visible, expression)

    def _on_done(self, text: str, expression: str | None, actions: list, spoken: str, voiced: bool = False) -> None:
        self.talking = self._voice_playing  # the streamed voice may still be speaking
        self.gain("chat")
        self.say(text, expression)
        if not voiced:  # nothing streamed for the final answer: speak <ja> or a translation afterwards, as before
            self.speak(text, japanese=spoken)
        self._set_busy(False)
        if actions:
            self.pending_actions = list(actions)
            self._show_next_card()

    def _on_error(self, message: str) -> None:
        self.talking = False
        self.say(f"앗, 문제가 생겼어요.\n{message}", "sad")
        self._set_busy(False)

    def _on_voice(self, playing: bool) -> None:
        self._voice_playing = playing
        if playing:
            self._start_talking()
        else:
            self.talking = False

    def _on_voice_error(self, message: str) -> None:
        if not self._voice_error_shown:
            self._voice_error_shown = True
            self.say(f"목소리가 안 나와요.\n{message}", "sad")

    def _on_notice(self, message: str, expression: str) -> None:
        if self.state() == "withdrawn":
            # The picker is still open; the greeting after picking would overwrite it.
            self._held_notices.append((message, expression))
        else:
            self.say(message, expression)

    def _on_setup_needed(self) -> None:
        if self.state() == "withdrawn":  # the picker is still open: open it after picking
            self._setup_held = True
        else:
            self.open_setup_check()

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        if busy:
            self.chat.set_enabled(False, f"{subject_particle(self.persona.name)} 대답하는 중…")
        else:
            self.chat.set_enabled(True, self._idle_hint())
            if self.chat.visible:
                self.chat.focus()

    def _check_model(self, offer_setup: bool = False) -> None:
        client, model = OllamaClient(self.settings.ollama_url), self.settings.model
        try:
            installed = client.list_models()
        except Exception as exc:  # noqa: BLE001 - shown to the user, app keeps running
            self.events.put(("notice", f"{exc}\n설치: https://ollama.com", "sad"))
            if offer_setup:
                self.events.put(("setup_needed",))
            return
        if not has_model(installed, model):
            self.events.put(("notice", f"'{model}' 모델이 아직 없어요.\n터미널에서 ollama pull {model} 을 실행해 주세요.", "surprised"))
            if offer_setup:
                self.events.put(("setup_needed",))

    # ----- confirm cards -------------------------------------------------------------

    def _show_next_card(self) -> None:
        if not self.pending_actions:
            self.card.hide()
            return
        action = self.pending_actions[0]
        details = (lambda: self.open_rename_preview(action)) if isinstance(action, RenameAction) and action.previews else None
        self.card.show(action, lambda: self._resolve_card(True), lambda: self._resolve_card(False), details)

    def open_rename_preview(self, action: RenameAction) -> None:
        """Full old -> new list for the rename on the card; its buttons answer the same card."""

        if self._preview_window is not None and self._preview_window.winfo_exists():
            self._preview_window.destroy()
        self._preview_window = RenamePreviewWindow(self, action, lambda: self._resolve_card(True), lambda: self._resolve_card(False))

    def _resolve_card(self, approved: bool) -> None:
        if not self.pending_actions:
            self.card.hide()
            return
        action = self.pending_actions.pop(0)
        if self._preview_window is not None and self._preview_window.winfo_exists():
            self._preview_window.destroy()  # answered from the card or by typing; the list is stale now
        self._preview_window = None
        if approved:
            message = self.toolbox.confirm(action)
            self.companion.note(message)
            self.talk(message, "happy")
            self.gain("todo_done" if isinstance(action, TodoAction) and action.kind == "done" else "approved")
            if isinstance(action, WatchAction) and action.kind == "add":
                self.check_prices_now()
        else:
            what = "파일 이름은" if isinstance(action, RenameAction) else f"'{action.title}'은(는)"
            message = f"알겠어요, {what} 그대로 둘게요."
            self.companion.note(message, "neutral")
            self.say(message, "neutral")
        self._show_next_card()



    def destroy(self) -> None:
        # Cancel animation/polling timers so none fires into a destroyed interpreter.
        # Plain Tcl "after cancel": after_cancel() also deletes the callback's Tcl command, and for
        # timers a child widget scheduled (chat box, bubble) that command belongs to the child, whose
        # own destroy then fails with "can't delete Tcl command" and the app never closes.
        for after_id in self.tk.splitlist(self.tk.call("after", "info")):
            self.tk.call("after", "cancel", after_id)
        super().destroy()

    def quit_app(self) -> None:
        self._update_settings(x=self.winfo_x(), y=self.winfo_y())
        self.destroy()


def selfcheck() -> None:
    """Build check: the character window comes up with its art, in a temp folder. Raises if not."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        app = MascotApp(Path(tmp), with_windows=True)
        try:
            app.update()
            if not app.art.image_path("neutral", app.persona.id, full=False):
                raise RuntimeError(f"캐릭터 그림을 찾지 못했습니다: {ASSETS_DIR}")
        finally:
            app.destroy()


def run_mascot(with_windows: bool = False) -> None:
    MascotApp(with_windows=with_windows).mainloop()
