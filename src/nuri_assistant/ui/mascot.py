from __future__ import annotations

import queue
import random
import sys
import threading
import time
import tkinter as tk
from dataclasses import replace
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
from ..storage import HistoryStore
from .assistant import AssistantWindow
from .desktop import APP_DIR, DB_PATH, NuriAssistantApp
from .chatbox import HEIGHT as CHAT_HEIGHT, ChatBox, subject_particle
from .placeholder import PLACEHOLDER_HEIGHT, draw_emote, draw_placeholder


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
# Windows keys this exact color out of the window. A near-black key keeps
# anti-aliased PNG edges looking like line art instead of a colored halo.
TRANSPARENT_KEY = "#010203"
FALLBACK_BG = "#f3eff7"
BUBBLE_FONT = ("Malgun Gothic", 11) if sys.platform == "win32" else ("TkDefaultFont", 11)


class MascotApp(tk.Tk):
    """Desktop companion: an always-on-top character that chats through a local model."""

    def __init__(self, app_dir: Path = APP_DIR) -> None:
        super().__init__()
        self.settings_path = app_dir / SETTINGS_PATH.name
        self.settings = load_settings(self.settings_path)
        self.store = ConversationStore(app_dir / MEMORY_PATH.name)
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
        self._images: dict[Path, tk.PhotoImage | None] = {}
        self._drag_start: tuple[int, int, int, int] | None = None
        self._dragged = False
        self._last_hover = 0.0

        self._setup_window()
        self._build()
        self._place_window()
        self._render_character()
        self.say(random.choice(self.persona.greetings), "happy")
        self.after(50, self._drain_events)
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

        self.menu = tk.Menu(self, tearoff=False)
        self.persona_var = tk.StringVar(value=self.persona.id)
        persona_menu = tk.Menu(self.menu, tearoff=False)
        for persona in PERSONAS.values():
            persona_menu.add_radiobutton(
                label=f"{persona.name} ({persona.archetype})",
                value=persona.id,
                variable=self.persona_var,
                command=lambda persona_id=persona.id: self.switch_persona(persona_id),
            )
        self.menu.add_cascade(label="캐릭터 변경", menu=persona_menu)
        self.menu.add_command(label="내 이름 설정", command=self.ask_user_name)
        self.menu.add_command(label="AI 모델 설정", command=self.ask_model)
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

    def _image_path(self, name: str) -> Path | None:
        for folder in (self.user_dir / self.persona.id, ASSETS_DIR / self.persona.id):
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

    def _load_image(self, path: Path) -> tk.PhotoImage | None:
        if path in self._images:
            return self._images[path]
        image: tk.PhotoImage | None
        try:
            from PIL import Image, ImageTk  # optional: smoother resizing when Pillow is installed

            picture = Image.open(path).convert("RGBA")
            picture.thumbnail(CHAR_BOX, Image.LANCZOS)
            image = ImageTk.PhotoImage(picture, master=self)
        except ImportError:
            try:
                image = _fit_photo(tk.PhotoImage(master=self, file=str(path)))
            except tk.TclError:
                image = None
        except OSError:
            image = None
        self._images[path] = image
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
        self.canvas.tag_raise("bubble")

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
        cx, bottom = WIDTH // 2, self.head_top - 18
        item = self.canvas.create_text(cx, bottom, text=text, width=WIDTH - 60, anchor="s", font=BUBBLE_FONT,
                                       fill="#2b2233", justify="left", tags="bubble")
        # Long replies keep their latest part visible; the full text is in the chat log.
        shown = text
        while self.canvas.bbox(item)[1] < 16 and len(shown) > 20:
            shown = shown[max(len(shown) // 10, 1):]
            self.canvas.itemconfigure(item, text="…" + shown.lstrip())
        x1, y1, x2, y2 = self.canvas.bbox(item)
        pad = 12
        self._rounded_rect(x1 - pad, y1 - pad, x2 + pad, y2 + pad, 16)
        # Tail sits at the center so it stays inside even a one-character bubble.
        self.canvas.create_polygon(cx - 9, y2 + pad - 2, cx + 9, y2 + pad - 2, cx + 3, self.head_top + 4,
                                   fill="#ffffff", outline="", tags="bubble")
        self.canvas.create_line(cx - 9, y2 + pad, cx + 3, self.head_top + 4, cx + 9, y2 + pad,
                                fill="#8a7a9e", width=2, tags="bubble")
        self.canvas.tag_raise(item)

    def _rounded_rect(self, x1: int, y1: int, x2: int, y2: int, r: int) -> None:
        points = (
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
            x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        )
        self.canvas.create_polygon(*points, smooth=True, fill="#ffffff", outline="#8a7a9e", width=2, tags="bubble")

    # ----- conversation -----------------------------------------------------------

    def send(self) -> None:
        text = self.chat.text().strip()
        if not text or self.busy:
            return
        self.chat.clear()
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
        self.events.put(("done", reply.text, reply.expression))

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
                    text, expression = values
                    self.talking = False
                    self.say(text, expression)
                    self._set_busy(False)
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

    # ----- menu actions -----------------------------------------------------------

    def switch_persona(self, persona_id: str) -> None:
        if self.busy:
            self.persona_var.set(self.persona.id)
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

    def quit_app(self) -> None:
        self._update_settings(x=self.winfo_x(), y=self.winfo_y())
        self.destroy()


def _fit_photo(image: tk.PhotoImage) -> tk.PhotoImage:
    """Scale into CHAR_BOX with Tk's integer zoom/subsample (used when Pillow is absent)."""

    target = min(CHAR_BOX[0] / image.width(), CHAR_BOX[1] / image.height(), 1.0)
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
