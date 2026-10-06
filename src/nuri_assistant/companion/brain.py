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
    # Japanese line for text-to-speech (empty unless voice is on and the model wrote one).
    voice: str = ""


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
        voice: bool = False,
    ) -> None:
        self.persona = persona
        self.client = client
        self.store = store
        self.model = model
        self.user_name = user_name
        self.history_limit = history_limit
        self.clock = clock
        self.tools = tools
        self.voice = voice
        # Turned off for the session if the model turns out not to support tool calls.
        self.tools_supported = tools is not None

    def build_messages(self, user_text: str) -> list[dict[str, str]]:
        now = self.clock()
        stamp = f"{now:%Y-%m-%d} ({WEEKDAYS[now.weekday()]}) {now:%H:%M}"
        system = self.persona.system_prompt(self.user_name, stamp, tools=self.tools_supported, voice=self.voice)
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
        visible, expression, spoken = "", "neutral", ""
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
                visible, expression, spoken = round_text, parser.expression, parser.voice
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
        return CompanionReply(visible, expression, actions, spoken)

    def to_japanese(self, text: str) -> str:
        """Translate an app-made Korean line into the character's spoken Japanese (for TTS)."""

        messages = [
            {"role": "system", "content": (
                f"너는 '{self.persona.name}'({self.persona.archetype}) 캐릭터의 대사를 일본어로 옮기는 번역가다. "
                f"{self.persona.speech_style} 이 말투를 일본 애니메이션 캐릭터처럼 살려서, 주어진 한국어 대사를 "
                "자연스러운 일본어 구어체 한 덩어리로만 옮긴다. 설명, 따옴표, 로마자, 한국어는 쓰지 않는다."
            )},
            {"role": "user", "content": text},
        ]
        parser = ReplyParser()
        for item in self.client.chat_stream(self.model, messages):
            if isinstance(item, str):
                parser.feed(item)
        return parser.finish()

    def note(self, text: str, expression: str = "happy") -> None:
        """Record something the app did on the character's behalf (e.g. a confirmed event)."""

        self.store.add(self.persona.id, "assistant", f"[{expression}] {text}")
