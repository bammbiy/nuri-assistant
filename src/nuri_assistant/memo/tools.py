from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..companion.toolbox import ConfirmingTools, clean_args, unknown_tool
from .store import MemoStore


MAX_LENGTH = 120

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "사용자가 앞으로도 변하지 않을 개인 사실이나 취향(알레르기, 생일, 좋아하는 음식, 직업, 반려동물 등)을 알려 줄 때 호출한다. 일정이나 할 일에는 쓰지 않는다. 사용자가 확인 버튼을 눌러야 저장된다.",
            "parameters": {
                "type": "object",
                "properties": {"fact": {"type": "string", "description": "기억할 내용을 짧은 한 문장으로. 예: 고양이 알레르기가 있음"}},
                "required": ["fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget_fact",
            "description": "기억해 둔 내용을 잊어 달라고 할 때 호출한다. 사용자가 확인 버튼을 눌러야 지워진다.",
            "parameters": {
                "type": "object",
                "properties": {"keyword": {"type": "string", "description": "기억 내용 일부"}},
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_facts",
            "description": "기억하고 있는 사용자 정보를 볼 때 호출한다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


@dataclass(frozen=True)
class MemoAction:
    kind: str  # "add" | "delete"
    text: str
    memo_id: int | None = None

    @property
    def heading(self) -> str:
        return {"add": "기억해 둘게요", "delete": "기억 지우기"}[self.kind]

    @property
    def when(self) -> str:
        return "기억 수첩"

    @property
    def title(self) -> str:
        return self.text


class MemoTools(ConfirmingTools[MemoAction]):
    specs = TOOL_SPECS
    action_type = MemoAction

    def __init__(self, store: MemoStore) -> None:
        super().__init__()
        self.store = store

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        args = clean_args(arguments)
        if name == "remember_fact":
            return self._remember(str(args.get("fact", "")))
        if name == "forget_fact":
            return self._forget(str(args.get("keyword", "")))
        if name == "list_facts":
            memos = self.store.all()
            return {"ok": True, "count": len(memos), "facts": [memo.text for memo in memos]}
        return unknown_tool(name)

    def _remember(self, fact: str) -> dict[str, Any]:
        text = fact.strip()
        if not text:
            return {"ok": False, "error": "기억할 내용이 필요해요."}
        if len(text) > MAX_LENGTH:
            return {"ok": False, "error": f"너무 길어요. {MAX_LENGTH}자 안으로 줄여서 다시 호출한다."}
        if any(memo.text.casefold() == text.casefold() for memo in self.store.all()):
            return {"ok": False, "error": "이미 기억하고 있어요"}
        if any(action.kind == "add" and action.text.casefold() == text.casefold() for action in self.pending):
            return {"ok": False, "error": "이미 기억하려고 확인을 기다리는 내용이에요"}
        self.pending.append(MemoAction("add", text))
        return {"ok": True, "status": "사용자 확인 대기 중 (아직 저장되지 않음)", "fact": text}

    def _forget(self, keyword: str) -> dict[str, Any]:
        matches = self.store.find(keyword)
        if not matches:
            return {"ok": False, "error": "그런 기억이 없어요."}
        if len(matches) > 1:
            return {"ok": False, "error": "여러 개가 해당돼요. 어떤 것인지 물어본다.", "candidates": [m.text for m in matches]}
        memo = matches[0]
        self.pending.append(MemoAction("delete", memo.text, memo.id))
        return {"ok": True, "status": "사용자 확인 대기 중", "fact": memo.text}

    def confirm(self, action: MemoAction) -> str:
        if action.kind == "add":
            memo = self.store.add(action.text)
            return f"기억해 둘게요: {memo.text}"
        if action.memo_id is not None and self.store.delete(action.memo_id):
            return f"잊어버릴게요: {action.text}"
        return "이미 없는 기억이에요."
