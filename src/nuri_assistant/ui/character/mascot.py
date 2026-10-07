from __future__ import annotations

import queue
import random
import sys
import threading
import time
import tkinter as tk
import webbrowser
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox, simpledialog

from ...announcements import compose_briefing, nag_line, price_alert_line, reminder_line, timer_line
from ...companion import (
    EXPRESSIONS,
    PERSONAS,
    Companion,
    ConfirmableAction,
    OllamaClient,
    get_persona,
    load_settings,
    parse_confirmation,
    save_settings,
)
from ...crashlog import log_exception
from ...paths import APP_DIR, ASSETS_DIR, SETTINGS_PATH, USER_CHARACTERS
from ...pricewatch import CheckResult, WatchAction
from ...screen import Rect, all_monitors, default_position, is_reachable, work_area
from ...services import Services
from ...voice import VoiceSpeaker, VoicevoxClient
from ..classic.assistant import AssistantWindow
from ..classic.desktop import NuriAssistantApp
from ..windows.conversation_log import ConversationLogWindow
from ..windows.price import PriceWindow
from ..windows.price_settings import PriceSettingsWindow
from ..windows.schedule import ScheduleWindow
from ..windows.todo import TodoWindow
from ..windows.voice_settings import VoiceSettingsWindow
from ..theme import apply_default_fonts
from .art import CharacterArt
from .chatbox import HEIGHT as CHAT_HEIGHT, ChatBox, subject_particle
from .confirm_card import HEIGHT as CARD_HEIGHT, ConfirmCard
from .picker import CharacterPicker
from .placeholder import PLACEHOLDER_HEIGHT, draw_emote, draw_placeholder
from .speech_bubble import SpeechBubble
from .timer_badge import draw_timer_badge


# Character frames are 405px wide and CHAR_BOX is WIDTH - 10, so they show 1:1 with no
# runtime resampling (which is what made the art look soft, especially without Pillow).
WIDTH = 415
CANVAS_HEIGHT = 560
# The chat box appears right under the character, in the strip below CHAR_BOTTOM.
CHAR_BOTTOM = CANVAS_HEIGHT - CHAT_HEIGHT - 18
CHAR_TOP = CHAR_BOTTOM - PLACEHOLDER_HEIGHT
# Images may rise behind the bubble area so a bust-up drawing is shown large.
CHAR_BOX = (WIDTH - 10, CHAR_BOTTOM - 120)
# Full-body frames are 480px tall vs 344px for the bust; the window grows by this much.
FULL_EXTRA = 150
# Timings (ms unless noted); together they set how lively the character feels.
EVENT_POLL_MS = 50
POINTER_POLL_MS = 120
CHAT_HIDE_DELAY_MS = 1200
FIRST_REMINDER_CHECK_MS = 5000
REMINDER_POLL_MS = 20_000
TIMER_TICK_MS = 1000
FIRST_PRICE_CHECK_MS = 30_000
MIN_PRICE_CHECK_MINUTES = 10
PRICE_ALERT_GAP_MS = 9000
BRIEFING_DELAY_MS = 4500
FIRST_BLINK_MS = 3500
BLINK_MS = 140
BLINK_GAP_MS = (2500, 6000)
MOUTH_FLAP_MS = 130
# The face relaxes to neutral after a base delay plus a little per character of text.
RELAX_BASE_MS = 6000
RELAX_PER_CHAR_MS = 60
RELAX_MAX_EXTRA_MS = 9000
RELAX_RETRY_MS = 2000
# Notices that arrived while the picker was open are replayed after picking.
HELD_NOTICE_DELAY_MS = 3500
HELD_NOTICE_GAP_MS = 4000
# Pointer travel (px) before a press on the character counts as a drag, not a poke.
DRAG_THRESHOLD_PX = 4
KEEP_ON_TOP_MS = 3000  # re-assert topmost / on-screen
# Windows keys this exact color out of the window. A near-black key keeps
# anti-aliased PNG edges looking like line art instead of a colored halo.
TRANSPARENT_KEY = "#010203"
FALLBACK_BG = "#f3eff7"


