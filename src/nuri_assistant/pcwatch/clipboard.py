from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from ..schedule.timeparse import WhenError, parse_when


SHOP_HOSTS = (
    "coupang.com", "11st.co.kr", "gmarket.co.kr", "auction.co.kr", "smartstore.naver.com",
    "shopping.naver.com", "brand.naver.com", "ssg.com", "lotteon.com", "musinsa.com",
    "ohou.se", "kurly.com", "danawa.com",
)
MAX_LENGTH = 200
MAX_LINES = 3
TITLE_LENGTH = 30


@dataclass(frozen=True)
class ClipSuggestion:
    kind: str  # "event" or "price"
    title: str
    when_text: str = ""
    url: str = ""


_DATE = (
    r"(?:\d{4}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}"
    r"|\d{1,2}\s*월\s*\d{1,2}\s*일"
    r"|(?<![\d:/])\d{1,2}\s*/\s*\d{1,2}(?![\d:/])"
    r"|(?:(?:다다음|다음|이번)\s*주\s*)?[월화수목금토일]\s*요일"
    r"|내일\s*모레|오늘|내일|모레|글피"
    r"|(?<![\d월/])\d{1,2}\s*일(?!\s*(?:뒤|후|간|동안)))"
)
_TIME = (
    r"(?:(?:오전|오후|저녁|아침|밤|새벽)\s*)?"
    r"(?:\d{1,2}\s*:\s*\d{2}|\d{1,2}\s*시(?!간)(?:\s*\d{1,2}\s*분|\s*반)?)"
)
_WHEN = re.compile(rf"(?:{_DATE})?(?:\s*{_TIME})?")
_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_LEADING_PARTICLE = re.compile(r"^\s*(?:에는|에서|에|까지|부터)(?![가-힣])")
_EDGE = " \t\r\n.,;:!?-–—~·|/\\()[]{}<>\"'`「」『』【】《》“”‘’"


def find_when(text: str, now: datetime) -> tuple[str, int, int] | None:
    """Find the longest date/time expression in text that parse_when accepts."""

    best: tuple[str, int, int] | None = None
    for m in _WHEN.finditer(text):
        expr = m.group(0)
        stripped = expr.strip()
        if not stripped:
            continue
        start = m.start() + (len(expr) - len(expr.lstrip()))
        end = start + len(stripped)
        try:
            parse_when(stripped, now)
        except (WhenError, ValueError):
            continue
        if best is None or end - start > best[2] - best[1]:
            best = (stripped, start, end)
    return best


def _looks_secret(text: str) -> bool:
    lowered = text.lower()
    if "password" in lowered or "비밀번호" in text or "pw:" in lowered:
        return True
    stripped = text.strip()
    return (
        " " not in stripped
        and len(stripped) >= 16
        and any(c.isalpha() for c in stripped)
        and any(c.isdigit() for c in stripped)
    )


def _shop_url(text: str) -> str | None:
    for m in _URL.finditer(text):
        url = m.group(0)
        host = (urlparse(url).hostname or "").lower()
        if any(host == h or host.endswith("." + h) for h in SHOP_HOSTS):
            return url
    return None


def suggest(text: str, now: datetime) -> ClipSuggestion | None:
    """Suggest an action for copied text. Decided by code; the text is never stored."""

    if not text or not text.strip():
        return None
    text = text.strip()
    if len(text) > MAX_LENGTH or len(text.splitlines()) > MAX_LINES:
        return None
    lowered = text.lower()
    if "password" in lowered or "비밀번호" in text or "pw:" in lowered:
        return None
    if _URL.search(text):
        url = _shop_url(text)
        return ClipSuggestion("price", "", url=url) if url else None
    if _looks_secret(text):
        return None
    found = find_when(text, now)
    if found is None:
        return None
    expr, start, end = found
    after = _LEADING_PARTICLE.sub("", text[end:])
    title = re.sub(r"\s+", " ", f"{text[:start]} {after}").strip(_EDGE)
    title = re.sub(r"\s+", " ", title).strip(_EDGE)[:TITLE_LENGTH].strip()
    if not title:
        return None
    return ClipSuggestion("event", title, when_text=expr)
