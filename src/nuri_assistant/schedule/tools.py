from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from .store import Event, ScheduleStore, default_remind_at
from .timeparse import WhenError, format_when, parse_range, parse_when


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "add_event",
            "description": (
                "새 일정을 등록하려 할 때 호출한다. 실제 등록은 사용자가 화면의 확인 버튼을 눌러야 끝난다. "
                "날짜와 시간은 직접 계산하지 말고 사용자가 말한 표현 그대로 when에 넣는다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "일정 이름. 예: 팀 회의, 치과"},
                    "when": {"type": "string", "description": "사용자가 말한 날짜/시간 표현 그대로. 예: 내일 오후 3시, 다음 주 화요일"},
                    "remind_minutes_before": {"type": "integer", "description": "몇 분 전에 알릴지. 사용자가 말한 경우에만."},
                },
                "required": ["title", "when"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_events",
            "description": "일정을 조회할 때 호출한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "range": {"type": "string", "description": "오늘, 내일, 이번 주, 다음 주, 이번 달, 또는 날짜. 비우면 앞으로 일주일."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_event",
            "description": "일정을 취소(삭제)하려 할 때 호출한다. 실제 삭제는 사용자가 화면의 확인 버튼을 눌러야 끝난다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "취소할 일정 이름의 일부. 예: 회의"},
                    "when": {"type": "string", "description": "일정 날짜 표현. 예: 내일. 모르면 비운다."},
                },
            },
        },
    },
]


@dataclass(frozen=True)
class PendingAction:
    """A change waiting for the user's on-screen confirmation."""

    kind: str  # "add" | "cancel"
    title: str
    start: datetime
    all_day: bool
    remind_at: datetime | None = None
    event_id: int | None = None

    @property
    def when(self) -> str:
        return format_when(self.start, self.all_day)

    @property
    def heading(self) -> str:
        return "일정 등록" if self.kind == "add" else "일정 취소"


class ScheduleTools:
    """Executes the model's schedule tool calls. Changes only become real via confirm()."""

    def __init__(self, store: ScheduleStore, clock: Callable[[], datetime] = datetime.now) -> None:
        self.store = store
        self.clock = clock
        self.pending: list[PendingAction] = []

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handler = {"add_event": self._add, "list_events": self._list, "cancel_event": self._cancel}.get(name)
        if handler is None:
            return {"ok": False, "error": f"알 수 없는 도구: {name}"}
        try:
            return handler(**{key: value for key, value in arguments.items() if value not in (None, "")})
        except TypeError as exc:
            return {"ok": False, "error": f"잘못된 인자: {exc}"}

    def _add(self, title: str, when: str, remind_minutes_before: int | None = None) -> dict[str, Any]:
        now = self.clock()
        try:
            parsed = parse_when(when, now)
        except WhenError as exc:
            return {"ok": False, "error": str(exc), "hint": "사용자에게 날짜와 시간을 다시 물어본다."}
        minutes = int(remind_minutes_before) if remind_minutes_before is not None else None
        remind_at = default_remind_at(parsed.start, parsed.all_day, now, minutes)
        action = PendingAction("add", title.strip(), parsed.start, parsed.all_day, remind_at)
        self.pending.append(action)
        return {
            "ok": True,
            "status": "사용자 확인 대기 중 (아직 등록되지 않음)",
            "title": action.title,
            "when": action.when,
            "remind": remind_at.strftime("%m/%d %H:%M") if remind_at else "없음",
        }

    def _list(self, range: str = "") -> dict[str, Any]:  # noqa: A002 - matches the tool schema
        start, end, label = parse_range(range, self.clock())
        events = self.store.between(start, end)
        return {"ok": True, "range": label, "count": len(events), "events": [f"{e.when} {e.title}" for e in events]}

    def _cancel(self, keyword: str = "", when: str = "") -> dict[str, Any]:
        now = self.clock()
        if when:
            start, end, _label = parse_range(when, now)
        else:
            start, end = now - timedelta(hours=1), now + timedelta(days=366)
        candidates = [e for e in self.store.between(start, end) if keyword.strip() in e.title]
        if not candidates:
            return {"ok": False, "error": "조건에 맞는 일정이 없어요."}
        if len(candidates) > 1:
            return {
                "ok": False,
                "error": "여러 일정이 해당돼요. 어떤 것인지 사용자에게 물어본다.",
                "candidates": [f"{e.when} {e.title}" for e in candidates[:10]],
            }
        event = candidates[0]
        action = PendingAction("cancel", event.title, event.start, event.all_day, event.remind_at, event.id)
        self.pending.append(action)
        return {"ok": True, "status": "사용자 확인 대기 중 (아직 취소되지 않음)", "title": event.title, "when": event.when}

    def take_pending(self) -> list[PendingAction]:
        pending, self.pending = self.pending, []
        return pending

    def confirm(self, action: PendingAction) -> str:
        if action.kind == "add":
            event: Event = self.store.add(action.title, action.start, action.all_day, action.remind_at)
            return f"일정을 등록했어요: {event.when} {event.title}"
        if action.event_id is not None and self.store.delete(action.event_id):
            return f"일정을 취소했어요: {action.when} {action.title}"
        return "이미 없는 일정이에요."
