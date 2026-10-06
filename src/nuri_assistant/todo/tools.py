from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from ..schedule.timeparse import WhenError, parse_when
from .store import Todo, TodoStore


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "add_todo",
            "description": "할 일을 추가할 때 호출한다. 기한은 계산하지 말고 사용자가 말한 표현 그대로 due에 넣는다. 실제 추가는 사용자가 확인 버튼을 눌러야 끝난다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "할 일. 예: 보고서 제출"},
                    "due": {"type": "string", "description": "기한 표현 그대로. 예: 금요일까지, 내일 오후 6시. 없으면 비운다."},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_todos",
            "description": "남은 할 일 목록을 볼 때 호출한다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_todo",
            "description": "할 일을 끝냈다고 할 때 호출한다. 사용자가 확인 버튼을 눌러야 완료 처리된다.",
            "parameters": {
                "type": "object",
                "properties": {"keyword": {"type": "string", "description": "할 일 이름 일부"}},
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_todo",
            "description": "할 일을 지울 때 호출한다. 사용자가 확인 버튼을 눌러야 삭제된다.",
            "parameters": {
                "type": "object",
                "properties": {"keyword": {"type": "string", "description": "할 일 이름 일부"}},
                "required": ["keyword"],
            },
        },
    },
]


@dataclass(frozen=True)
class TodoAction:
    kind: str  # "add" | "done" | "delete"
    title: str
    due: datetime | None = None
    all_day: bool = True
    todo_id: int | None = None

    @property
    def heading(self) -> str:
        return {"add": "할 일 추가", "done": "할 일 완료", "delete": "할 일 삭제"}[self.kind]

    @property
    def when(self) -> str:
        return Todo(0, self.title, self.due, self.all_day, False).due_text


class TodoTools:
    specs = TOOL_SPECS

    def __init__(self, store: TodoStore, clock: Callable[[], datetime] = datetime.now) -> None:
        self.store = store
        self.clock = clock
        self.pending: list[TodoAction] = []

    def owns(self, action: object) -> bool:
        return isinstance(action, TodoAction)

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        args = {key: value for key, value in arguments.items() if value not in (None, "")}
        if name == "add_todo":
            return self._add(str(args.get("title", "")), str(args.get("due", "")))
        if name == "list_todos":
            today = self.clock().date()
            todos = self.store.open()
            return {"ok": True, "count": len(todos),
                    "todos": [f"{t.title} ({t.due_text}{', ' + t.d_day(today) if t.due else ''})" for t in todos]}
        if name in ("complete_todo", "delete_todo"):
            return self._pick("done" if name == "complete_todo" else "delete", str(args.get("keyword", "")))
        return {"ok": False, "error": f"알 수 없는 도구: {name}"}

    def _add(self, title: str, due: str) -> dict[str, Any]:
        if not title.strip():
            return {"ok": False, "error": "할 일 내용이 필요해요."}
        when = None
        if due.strip():
            try:
                when = parse_when(due.replace("까지", " "), self.clock())
            except WhenError as exc:
                return {"ok": False, "error": str(exc), "hint": "기한을 다시 물어본다."}
        action = TodoAction("add", title.strip(), when.start if when else None, when.all_day if when else True)
        self.pending.append(action)
        return {"ok": True, "status": "사용자 확인 대기 중 (아직 추가되지 않음)", "title": action.title, "due": action.when}

    def _pick(self, kind: str, keyword: str) -> dict[str, Any]:
        matches = [t for t in self.store.open() if keyword.strip() and keyword.strip() in t.title]
        if not matches:
            return {"ok": False, "error": "그런 할 일이 없어요."}
        if len(matches) > 1:
            return {"ok": False, "error": "여러 개가 해당돼요. 어떤 것인지 물어본다.", "candidates": [t.title for t in matches]}
        todo = matches[0]
        self.pending.append(TodoAction(kind, todo.title, todo.due, todo.all_day, todo.id))
        return {"ok": True, "status": "사용자 확인 대기 중", "title": todo.title}

    def take_pending(self) -> list[TodoAction]:
        pending, self.pending = self.pending, []
        return pending

    def confirm(self, action: TodoAction) -> str:
        if action.kind == "add":
            todo = self.store.add(action.title, action.due, action.all_day)
            return f"할 일을 추가했어요: {todo.title} ({todo.due_text})"
        if action.todo_id is None:
            return "이미 없는 할 일이에요."
        if action.kind == "done" and self.store.set_done(action.todo_id):
            return f"'{action.title}' 완료! 수고했어요."
        if action.kind == "delete" and self.store.delete(action.todo_id):
            return f"'{action.title}'을(를) 목록에서 지웠어요."
        return "이미 없는 할 일이에요."
