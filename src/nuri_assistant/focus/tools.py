from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from ..companion.toolbox import unknown_tool
from .timer import FocusTimer


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "start_focus_timer",
            "description": "집중 타이머(뽀모도로)를 시작할 때 호출한다. 예: '25분 집중 모드', '50분 집중 10분 휴식 2번'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "focus_minutes": {"type": "integer", "description": "집중 시간(분). 말하지 않으면 25"},
                    "break_minutes": {"type": "integer", "description": "휴식 시간(분). 말하지 않으면 5"},
                    "cycles": {"type": "integer", "description": "반복 횟수. 말하지 않으면 1"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop_focus_timer",
            "description": "집중 타이머를 멈출 때 호출한다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "focus_timer_status",
            "description": "집중 타이머가 얼마나 남았는지 물을 때 호출한다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


class FocusTools:
    """Timer tools act immediately: starting or stopping a timer changes nothing permanent."""

    specs = TOOL_SPECS

    def __init__(self, timer: FocusTimer, clock: Callable[[], datetime] = datetime.now) -> None:
        self.timer = timer
        self.clock = clock

    def owns(self, action: object) -> bool:
        return False

    def take_pending(self) -> list:
        return []

    def confirm(self, action: object) -> str:
        raise ValueError("Focus timer actions need no confirmation")

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        now = self.clock()
        if name == "start_focus_timer":
            def number(key: str, default: int) -> int:
                try:
                    return int(arguments.get(key) or default)
                except (TypeError, ValueError):
                    return default
            state = self.timer.start(now, number("focus_minutes", 25), number("break_minutes", 5), number("cycles", 1))
            return {"ok": True, "status": "시작함", "focus_minutes": self.timer.focus_minutes,
                    "break_minutes": self.timer.break_minutes, "cycles": state.cycles}
        if name == "stop_focus_timer":
            return {"ok": True, "status": "멈춤" if self.timer.stop() else "실행 중인 타이머 없음"}
        if name == "focus_timer_status":
            state = self.timer.state(now)
            if state.phase is None:
                return {"ok": True, "status": "실행 중인 타이머 없음"}
            return {"ok": True, "phase": "집중" if state.phase == "focus" else "휴식", "remaining": state.clock,
                    "cycle": f"{min(state.cycle, state.cycles)}/{state.cycles}"}
        return unknown_tool(name)
