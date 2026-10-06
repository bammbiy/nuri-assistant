from __future__ import annotations

import math
import queue
import random
import sys
import threading
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
from .placeholder import draw_placeholder


ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets" / "characters"
SETTINGS_PATH = APP_DIR / "companion.json"
MEMORY_PATH = APP_DIR / "companion.sqlite3"

WIDTH = 360
CHAR_TOP = 200
CANVAS_HEIGHT = 540
CHAR_BOX = (340, CANVAS_HEIGHT - CHAR_TOP)
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
        self.talking = False
        self.mouth_open = False
        self.blinking = False
        self.busy = False
        self._images: dict[Path, tk.PhotoImage | None] = {}
        self._drag_start: tuple[int, int, int, int] | None = None
        self._dragged = False

        self._setup_window()
        self._build()
        self._place_window()
        self._render_character()
        self.say(random.choice(self.persona.greetings), "happy")
        self.after(50, self._drain_events)
        self.after(3500, self._blink)
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
        self.canvas.tag_bind("bubble", "<Button-1>", lambda _event: self._hide_bubble())
        self.canvas.bind("<Button-3>", self._show_menu)
        if sys.platform == "darwin":
            self.canvas.bind("<Button-2>", self._show_menu)

        bar = tk.Frame(self, bg="#ffffff", highlightthickness=1, highlightbackground="#c9bfd6")
        bar.pack(fill="x", padx=12, pady=(0, 6))
        self.input_var = tk.StringVar()
        self.entry = ttk.Entry(bar, textvariable=self.input_var)
        self.entry.pack(side="left", fill="x", expand=True, padx=(6, 4), pady=6)
        self.entry.bind("<Return>", lambda _event: self.send())
        # Borderless windows do not always take focus on click (notably on X11).
        self.entry.bind("<Button-1>", lambda _event: self.entry.focus_force())
        self.send_button = ttk.Button(bar, text="보내기", width=6, command=self.send)
        self.send_button.pack(side="left", pady=6)
        ttk.Button(bar, text="≡", width=2, command=self._show_menu_at_button).pack(side="left", padx=(4, 6), pady=6)
        self.menu_anchor = bar

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

    def _show_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def _show_menu_at_button(self) -> None:
        self.menu.tk_popup(self.menu_anchor.winfo_rootx() + WIDTH - 60, self.menu_anchor.winfo_rooty())

    # ----- character --------------------------------------------------------------

    def _image_for(self, expression: str, talking: bool, blinking: bool) -> tk.PhotoImage | None:
        names = []
        if talking:
            names.append(f"{expression}_talk")
        if blinking:
            names.append(f"{expression}_blink")
        names += [expression, "neutral"]
        for folder in (self.user_dir / self.persona.id, ASSETS_DIR / self.persona.id):
            for name in names:
                path = folder / f"{name}.png"
                if path.exists():
                    image = self._load_image(path)
                    if image is not None:
                        return image
        return None

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
                image = tk.PhotoImage(master=self, file=str(path))
                factor = math.ceil(max(image.width() / CHAR_BOX[0], image.height() / CHAR_BOX[1], 1))
                if factor > 1:
                    image = image.subsample(factor)
            except tk.TclError:
                image = None
        except OSError:
            image = None
        self._images[path] = image
        return image

    def _render_character(self) -> None:
        mouth = self.talking and self.mouth_open
        image = self._image_for(self.expression, mouth, self.blinking)
        if image is None:
            draw_placeholder(self.canvas, WIDTH // 2, CHAR_TOP, self.persona.look, self.expression, mouth, self.blinking)
        else:
            self.canvas.delete("character")
            self.canvas.create_image(WIDTH // 2, CANVAS_HEIGHT, anchor="s", image=image, tags="character")
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
        self._show_bubble(text)

    def _hide_bubble(self) -> None:
        self.canvas.delete("bubble")

    def _show_bubble(self, text: str) -> None:
        self._hide_bubble()
        if not text:
            return
        cx, bottom = WIDTH // 2, CHAR_TOP - 18
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
        self.canvas.create_polygon(cx + 10, y2 + pad - 2, cx + 34, y2 + pad - 2, cx + 18, CHAR_TOP + 4,
                                   fill="#ffffff", outline="", tags="bubble")
        self.canvas.create_line(cx + 10, y2 + pad, cx + 18, CHAR_TOP + 4, cx + 34, y2 + pad,
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
        text = self.input_var.get().strip()
        if not text or self.busy:
            return
        self.input_var.set("")
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
        state = "disabled" if busy else "normal"
        self.entry.configure(state=state)
        self.send_button.configure(state=state)
        if not busy:
            self.entry.focus_set()

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


def run_mascot() -> None:
    MascotApp().mainloop()
