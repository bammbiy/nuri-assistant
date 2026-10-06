from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .llm import OllamaClient
from .memory import ConversationStore
from .personas import Persona
from .reply import ReplyParser


WEEKDAYS = "월화수목금토일"


@dataclass(frozen=True)
class CompanionReply:
    text: str
    expression: str


class Companion:
    """Connects a persona, the local model, and the conversation memory."""

    def __init__(
        self,
        persona: Persona,
        client: OllamaClient,
        store: ConversationStore,
        model: str,
        user_name: str = "",
        history_limit: int = 20,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.persona = persona
        self.client = client
        self.store = store
        self.model = model
        self.user_name = user_name
        self.history_limit = history_limit
        self.clock = clock

    def build_messages(self, user_text: str) -> list[dict[str, str]]:
        now = self.clock()
        stamp = f"{now:%Y-%m-%d} ({WEEKDAYS[now.weekday()]}) {now:%H:%M}"
        messages = [{"role": "system", "content": self.persona.system_prompt(self.user_name, stamp)}]
        messages.extend(
            {"role": row["role"], "content": row["content"]}
            for row in self.store.recent(self.persona.id, self.history_limit)
        )
        messages.append({"role": "user", "content": user_text})
        return messages

    def reply(self, user_text: str, on_update: Callable[[str, str], None] | None = None) -> CompanionReply:
        """Stream a reply, reporting (visible_text, expression) as it grows.

        The exchange is saved only when the model answered, so a failed request
        never leaves a dangling user message in the memory.
        """

        text = user_text.strip()
        if not text:
            raise ValueError("메시지를 입력하세요.")
        parser = ReplyParser()
        for chunk in self.client.chat_stream(self.model, self.build_messages(text)):
            visible = parser.feed(chunk)
            if on_update is not None:
                on_update(visible, parser.expression)
        visible = parser.finish()
        if not visible:
            visible = "..."
        self.store.add(self.persona.id, "user", text)
        # Keep the tag in memory so the model sees its own format in the history.
        self.store.add(self.persona.id, "assistant", f"[{parser.expression}] {visible}")
        return CompanionReply(visible, parser.expression)
