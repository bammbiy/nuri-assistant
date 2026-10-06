from __future__ import annotations

import queue
import random
import sys
import threading
import time
import tkinter as tk
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from ..companion import (
    EXPRESSIONS,
    PERSONAS,
    Companion,
    ConversationStore,
    OllamaClient,
    get_persona,
    load_settings,
    save_settings,
)
from ..schedule import Event, PendingAction, ScheduleStore, ScheduleTools
from ..storage import HistoryStore
from .assistant import AssistantWindow
from .desktop import APP_DIR, DB_PATH, NuriAssistantApp
from .chatbox import HEIGHT as CHAT_HEIGHT, ChatBox, draw_pill, subject_particle
from .confirm_card import HEIGHT as CARD_HEIGHT, ConfirmCard
from .picker import CharacterPicker
from .placeholder import PLACEHOLDER_HEIGHT, draw_emote, draw_placeholder
from .schedule_window import ScheduleWindow


ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets" / "characters"
SETTINGS_PATH = APP_DIR / "companion.json"
MEMORY_PATH = APP_DIR / "companion.sqlite3"

WIDTH = 360
CANVAS_HEIGHT = 560
# The chat box appears right under the character, in the strip below CHAR_BOTTOM.
CHAR_BOTTOM = CANVAS_HEIGHT - CHAT_HEIGHT - 18
CHAR_TOP = CHAR_BOTTOM - PLACEHOLDER_HEIGHT
# Images may rise behind the bubble area so a bust-up drawing is shown large.
CHAR_BOX = (WIDTH - 10, CHAR_BOTTOM - 130)
CHAT_HIDE_DELAY_MS = 1200
REMINDER_POLL_MS = 20_000
BRIEFING_DELAY_MS = 4500
# Typed answers that settle a confirm card without asking the model.
YES_WORDS = {"응", "어", "네", "넵", "넹", "예", "웅", "ㅇㅇ", "ㅇ", "좋아", "그래", "등록", "등록해", "삭제", "삭제해", "확인", "오케이", "ok", "okay"}
NO_WORDS = {"아니", "아니요", "아뇨", "ㄴㄴ", "ㄴ", "취소", "됐어", "싫어", "노", "no"}
# Windows keys this exact color out of the window. A near-black key keeps
# anti-aliased PNG edges looking like line art instead of a colored halo.
TRANSPARENT_KEY = "#010203"
FALLBACK_BG = "#f3eff7"
BUBBLE_FONT = ("Malgun Gothic", 11) if sys.platform == "win32" else ("TkDefaultFont", 11)
BUBBLE_TEXT = "#2f2640"
BUBBLE_LINE = "#c9b6ea"
BUBBLE_SHADOW = "#e7def5"
BUBBLE_PLATE = "#9b7fdc"


