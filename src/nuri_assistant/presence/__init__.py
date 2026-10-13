"""자리 비움·연속 사용 감지 (입력 시각만 읽음)."""

from .idle import idle_seconds
from .tracker import PresenceTracker

__all__ = ["PresenceTracker", "idle_seconds"]
