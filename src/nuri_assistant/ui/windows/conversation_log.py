from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...companion import ConversationStore, Persona


class ConversationLogWindow(tk.Toplevel):
    """Plain read-only transcript of one character's conversation."""

    def __init__(self, master: tk.Misc, store: ConversationStore, persona: Persona) -> None:
        super().__init__(master)
        self.title(f"{persona.name} 대화 기록")
        self.geometry("520x560")
        text = tk.Text(self, wrap="word", padx=10, pady=10)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        rows = store.recent(persona.id, limit=500)
        if not rows:
            text.insert("end", "아직 대화가 없습니다.")
        for row in rows:
            speaker = "나" if row["role"] == "user" else persona.name
            content = row["content"]
            # Stored assistant turns start with an [expression] tag.
            if row["role"] == "assistant" and content.startswith("["):
                content = content.split("]", 1)[-1].strip()
            text.insert("end", f"[{row['created_at']}] {speaker}\n{content}\n\n")
        text.configure(state="disabled")
        text.see("end")
