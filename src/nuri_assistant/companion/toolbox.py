from __future__ import annotations

from typing import Any, Protocol


class ToolProvider(Protocol):
    specs: list[dict[str, Any]]

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...
    def take_pending(self) -> list[Any]: ...
    def owns(self, action: object) -> bool: ...
    def confirm(self, action: Any) -> str: ...


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
        return {"ok": False, "error": f"알 수 없는 도구: {name}"}

    def take_pending(self) -> list[Any]:
        return [action for provider in self.providers for action in provider.take_pending()]

    def confirm(self, action: Any) -> str:
        for provider in self.providers:
            if provider.owns(action):
                return provider.confirm(action)
        raise ValueError(f"No tool provider owns {action!r}")
