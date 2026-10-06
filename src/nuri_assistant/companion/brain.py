from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from typing import Any

from .llm import OllamaClient, OllamaToolsUnsupported, ToolCall
from .memory import ConversationStore
from .personas import Persona
from .reply import ReplyParser
from .toolbox import ToolBox


WEEKDAYS = "월화수목금토일"
# Model -> tool -> model rounds per message; a small model can loop on tool calls.
MAX_TOOL_ROUNDS = 4


@dataclass(frozen=True)
class CompanionReply:
    text: str
    expression: str
    # Changes the model proposed (schedule, price watch); the UI asks the user to confirm each one.
    actions: tuple[Any, ...] = ()


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
        tools: ToolBox | None = None,
    ) -> None:
        self.persona = persona
        self.client = client
        self.store = store
        self.model = model
        self.user_name = user_name
        self.history_limit = history_limit
        self.clock = clock
        self.tools = tools
        # Turned off for the session if the model turns out not to support tool calls.
        self.tools_supported = tools is not None

    def build_messages(self, user_text: str) -> list[dict[str, str]]:
        now = self.clock()
        stamp = f"{now:%Y-%m-%d} ({WEEKDAYS[now.weekday()]}) {now:%H:%M}"
        system = self.persona.system_prompt(self.user_name, stamp, tools=self.tools_supported)
        messages = [{"role": "system", "content": system}]
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
        messages: list[dict] = self.build_messages(text)
        visible, expression = "", "neutral"
        for _round in range(MAX_TOOL_ROUNDS):
            tools = self.tools.specs if self.tools_supported and self.tools is not None else None
            parser = ReplyParser(default_expression=expression)
            calls: list[ToolCall] = []
            try:
                for item in self.client.chat_stream(self.model, messages, tools=tools):
                    if isinstance(item, ToolCall):
                        calls.append(item)
                        continue
                    shown = parser.feed(item)
                    if on_update is not None and shown:
                        on_update(shown, parser.expression)
            except OllamaToolsUnsupported:
                self.tools_supported = False
                messages[0] = self.build_messages(text)[0]
                continue
            round_text = parser.finish()
            if round_text:
                visible, expression = round_text, parser.expression
            if not calls or self.tools is None:
                break
            messages.append({
                "role": "assistant",
                "content": parser.raw,
                "tool_calls": [{"function": {"name": call.name, "arguments": call.arguments}} for call in calls],
            })
            for call in calls:
                result = self.tools.execute(call.name, call.arguments)
                messages.append({"role": "tool", "tool_name": call.name, "content": json.dumps(result, ensure_ascii=False)})

        actions = tuple(self.tools.take_pending()) if self.tools is not None else ()
        if not visible:
            visible = "아래에서 확인해 주세요." if actions else "..."
        self.store.add(self.persona.id, "user", text)
        # Keep the tag in memory so the model sees its own format in the history.
        self.store.add(self.persona.id, "assistant", f"[{expression}] {visible}")
        return CompanionReply(visible, expression, actions)

    def note(self, text: str, expression: str = "happy") -> None:
        """Record something the app did on the character's behalf (e.g. a confirmed event)."""

        self.store.add(self.persona.id, "assistant", f"[{expression}] {text}")
