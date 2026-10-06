from __future__ import annotations

import re

from .personas import EXPRESSIONS


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
_JA_BLOCK = re.compile(r"<ja>(.*?)</ja>", re.DOTALL)
# Markup that may arrive split across chunks; a trailing prefix of these is held back.
_PARTIAL_MARKUP = ("<think>", "<ja>", "</ja>")
_TAG = re.compile(r"\[\s*([^\[\]\s]{1,10})\s*\]")
_ALIASES = {
    "기본": "neutral",
    "웃음": "happy",
    "기쁨": "happy",
    "생각": "thinking",
    "놀람": "surprised",
    "슬픔": "sad",
    "화남": "angry",
    "부끄럼": "shy",
    "embarrassed": "shy",
    "smile": "happy",
}


def _expression_for(tag: str) -> str | None:
    key = tag.strip().lower()
    if key in EXPRESSIONS:
        return key
    return _ALIASES.get(key)


class ReplyParser:
    """Turns a streamed model reply into bubble text plus an expression.

    The model is asked to start with a tag such as ``[happy]``. Tags and any
    ``<think>`` reasoning are hidden, and partial tags at the end of the stream
    are held back so they never flash in the bubble.
    """

    def __init__(self, default_expression: str = "neutral") -> None:
        self.raw = ""
        self.expression = default_expression
        # Japanese line for text-to-speech, written by the model inside <ja>...</ja>.
        self.voice = ""

    def feed(self, chunk: str) -> str:
        self.raw += chunk
        return self._visible(final=False)

    def finish(self) -> str:
        return self._visible(final=True)

    def _visible(self, final: bool) -> str:
        text = _THINK_BLOCK.sub("", self.raw)
        unfinished_think = text.find("<think>")
        if unfinished_think != -1:
            text = text[:unfinished_think]
        text = text.replace("</think>", "")
        spoken = _JA_BLOCK.findall(text)
        if spoken:
            self.voice = " ".join(part.strip() for part in spoken if part.strip())
        text = _JA_BLOCK.sub("", text)
        unfinished_ja = text.find("<ja>")
        if unfinished_ja != -1:
            text = text[:unfinished_ja]
        text = text.replace("</ja>", "")

        def replace(match: re.Match[str]) -> str:
            expression = _expression_for(match.group(1))
            if expression is None:
                return match.group(0)
            self.expression = expression
            return ""

        text = _TAG.sub(replace, text)
        if not final:
            bracket = text.rfind("[")
            if bracket != -1 and "]" not in text[bracket:] and len(text) - bracket <= 12:
                text = text[:bracket]
            angle = text.rfind("<")
            if angle != -1 and any(markup.startswith(text[angle:]) for markup in _PARTIAL_MARKUP):
                text = text[:angle]
        return re.sub(r"[ \t]{2,}", " ", text).strip()
