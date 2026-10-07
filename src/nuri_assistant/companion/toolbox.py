from __future__ import annotations

from typing import Any, Generic, Protocol, TypeVar

# Typed answers that settle a confirm card without asking the model.
YES_WORDS = frozenset({"응", "어", "네", "넵", "넹", "예", "웅", "ㅇㅇ", "ㅇ", "좋아", "그래", "등록", "등록해", "삭제", "삭제해", "확인", "오케이", "ok", "okay"})
NO_WORDS = frozenset({"아니", "아니요", "아뇨", "ㄴㄴ", "ㄴ", "취소", "됐어", "싫어", "노", "no"})


def parse_confirmation(text: str) -> bool | None:
    """True/False for a typed yes/no ("응!", "아니요."), None when it is a normal message."""

    answer = text.strip().strip(" .!~?").lower()
    if answer in YES_WORDS:
        return True
    if answer in NO_WORDS:
        return False
    return None


def unknown_tool(name: str) -> dict[str, Any]:
    return {"ok": False, "error": f"알 수 없는 도구: {name}"}


def clean_args(arguments: dict[str, Any]) -> dict[str, Any]:
    """Drop arguments the model sent as null or empty string, so defaults apply."""

    return {key: value for key, value in arguments.items() if value not in (None, "")}


class ConfirmableAction(Protocol):
    """What the confirm card reads from any provider's pending action (schedule, todo, price watch)."""

    kind: str  # add | done | cancel | delete
    heading: str
    when: str
    title: str


class ToolProvider(Protocol):
    specs: list[dict[str, Any]]

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...
    def take_pending(self) -> list[Any]: ...
    def owns(self, action: object) -> bool: ...
    def confirm(self, action: Any) -> str: ...


A = TypeVar("A")


class ConfirmingTools(Generic[A]):
    """Shared plumbing for providers whose changes wait for the confirm card.

    Subclasses set ``action_type`` and append to ``self.pending``; MascotApp collects the
    actions with take_pending() and hands approved ones back through ToolBox.confirm().
    """

    action_type: type

    def __init__(self) -> None:
        self.pending: list[A] = []

    def owns(self, action: object) -> bool:
        return isinstance(action, self.action_type)

    def take_pending(self) -> list[A]:
        pending, self.pending = self.pending, []
        return pending


class ToolBox:
    """Routes the model's tool calls to the feature that owns each tool (schedule, prices...)."""

    def __init__(self, providers: list[ToolProvider]) -> None:
        self.providers = providers

    @property
    def specs(self) -> list[dict[str, Any]]:
        return [spec for provider in self.providers for spec in provider.specs]

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        for provider in self.providers:
            if any(spec["function"]["name"] == name for spec in provider.specs):
                return provider.execute(name, arguments)
        return unknown_tool(name)

    def take_pending(self) -> list[Any]:
        return [action for provider in self.providers for action in provider.take_pending()]

    def confirm(self, action: Any) -> str:
        for provider in self.providers:
            if provider.owns(action):
                return provider.confirm(action)
        raise ValueError(f"No tool provider owns {action!r}")
