from __future__ import annotations

import re
from datetime import datetime

from .models import RenameError, RenameInput


def normalize_date(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) != 8:
        raise RenameError("날짜는 YYYYMMDD 형식이어야 합니다.")
    datetime.strptime(digits, "%Y%m%d")
    return digits


def normalize_media(value: str) -> str:
    media = value.strip().lower()
    if not re.fullmatch(r"[a-z]{2}\d{2}", media):
        raise RenameError("매체코드는 ja00 같은 영문 2자 + 숫자 2자 형식이어야 합니다.")
    return media


def normalize_page(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if not digits:
        raise RenameError("페이지 번호를 입력해야 합니다.")
    return digits.zfill(3)


def safe_name(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")


# Rule placeholders and the Korean names the settings window shows for them.
RULE_TOKENS = {"DATE": "날짜", "YEAR": "연도", "MONTH": "월", "DAY": "일", "MEDIA": "매체", "PAGE": "페이지"}
_TOKEN = re.compile(r"\{([^{}]*)\}")
_TOKEN_PATTERNS = {"DATE": r"\d{8}", "YEAR": r"\d{4}", "MONTH": r"\d{2}", "DAY": r"\d{2}",
                   "MEDIA": r"[a-z]{2}\d{2}", "PAGE": r"\d{3,}"}


def rule_from_korean(text: str) -> str:
    """'{날짜}_{매체}_{페이지}' -> '{DATE}_{MEDIA}_{PAGE}'; English placeholders pass through."""

    names = {korean: key for key, korean in RULE_TOKENS.items()}
    return _TOKEN.sub(lambda m: "{" + names.get(m.group(1).strip(), m.group(1).strip()) + "}", text.strip())


def rule_to_korean(rule: str) -> str:
    return _TOKEN.sub(lambda m: "{" + RULE_TOKENS.get(m.group(1), m.group(1)) + "}", rule)


def validate_rule(rule: str) -> None:
    """A usable rule names only known placeholders and has a page, so every file gets its own name."""

    unknown = [name for name in _TOKEN.findall(rule) if name not in RULE_TOKENS]
    if unknown:
        raise RenameError(f"모르는 칸이 있어요: {{{unknown[0]}}}")
    if "{PAGE}" not in rule:
        raise RenameError("파일마다 이름이 달라지도록 {페이지}가 꼭 들어가야 해요.")
    if not safe_name(_TOKEN.sub("x", rule)):
        raise RenameError("이름 형식이 비어 있어요.")


def rule_uses_media(rule: str) -> bool:
    return "{MEDIA}" in rule


def rule_pattern(rule: str) -> re.Pattern[str]:
    """Matches a file stem that already follows the rule (used to skip files that are done)."""

    parts, last = [], 0
    for match in _TOKEN.finditer(rule):
        parts.append(re.escape(rule[last:match.start()]))
        parts.append(_TOKEN_PATTERNS.get(match.group(1), ".+"))
        last = match.end()
    parts.append(re.escape(rule[last:]))
    return re.compile("".join(parts), re.IGNORECASE)


def build_file_name(item: RenameInput) -> str:
    date = normalize_date(item.date)
    media = normalize_media(item.media) if rule_uses_media(item.rule) else item.media.strip().lower()
    page = normalize_page(item.page)
    stem = item.rule.format(DATE=date, YEAR=date[:4], MONTH=date[4:6], DAY=date[6:], MEDIA=media, PAGE=page)
    stem = safe_name(stem)
    if not stem:
        raise RenameError("파일명 규칙 결과가 비어 있습니다.")
    return f"{stem}{item.path.suffix.lower()}"
