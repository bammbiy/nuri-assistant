from __future__ import annotations

import random


CHOICES = ("가위", "바위", "보")

_ALIASES = {
    "가위": "가위", "찌": "가위", "scissors": "가위", "scissor": "가위",
    "바위": "바위", "주먹": "바위", "rock": "바위",
    "보": "보", "빠": "보", "paper": "보",
}
_BEATS = {"가위": "보", "바위": "가위", "보": "바위"}


def normalize(text: object) -> str | None:
    return _ALIASES.get(str(text or "").strip().lower())


def play(user: str, rng: random.Random) -> tuple[str, str]:
    computer = rng.choice(CHOICES)
    if user == computer:
        return computer, "draw"
    return computer, "win" if _BEATS[user] == computer else "lose"