class MascotApp(tk.Tk):
    """Desktop companion: an always-on-top character that chats through a local model."""

    def __init__(self, app_dir: Path = APP_DIR) -> None:
        super().__init__()
        self.settings_path = app_dir / SETTINGS_PATH.name
        self.settings = load_settings(self.settings_path)
        self.store = ConversationStore(app_dir / MEMORY_PATH.name)
        self.schedule = ScheduleStore(app_dir / MEMORY_PATH.name)
        self.schedule_tools = ScheduleTools(self.schedule)
        self.pending_actions: list[PendingAction] = []
        self.history = HistoryStore(app_dir / DB_PATH.name)
        self.user_dir = app_dir / "characters"
        self.events: queue.Queue[tuple] = queue.Queue()
        self.companion = self._make_companion()

        self.expression = "neutral"
        self.head_top = CHAR_TOP
        self._bubble_text = ""
        self._relax_token = 0
        self.talking = False
        self.mouth_open = False
        self.blinking = False
        self.busy = False
        self._images: dict[tuple[Path, tuple[int, int]], tk.PhotoImage | None] = {}
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
            self.say(random.choice(self.persona.greetings), "happy")
            self.after(BRIEFING_DELAY_MS, self.brief_today)
        self.after(50, self._drain_events)
        self.after(5000, self._check_reminders)
        self.after(3500, self._blink)
        self.after(120, self._watch_pointer)
        threading.Thread(target=self._check_model, daemon=True).start()

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
            tools=self.schedule_tools,
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
        self.canvas = tk.Canvas(self, width=WIDTH, height=CANVAS_HEIGHT, bg=self.bg, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.canvas.tag_bind("character", "<ButtonPress-1>", self._on_press)
        self.canvas.tag_bind("character", "<B1-Motion>", self._on_drag)
        self.canvas.tag_bind("character", "<ButtonRelease-1>", self._on_release)
        self.canvas.tag_bind("bubble", "<Button-1>", lambda _event: self._show_bubble(""))
        self.canvas.bind("<Button-3>", self._show_menu)
        if sys.platform == "darwin":
            self.canvas.bind("<Button-2>", self._show_menu)

        self.chat = ChatBox(
            self.canvas, 20, CHAR_BOTTOM + 6, WIDTH - 40,
            on_send=self.send,
            on_menu=lambda x, y: self.menu.tk_popup(x, y),
        )
        self.chat.set_hint(self._idle_hint())
        # Confirm cards sit over the character's chest, just above the chat box.
        self.card = ConfirmCard(self.canvas, 20, CHAR_BOTTOM - CARD_HEIGHT - 4, WIDTH - 40)

        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label="비서 선택…", command=self.open_picker)
        self.menu.add_command(label="내 이름 설정", command=self.ask_user_name)
        self.menu.add_command(label="AI 모델 설정", command=self.ask_model)
        self.menu.add_separator()
        self.menu.add_command(label="일정 보기", command=lambda: ScheduleWindow(self, self.schedule))
        self.menu.add_command(label="오늘 일정 브리핑", command=lambda: self.brief_today(force=True))
        self.menu.add_separator()
        self.menu.add_command(label="대화 기록 보기", command=self.show_log)
        self.menu.add_command(label="이 캐릭터의 기억 지우기", command=self.clear_memory)
        self.menu.add_separator()
        self.menu.add_command(label="파일 정리 도구", command=lambda: NuriAssistantApp(self, history=self.history))
        self.menu.add_command(label="파일/구매 비서", command=lambda: AssistantWindow(self, self.history))
        self.menu.add_separator()
        self.menu.add_command(label="종료", command=self.quit_app)

    def _place_window(self) -> None:
        self.update_idletasks()
        height = self.winfo_reqheight()
        x, y = self.settings.x, self.settings.y
        if x is None or y is None:
            x = self.winfo_screenwidth() - WIDTH - 40
            y = self.winfo_screenheight() - height - 60
        x = min(max(int(x), 0), max(self.winfo_screenwidth() - WIDTH, 0))
        y = min(max(int(y), 0), max(self.winfo_screenheight() - height, 0))
        self.geometry(f"+{x}+{y}")

    def _on_press(self, event: tk.Event) -> None:
        self._drag_start = (event.x_root, event.y_root, self.winfo_x(), self.winfo_y())
        self._dragged = False

    def _on_drag(self, event: tk.Event) -> None:
        if self._drag_start is None:
            return
        start_x, start_y, win_x, win_y = self._drag_start
        dx, dy = event.x_root - start_x, event.y_root - start_y
        if abs(dx) + abs(dy) > 4:
            self._dragged = True
        if self._dragged:
            self.geometry(f"+{win_x + dx}+{win_y + dy}")

    def _on_release(self, _event: tk.Event) -> None:
        self._drag_start = None
        if self._dragged:
            self._update_settings(x=self.winfo_x(), y=self.winfo_y())
        elif not self.busy:
            self.say(random.choice(self.persona.pokes), random.choice(("surprised", "shy", "happy")))
            self.chat.focus()

    def _show_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def _idle_hint(self) -> str:
        return f"{self.persona.name}에게 말 걸기…"

    def _watch_pointer(self) -> None:
        """Show the chat box while the mouse is on the character (or the box itself)."""

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
        self.after(120, self._watch_pointer)

    # ----- character --------------------------------------------------------------

    def _image_path(self, name: str, persona_id: str | None = None) -> Path | None:
        persona_id = persona_id or self.persona.id
        for folder in (self.user_dir / persona_id, ASSETS_DIR / persona_id):
            path = folder / f"{name}.png"
            if path.exists():
                return path
        return None

    def _image_for(self, expression: str, talking: bool, blinking: bool) -> tuple[tk.PhotoImage | None, bool]:
        """Return the frame to show and whether the expression itself has art.

        A missing expression falls back to neutral; its talk/blink variants still
        animate, and the caller adds an emote mark so the mood stays readable.
        """

        has_expression = self._image_path(expression) is not None
        base = expression if has_expression else "neutral"
        names = ([f"{base}_talk"] if talking else []) + ([f"{base}_blink"] if blinking else []) + [base]
        for name in names:
            path = self._image_path(name)
            if path is not None:
                image = self._load_image(path)
                if image is not None:
                    return image, has_expression
        return None, False

    def _load_image(self, path: Path, box: tuple[int, int] = CHAR_BOX) -> tk.PhotoImage | None:
        if (path, box) in self._images:
            return self._images[(path, box)]
        image: tk.PhotoImage | None
        try:
            from PIL import Image, ImageTk  # optional: smoother resizing when Pillow is installed

            picture = Image.open(path).convert("RGBA")
            picture.thumbnail(box, Image.LANCZOS)
            image = ImageTk.PhotoImage(picture, master=self)
        except ImportError:
            try:
                image = _fit_photo(tk.PhotoImage(master=self, file=str(path)), box)
            except tk.TclError:
                image = None
        except OSError:
            image = None
        self._images[(path, box)] = image
        return image

    def _render_character(self) -> None:
        mouth = self.talking and self.mouth_open
        image, has_expression = self._image_for(self.expression, mouth, self.blinking)
        if image is None:
            head_top = CHAR_TOP
            draw_placeholder(self.canvas, WIDTH // 2, CHAR_TOP, self.persona.look, self.expression, mouth, self.blinking)
        else:
            top = CHAR_BOTTOM - image.height()
            head_top = top + 12
            self.canvas.delete("character")
            self.canvas.create_image(WIDTH // 2, CHAR_BOTTOM, anchor="s", image=image, tags="character")
            if not has_expression:
                draw_emote(self.canvas, WIDTH // 2 + int(image.width() * 0.3), top + int(image.height() * 0.2), self.expression)
        if head_top != self.head_top:
            # Art of a different height: keep the bubble tail touching the head.
            self.head_top = head_top
            self._show_bubble(self._bubble_text)
        # Freshly drawn character items would otherwise cover the overlays.
        for overlay in ("bubble", "confirm", "chat"):
            self.canvas.tag_raise(overlay)

    def set_expression(self, expression: str) -> None:
        if expression in EXPRESSIONS and expression != self.expression:
            self.expression = expression
            self._render_character()

    def _blink(self) -> None:
        if not self.blinking:
            self.blinking = True
            self._render_character()
            self.after(140, self._blink)
            return
        self.blinking = False
        self._render_character()
        self.after(random.randint(2500, 6000), self._blink)

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
        self._render_character()
        self.after(130, self._flap)

    # ----- speech bubble ----------------------------------------------------------

    def say(self, text: str, expression: str | None = None) -> None:
        if expression:
            self.set_expression(expression)
            self._relax_later(6000 + min(len(text) * 60, 9000))
        self._show_bubble(text)

    def _relax_later(self, delay_ms: int) -> None:
        """Return to the neutral face a while after speaking, so moods do not stick."""

        self._relax_token += 1
        token = self._relax_token

        def relax() -> None:
            if token != self._relax_token:
                return
            if self.busy:
                self._relax_later(2000)
            else:
                self.set_expression("neutral")

        self.after(delay_ms, relax)

    def _hide_bubble(self) -> None:
        self.canvas.delete("bubble")

    def _show_bubble(self, text: str) -> None:
        self._hide_bubble()
        self._bubble_text = text
        if not text:
            return
        canvas = self.canvas
        cx, bottom = WIDTH // 2, self.head_top - 18
        item = canvas.create_text(cx, bottom, text=text, width=WIDTH - 64, anchor="s", font=BUBBLE_FONT,
                                  fill=BUBBLE_TEXT, justify="left", tags="bubble")
        # Long replies keep their latest part visible; the full text is in the chat log.
        shown = text
        while canvas.bbox(item)[1] < 34 and len(shown) > 20:
            shown = shown[max(len(shown) // 10, 1):]
            canvas.itemconfigure(item, text="…" + shown.lstrip())

        # Visual-novel style name plate on the top-left edge.
        plate = canvas.create_text(0, 0, text=self.persona.name, font=(BUBBLE_FONT[0], 9, "bold"), fill="#ffffff", tags="bubble")
        plate_w = canvas.bbox(plate)[2] - canvas.bbox(plate)[0] + 22
        x1, y1, x2, y2 = canvas.bbox(item)
        pad_x, pad_top, pad_bottom = 16, 16, 12
        bx1, by1, bx2, by2 = x1 - pad_x, y1 - pad_top, x2 + pad_x, y2 + pad_bottom
        if bx2 - bx1 < plate_w + 40:
            grow = (plate_w + 40 - (bx2 - bx1)) // 2 + 1
            bx1, bx2 = bx1 - grow, bx2 + grow

        _round_rect(canvas, bx1, by1 + 3, bx2, by2 + 3, 16, fill=BUBBLE_SHADOW, outline="", tags="bubble")
        canvas.create_polygon(cx - 9, by2 - 2, cx + 9, by2 - 2, cx + 3, self.head_top + 4,
                              fill="#ffffff", outline=BUBBLE_LINE, width=2, tags="bubble")
        _round_rect(canvas, bx1, by1, bx2, by2, 16, fill="#ffffff", outline=BUBBLE_LINE, width=2, tags="bubble")
        # Open the outline where the tail joins the bubble.
        canvas.create_line(cx - 7, by2, cx + 8, by2, fill="#ffffff", width=3, tags="bubble")
        draw_pill(canvas, bx1 + 14, by1 - 11, bx1 + 14 + plate_w, by1 + 11, fill=BUBBLE_PLATE, tags="bubble")
        canvas.coords(plate, bx1 + 14 + plate_w / 2, by1)
        canvas.tag_raise(plate)
        canvas.tag_raise(item)

    # ----- conversation -----------------------------------------------------------

    def send(self) -> None:
        text = self.chat.text().strip()
        if not text or self.busy:
            return
        self.chat.clear()
        if self.card.visible:
            answer = text.strip(" .!~?").lower()
            if answer in YES_WORDS or answer in NO_WORDS:
                self._resolve_card(answer in YES_WORDS)
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
        self.events.put(("done", reply.text, reply.expression, reply.actions))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, *values = self.events.get_nowait()
                if kind == "update":
                    visible, expression = values
                    if visible:
                        self._start_talking()
                        self.say(visible, expression)
                elif kind == "done":
                    text, expression, actions = values
                    self.talking = False
                    self.say(text, expression)
                    self._set_busy(False)
                    if actions:
                        self.pending_actions = list(actions)
                        self._show_next_card()
                elif kind == "error":
                    self.talking = False
                    self.say(f"앗, 문제가 생겼어요.\n{values[0]}", "sad")
                    self._set_busy(False)
                elif kind == "notice":
                    message, expression = values
                    self.say(message, expression)
        except queue.Empty:
            pass
        self.after(50, self._drain_events)

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

    # ----- schedule -----------------------------------------------------------------

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
            message = self.schedule_tools.confirm(action)
            self.companion.note(message)
            self.say(message, "happy")
        else:
            message = f"알겠어요, '{action.title}' {'등록은' if action.kind == 'add' else '취소는'} 하지 않을게요."
            self.companion.note(message, "neutral")
            self.say(message, "neutral")
        self._show_next_card()

    def _check_reminders(self) -> None:
        if self.state() != "withdrawn" and not self.busy:
            now = datetime.now()
            due = self.schedule.due_reminders(now)
            if due:
                # One per poll so bubbles do not overwrite each other; the rest stay due.
                event = due[0]
                self.schedule.mark_reminded(event.id)
                self.say(self.persona.reminder.format(when=_until(event, now), title=event.title), "surprised")
                self.bell()
        self.after(REMINDER_POLL_MS, self._check_reminders)

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
        if not events:
            if force:
                self.say("오늘은 등록된 일정이 없어요.", "neutral")
            return
        lines = [f"· {'하루 종일' if e.all_day else e.start.strftime('%H:%M')} {e.title}" for e in events[:5]]
        if len(events) > 5:
            lines.append(f"· 외 {len(events) - 5}개")
        self.say(self.persona.briefing.format(count=len(events)) + "\n" + "\n".join(lines), "happy")

    # ----- menu actions -----------------------------------------------------------

    def open_picker(self, startup: bool = False) -> None:
        if self.busy:
            return

        def thumbnail(persona, box):
            path = self._image_path("neutral", persona.id)
            return self._load_image(path, box) if path else None

        def picked(persona_id: str, remember: bool) -> None:
            self._update_settings(pick_on_start=not remember)
            if startup:
                # Borderless windows need the flag re-applied after being withdrawn (Windows).
                self.overrideredirect(True)
                self.deiconify()
                self.attributes("-topmost", True)
            if startup or persona_id != self.persona.id:
                self.switch_persona(persona_id)
            if startup:
                self.after(BRIEFING_DELAY_MS, self.brief_today)

        CharacterPicker(self, PERSONAS.values(), self.persona.id, thumbnail, picked, remember=not self.settings.pick_on_start)

    def switch_persona(self, persona_id: str) -> None:
        if self.busy:
            return
        self._update_settings(persona_id=persona_id)
        self.chat.set_hint(self._idle_hint())
        self.expression = "neutral"
        self._render_character()
        self.say(random.choice(self.persona.greetings), "happy")

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
        window = tk.Toplevel(self)
        window.title(f"{self.persona.name} 대화 기록")
        window.geometry("520x560")
        text = tk.Text(window, wrap="word", padx=10, pady=10)
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        rows = self.store.recent(self.persona.id, limit=500)
        if not rows:
            text.insert("end", "아직 대화가 없습니다.")
        for row in rows:
            speaker = "나" if row["role"] == "user" else self.persona.name
            content = row["content"]
            if row["role"] == "assistant" and content.startswith("["):
                content = content.split("]", 1)[-1].strip()
            text.insert("end", f"[{row['created_at']}] {speaker}\n{content}\n\n")
        text.configure(state="disabled")
        text.see("end")

    def clear_memory(self) -> None:
        if messagebox.askyesno("기억 지우기", f"{self.persona.name}와의 대화 기록을 모두 지울까요?", parent=self):
            self.store.clear(self.persona.id)
            self.say("...처음 뵙겠습니다?", "surprised")

    def destroy(self) -> None:
        # Cancel animation/polling timers so none fires into a destroyed interpreter.
        for after_id in self.tk.splitlist(self.tk.call("after", "info")):
            self.after_cancel(after_id)
        super().destroy()

    def quit_app(self) -> None:
        self._update_settings(x=self.winfo_x(), y=self.winfo_y())
        self.destroy()


def _fit_photo(image: tk.PhotoImage, box: tuple[int, int]) -> tk.PhotoImage:
    """Scale into box with Tk's integer zoom/subsample (used when Pillow is absent)."""

    target = min(box[0] / image.width(), box[1] / image.height(), 1.0)
    if target >= 1.0:
        return image
    zoom, sub = max(
        ((z, s) for s in range(1, 7) for z in range(1, s + 1) if z / s <= target),
        key=lambda pair: pair[0] / pair[1],
    )
    if zoom > 1:
        image = image.zoom(zoom)
    return image.subsample(sub) if sub > 1 else image


def run_mascot() -> None:
    MascotApp().mainloop()


def _until(event: Event, now: datetime) -> str:
    """'10분 뒤에', '1시간 뒤에', '지금', or '오늘' for all-day events."""

    if event.all_day:
        return "오늘"
    minutes = max(round((event.start - now).total_seconds() / 60), 0)
    if minutes == 0:
        return "지금"
    if minutes < 60:
        return f"{minutes}분 뒤에"
    hours, rest = divmod(minutes, 60)
    return f"{hours}시간 {rest}분 뒤에" if rest else f"{hours}시간 뒤에"


def _round_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, r: int, **options: object) -> None:
    points = (
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
        x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    )
    canvas.create_polygon(*points, smooth=True, **options)
