from __future__ import annotations

import random
from datetime import datetime
from typing import Any, Callable

from ..companion.toolbox import unknown_tool
from .fortune import fortune_text, today_fortune
from .rps import normalize, play


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "today_fortune",
            "description": "사용자가 오늘의 운세를 물을 때 호출한다. 결과는 코드가 정했으니 바꾸지 말고 "
                           "캐릭터 말투로 그대로 전해 준다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_rps",
            "description": "사용자가 가위바위보를 할 때 호출한다. 사용자가 낸 것을 choice에 넘기면 "
                           "승패는 코드가 정한다. 결과를 캐릭터 말투로 알려 준다.",
            "parameters": {
                "type": "object",
                "properties": {"choice": {"type": "string", "description": "사용자가 낸 것: 가위, 바위, 보"}},
                "required": ["choice"],
            },
        },
    },
]


class FunTools:
    """Fun tools act immediately and store nothing."""

    specs = TOOL_SPECS

    def __init__(self, persona_id: Callable[[], str], clock: Callable[[], datetime] = datetime.now,
                 rng: random.Random | None = None) -> None:
        self.persona_id = persona_id
        self.clock = clock
        self.rng = rng or random.Random()

    def owns(self, action: object) -> bool:
        return False

    def take_pending(self) -> list:
        return []

    def confirm(self, action: object) -> str:
        raise ValueError("Fun tool actions need no confirmation")

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "today_fortune":
            fortune = today_fortune(self.clock().date(), self.persona_id())
            return {"ok": True, "stars": fortune.stars, "color": fortune.color, "item": fortune.item,
                    "advice": fortune.advice, "text": fortune_text(fortune)}
        if name == "play_rps":
            choice = normalize(arguments.get("choice"))
            if choice is None:
                return {"ok": False, "error": "가위, 바위, 보 중에 하나를 내 달라고 물어보세요."}
            computer, result = play(choice, self.rng)
            return {"ok": True, "user": choice, "computer": computer, "result": result}
        return unknown_tool(name)
