from __future__ import annotations

import re

from .personas import EXPRESSIONS


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
_JA_BLOCK = re.compile(r"<ja>(.*?)</ja>", re.DOTALL)
# Markup that may arrive split across chunks; a trailing prefix of these is held back.
_PARTIAL_MARKUP = ("<think>", "<ja>", "</ja>")
_SENTENCE_END = "。！？!?♪"  # not "…": "えっと…それは" stays one line
_CLOSERS = "」』）)\"'”’"
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
        self._voice_taken = 0

    def take_voice(self, final: bool = False) -> list[str]:
        """New complete Japanese sentences from the <ja> text seen so far (each returned once)."""

        text = _THINK_BLOCK.sub("", self.raw)
        unfinished_think = text.find("<think>")
        if unfinished_think != -1:
            text = text[:unfinished_think]
        parts: list[str] = []
        pos = 0
        while True:
            start = text.find("<ja>", pos)
            if start == -1:
                break
            start += len("<ja>")
            end = text.find("</ja>", start)
            if end == -1:
                content = text[start:]
                angle = content.rfind("<")
                if angle != -1 and "</ja>".startswith(content[angle:]):
                    content = content[:angle]
                parts.append(content)
                break
            parts.append(text[start:end])
            pos = end + len("</ja>")
        joined = "\n".join(parts)
        pending = joined[self._voice_taken:]
        sentences: list[str] = []
        begin = 0
        i = 0
        while i < len(pending):
            ch = pending[i]
            if ch == "\n":
                i += 1
            elif ch in _SENTENCE_END:
                i += 1
                while i < len(pending) and (pending[i] in _SENTENCE_END or pending[i] in _CLOSERS):
                    i += 1
                if i >= len(pending) and not final:
                    break  # closing marks may still be on the way
            else:
                i += 1
                continue
            sentence = pending[begin:i].strip()
            if sentence:
                sentences.append(sentence)
            begin = i
        if final:
            rest = pending[begin:].strip()
            if rest:
                sentences.append(rest)
            begin = len(pending)
        self._voice_taken += begin
        return sentences

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