class MascotApp(tk.Tk):
    """Desktop companion: an always-on-top character that chats through a local model."""

    def __init__(self, app_dir: Path = APP_DIR) -> None:
        super().__init__()
        apply_default_fonts(self)
        self.settings_path = app_dir / SETTINGS_PATH.name
        self.settings = load_settings(self.settings_path)
        services = Services(app_dir, lambda: self.settings)
        # Short names for what the windows, reminders and menus use.
        self.store, self.schedule, self.todos = services.store, services.schedule, services.todos
        self.watches, self.price_checker = services.watches, services.price_checker
        self.focus_timer, self.toolbox, self.history = services.focus_timer, services.toolbox, services.history
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
        self._reporting_error = False
        self._voice_error_shown = False
        self._price_checking = False
        self.pending_actions: list[ConfirmableAction] = []
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
        self._drag_start: tuple[int, int, int, int] | None = None
        self._dragged = False
        self._last_hover = 0.0

        self._setup_window()
        self._build()
        self._place_window()
        self._render_character()
        if self.settings.pick_on_start:
            self.withdraw()
            self.after(10, lambda: self.open_picker(startup=True))
        else:
            self.talk(random.choice(self.persona.greetings), "happy")
            self.after(BRIEFING_DELAY_MS, self.brief_today)
        self.after(EVENT_POLL_MS, self._drain_events)
        self.after(FIRST_REMINDER_CHECK_MS, self._check_reminders)
        self.after(TIMER_TICK_MS, self._tick_timer)
        self.after(FIRST_PRICE_CHECK_MS, self._price_loop)
        self.after(FIRST_BLINK_MS, self._blink)
        self.after(POINTER_POLL_MS, self._watch_pointer)
        self.after(KEEP_ON_TOP_MS, self._keep_on_screen)
        threading.Thread(target=self._check_model, daemon=True).start()

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
            history_limit=settings.history_limit,
            tools=self.toolbox,
            voice=settings.voice_enabled,
        )

    def _update_settings(self, **changes: object) -> None:
        self.settings = replace(self.settings, **changes)
        save_settings(self.settings_path, self.settings)
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
        self.menu.add_command(label="내 이름 설정", command=self.ask_user_name)
        self.menu.add_command(label="AI 모델 설정", command=self.ask_model)
        self.menu.add_separator()
        self.menu.add_command(label="일정 보기", command=lambda: ScheduleWindow(self, self.schedule))
        self.menu.add_command(label="오늘 일정 브리핑", command=lambda: self.brief_today(force=True))
        self.menu.add_command(label="할 일", command=lambda: TodoWindow(self, self.todos))
        self.menu.add_command(label="집중 타이머 시작 (25분)", command=lambda: self.start_focus(25, 5))
        self.menu.add_command(label="최저가 알림", command=self.open_price_window)
        self.menu.add_separator()
        self.menu.add_command(label="가격 알림 설정…", command=self.open_price_settings)
        self.menu.add_command(label="음성 설정…", command=self.open_voice_settings)
        self.menu.add_separator()
        self.menu.add_command(label="대화 기록 보기", command=self.show_log)
        self.menu.add_command(label="이 캐릭터의 기억 지우기", command=self.clear_memory)
        self.menu.add_separator()
        self.menu.add_command(label="파일 정리 도구", command=lambda: NuriAssistantApp(self, history=self.history))
        self.menu.add_command(label="파일/구매 비서", command=lambda: AssistantWindow(self, self.history))
        self.menu.add_separator()
        self.menu.add_command(label="종료", command=self.quit_app)

    def _place_window(self) -> None:
        """Saved spot if it is still on a monitor, else bottom-right above the taskbar."""

        self.update_idletasks()
        height = self.winfo_reqheight()
        x, y = self.settings.x, self.settings.y
        if x is None or y is None or not is_reachable(int(x), int(y), WIDTH, height, self._monitors()):
            x, y = default_position(self._work_area(), WIDTH, height)
        self.geometry(f"+{int(x)}+{int(y)}")

    def _work_area(self) -> Rect:
        return work_area(self.winfo_screenwidth(), self.winfo_screenheight())

    def _monitors(self) -> Rect:
        return all_monitors(self.winfo_screenwidth(), self.winfo_screenheight())

    def _keep_on_screen(self) -> None:
        try:
            self._stay_visible()
        finally:
            self.after(KEEP_ON_TOP_MS, self._keep_on_screen)

    def _stay_visible(self) -> None:
        """Windows drops "topmost" after full-screen apps or other topmost windows, and a
        monitor change can strand the window off-screen: re-assert both every few seconds."""

        if self.state() == "withdrawn" or self._drag_start is not None:
            return
        if not is_reachable(self.winfo_x(), self.winfo_y(), WIDTH, self.winfo_height(), self._monitors()):
            x, y = default_position(self._work_area(), WIDTH, self.winfo_height())
            self.geometry(f"+{x}+{y}")
            self._update_settings(x=x, y=y)
        # Not while our own windows are open: re-raising would cover them.
        if not any(isinstance(w, tk.Toplevel) and w.winfo_viewable() for w in self.winfo_children()):
            self.attributes("-topmost", True)

    def _on_press(self, event: tk.Event) -> None:
        self._drag_start = (event.x_root, event.y_root, self.winfo_x(), self.winfo_y())
        self._dragged = False

    def _on_drag(self, event: tk.Event) -> None:
        if self._drag_start is None:
            return
        start_x, start_y, win_x, win_y = self._drag_start
        dx, dy = event.x_root - start_x, event.y_root - start_y
        if abs(dx) + abs(dy) > DRAG_THRESHOLD_PX:
            self._dragged = True
        if self._dragged:
            self.geometry(f"+{win_x + dx}+{win_y + dy}")

    def _on_release(self, _event: tk.Event) -> None:
        self._drag_start = None
        if self._dragged:
            self._update_settings(x=self.winfo_x(), y=self.winfo_y())
        elif not self.busy:
            self.talk(random.choice(self.persona.pokes), random.choice(("surprised", "shy", "happy")))
            self.chat.focus()

    def _show_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def _idle_hint(self) -> str:
        return f"{self.persona.name}에게 말 걸기…"

    def _watch_pointer(self) -> None:
        """Show the chat box while the mouse is on the character (or the box itself)."""

        try:
            self._update_hover()
        finally:
            self.after(POINTER_POLL_MS, self._watch_pointer)

    def _update_hover(self) -> None:
        px, py = self.winfo_pointerxy()
        x, y = px - self.canvas.winfo_rootx(), py - self.canvas.winfo_rooty()
        box = self.canvas.bbox("character")
        over_character = box is not None and box[0] - 8 <= x <= box[2] + 8 and box[1] <= y <= box[3] + 12
        keep = (
            over_character
            or self.chat.contains(x, y)
            or self.busy
            or (self.chat.focused() and bool(self.chat.text()))
            or self._drag_start is not None
        )
        now = time.monotonic()
        if keep:
            self._last_hover = now
            self.chat.show()
        elif self.chat.visible and (now - self._last_hover) * 1000 > CHAT_HIDE_DELAY_MS:
            self.chat.hide()

    def set_display_mode(self, mode: str) -> None:
        """Switch bust/full body; the window grows upward so the character's feet stay put."""

        full = mode == "full"
        if full == self.full_mode:
            return
        dy = (FULL_EXTRA if full else 0) - self.extra
        self.full_mode, self.extra = full, FULL_EXTRA if full else 0
        self.full_var.set(full)
        self.canvas.configure(height=CANVAS_HEIGHT + self.extra)
        self.canvas.move("chat", 0, dy)
        self.chat.top += dy
        self.card.top += dy
        if self.card.visible:
            self._show_next_card()
        self.update_idletasks()
        y = max(self.winfo_y() - dy, self._monitors().top)
        self.geometry(f"+{self.winfo_x()}+{y}")
        self._update_settings(display_mode=mode, y=y)
        self._render_character()
        self._show_bubble(self.bubble.text)

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
            top = self.char_bottom - image.height()
            head_top = top + 12
            self.canvas.delete("character")
            self.canvas.create_image(WIDTH // 2, self.char_bottom, anchor="s", image=image, tags="character")
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
            self.after(BLINK_MS if self.blinking else random.randint(*BLINK_GAP_MS), self._blink)

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
        threading.Thread(target=self._ask, args=(companion, text), daemon=True).start()

    def _ask(self, companion: Companion, text: str) -> None:
        try:
            reply = companion.reply(text, on_update=lambda visible, expression: self.events.put(("update", visible, expression)))
        except Exception as exc:  # noqa: BLE001 - every failure must reach the bubble and re-enable input
            self.events.put(("error", str(exc)))
            return
        self.events.put(("done", reply.text, reply.expression, reply.actions, reply.voice))

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
            "notice": self._on_notice,
        }.get(kind)
        if handler is not None:
            handler(*values)

    def _on_update(self, visible: str, expression: str | None) -> None:
        if visible:
            self._start_talking()
            self.say(visible, expression)

    def _on_done(self, text: str, expression: str | None, actions: list, spoken: str) -> None:
        self.talking = False
        self.say(text, expression)
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

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        if busy:
            self.chat.set_enabled(False, f"{subject_particle(self.persona.name)} 대답하는 중…")
        else:
            self.chat.set_enabled(True, self._idle_hint())
            if self.chat.visible:
                self.chat.focus()

    def _check_model(self) -> None:
        client, model = OllamaClient(self.settings.ollama_url), self.settings.model
        try:
            installed = client.list_models()
        except Exception as exc:  # noqa: BLE001 - shown to the user, app keeps running
            self.events.put(("notice", f"{exc}\n설치: https://ollama.com", "sad"))
            return
        names = set(installed) | {name.removesuffix(":latest") for name in installed}
        if model not in names:
            self.events.put(("notice", f"'{model}' 모델이 아직 없어요.\n터미널에서 ollama pull {model} 을 실행해 주세요.", "surprised"))

    # ----- confirm cards & reminders ------------------------------------------------

    def _show_next_card(self) -> None:
        if not self.pending_actions:
            self.card.hide()
            return
        self.card.show(self.pending_actions[0], lambda: self._resolve_card(True), lambda: self._resolve_card(False))

    def _resolve_card(self, approved: bool) -> None:
        if not self.pending_actions:
            self.card.hide()
            return
        action = self.pending_actions.pop(0)
        if approved:
            message = self.toolbox.confirm(action)
            self.companion.note(message)
            self.talk(message, "happy")
            if isinstance(action, WatchAction) and action.kind == "add":
                self.check_prices_now()
        else:
            message = f"알겠어요, '{action.title}'은(는) 그대로 둘게요."
            self.companion.note(message, "neutral")
            self.say(message, "neutral")
        self._show_next_card()

    def _check_reminders(self) -> None:
        try:
            self._remind_due()
        finally:
            self.after(REMINDER_POLL_MS, self._check_reminders)

    def _remind_due(self) -> None:
        if self.state() != "withdrawn" and not self.busy:
            now = datetime.now()
            due = self.schedule.due_reminders(now)
            if due:
                # One per poll so bubbles do not overwrite each other; the rest stay due.
                event = due[0]
                self.schedule.mark_reminded(event.id)
                self.talk(reminder_line(self.persona, event, now), "surprised")
                self.bell()
            elif nags := self.todos.due_nags(now):
                todo, kind = nags[0]
                self.todos.mark_nagged(todo.id, kind)
                self.talk(*nag_line(self.persona, todo, kind))
                self.bell()

    def brief_today(self, force: bool = False) -> None:
        """Once a day (or on request), list today's events in the character's voice."""

        now = datetime.now()
        today = now.date().isoformat()
        if not force and self.settings.last_briefing == today:
            return
        if not force:
            self._update_settings(last_briefing=today)
        start = datetime.combine(now.date(), datetime.min.time())
        events = self.schedule.between(start, start + timedelta(days=1))
        urgent = [todo for todo in self.todos.open() if todo.due and todo.due.date() <= now.date()]
        briefing = compose_briefing(self.persona, events, urgent, now.date())
        if briefing is None:
            if force:
                self.say("오늘은 일정도 급한 할 일도 없어요.", "neutral")
            return
        text, headline = briefing
        self.say(text, "happy")
        self.speak(headline)

    # ----- focus timer --------------------------------------------------------------

    def start_focus(self, focus_minutes: int = 25, break_minutes: int = 5) -> None:
        self.focus_timer.start(datetime.now(), focus_minutes, break_minutes)
        self.talk(f"{focus_minutes}분 집중 시작! 끝나면 알려 줄게요.", "happy")
        self._draw_timer()

    def _tick_timer(self) -> None:
        try:
            self._timer_step()
        finally:
            self.after(TIMER_TICK_MS, self._tick_timer)

    def _timer_step(self) -> None:
        now = datetime.now()
        for event in self.focus_timer.tick(now):
            self.talk(*timer_line(self.persona, self.focus_timer, event))
            self.bell()
        self._draw_timer()

    def _draw_timer(self) -> None:
        draw_timer_badge(self.canvas, self.focus_timer.state(datetime.now()), self.head_top, self._stop_timer)

    def _stop_timer(self) -> None:
        if self.focus_timer.stop():
            self._draw_timer()
            self.talk("타이머를 멈췄어요.", "neutral")

    # ----- voice ----------------------------------------------------------------------

    def talk(self, text: str, expression: str | None = None) -> None:
        """Say a line in the bubble and, when voice is on, out loud."""

        self.say(text, expression)
        self.speak(text)

    def speak(self, text: str, japanese: str = "") -> None:
        if not self.settings.voice_enabled or not (text.strip() or japanese.strip()):
            return
        voice_id = self.settings.voice_ids.get(self.persona.id, self.persona.voice_id)
        self.voice.speak(voice_id, japanese=japanese, korean="" if japanese else text)

    def _to_japanese(self, text: str) -> str:
        key = f"{self.persona.id}:{text}"
        if key not in self._ja_cache:
            self._ja_cache[key] = self.companion.to_japanese(text)
        return self._ja_cache[key]

    def open_voice_settings(self) -> None:
        def preview(url: str, voice_id: int) -> None:
            speaker = VoiceSpeaker(
                client=lambda: VoicevoxClient(url), translate=self._to_japanese,
                on_start=lambda: self.events.put(("voice", True)), on_end=lambda: self.events.put(("voice", False)),
                on_error=lambda message: self.events.put(("notice", message, "sad")),
            )
            line = random.choice(self.persona.greetings)
            self.say(line, "happy")
            speaker.speak(voice_id, korean=line)

        def save(**changes: object) -> None:
            self._voice_error_shown = False
            self._update_settings(**changes)

        VoiceSettingsWindow(self, self.settings, self.persona, save, preview)

    # ----- price watch --------------------------------------------------------------

    def _price_loop(self) -> None:
        try:
            self.check_prices_now()
        finally:
            self.after(max(self.settings.price_check_minutes, MIN_PRICE_CHECK_MINUTES) * 60_000, self._price_loop)

    def check_prices_now(self) -> None:
        """Check every watch on a worker thread; results come back through the event queue."""

        if self._price_checking or not self.watches.all():
            return
        self._price_checking = True

        def work() -> None:
            results = []
            try:
                for watch in self.watches.all():
                    results.append(self.price_checker.check(watch))
            finally:
                self.events.put(("prices", results))

        threading.Thread(target=work, daemon=True).start()

    def _show_price_results(self, results: list[CheckResult]) -> None:
        self._price_checking = False
        alerts = [result for result in results if result.alert and result.offer]
        for index, result in enumerate(alerts):
            self.after(index * PRICE_ALERT_GAP_MS, lambda result=result: self._announce_price(result))

    def _announce_price(self, result: CheckResult) -> None:
        line = price_alert_line(self.persona, result)
        self.say(f"{line}\n(말풍선을 누르면 상품 페이지가 열려요)", "surprised")
        self.speak(line)
        self.bubble.link = result.offer.link
        self.bell()

    def open_price_window(self) -> None:
        PriceWindow(self, self.watches, self.check_prices_now, lambda: bool(self._price_sources()))

    def open_price_settings(self) -> None:
        def save(**changes: object) -> None:
            self._update_settings(**changes)
            self.check_prices_now()

        PriceSettingsWindow(self, self.settings, save)

    # ----- menu actions -----------------------------------------------------------

    def open_picker(self, startup: bool = False) -> None:
        if self.busy:
            return

        def thumbnail(persona, box):
            path = self.art.image_path("neutral", persona.id, full=False)
            return self.art.load(path, box) if path else None

        def picked(persona_id: str, remember: bool) -> None:
            if startup:
                self._reveal()  # first, so a later error cannot leave the app invisible
            self._update_settings(pick_on_start=not remember)
            if startup or persona_id != self.persona.id:
                self.switch_persona(persona_id)
            if startup:
                self.after(BRIEFING_DELAY_MS, self.brief_today)
                for index, (message, expression) in enumerate(self._held_notices):
                    self.after(HELD_NOTICE_DELAY_MS + index * HELD_NOTICE_GAP_MS, lambda m=message, e=expression: self.say(m, e))
                self._held_notices.clear()

        try:
            CharacterPicker(self, PERSONAS.values(), self.persona.id, thumbnail, picked, remember=not self.settings.pick_on_start)
        except Exception:  # noqa: BLE001 - start with the last character instead of staying hidden
            self.report_callback_exception(*sys.exc_info())
            if startup:
                picked(self.persona.id, not self.settings.pick_on_start)

    def switch_persona(self, persona_id: str) -> None:
        if self.busy:
            return
        self._update_settings(persona_id=persona_id)
        self.chat.set_hint(self._idle_hint())
        self.expression = "neutral"
        self._render_character()
        self.talk(random.choice(self.persona.greetings), "happy")

    def ask_user_name(self) -> None:
        name = simpledialog.askstring("내 이름", "캐릭터가 알고 있을 이름을 입력하세요.", initialvalue=self.settings.user_name, parent=self)
        if name is not None:
            self._update_settings(user_name=name.strip())
            self.say("이름, 기억해 둘게요." if name.strip() else "알겠어요.", "happy")

    def ask_model(self) -> None:
        try:
            installed = OllamaClient(self.settings.ollama_url, timeout=5).list_models()
        except Exception:  # noqa: BLE001 - the list is only a hint
            installed = []
        hint = ", ".join(installed) if installed else "(설치된 모델을 확인하지 못했습니다)"
        model = simpledialog.askstring(
            "AI 모델",
            f"사용할 Ollama 모델 이름\n설치됨: {hint}",
            initialvalue=self.settings.model,
            parent=self,
        )
        if model and model.strip():
            self._update_settings(model=model.strip())
            threading.Thread(target=self._check_model, daemon=True).start()

    def show_log(self) -> None:
        persona_id = self.persona.id
        ConversationLogWindow(self, self.store, self.persona, lambda size, bg: self.art.face(persona_id, size, bg))

    def clear_memory(self) -> None:
        if messagebox.askyesno("기억 지우기", f"{self.persona.name}와의 대화 기록을 모두 지울까요?", parent=self):
            self.store.clear(self.persona.id)
            self.say("...처음 뵙겠습니다?", "surprised")

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


def run_mascot() -> None:
    MascotApp().mainloop()

