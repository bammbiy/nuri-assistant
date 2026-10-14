"""자리 비움·연속 사용 감지 (입력 시각만 읽음)."""

from .chatter import CHATTER_MINUTES, IdleChatter
from .fullscreen import covers, foreground_fullscreen, looks_fullscreen
from .idle import idle_seconds
from .touch import ClickCombo, PatDetector
from .tracker import PresenceTracker

__all__ = ["CHATTER_MINUTES", "ClickCombo", "IdleChatter", "PatDetector", "PresenceTracker",
           "covers", "foreground_fullscreen", "looks_fullscreen", "idle_seconds"]
