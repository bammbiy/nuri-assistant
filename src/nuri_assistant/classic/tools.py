"""Chat tools for the classic file renamer: the model proposes, the confirm card applies.

The model passes the folder and the user's request as said; interpret_file_command reads the
date, media code, first page and rule from it, and the batch is previewed here. Nothing is
renamed until the user approves the card, and the last batch can be undone the same way.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..companion.toolbox import ConfirmingTools, clean_args, unknown_tool
from .commands import interpret_file_command
from .core import (
    DEFAULT_EXTENSIONS, DEFAULT_RULE, RenameError, RenameInput, RenamePreview, apply_batch_rename, build_file_name,
    preview_batch, rule_pattern, rule_uses_media, scan_files, undo_last_batch, validate_rule,
)
from .storage import HistoryStore

MAX_FILES = 300  # more than this in one folder is likely the wrong folder; ask for a narrower one
EXAMPLES = 5

# Spoken folder names -> folders under the home directory (Windows may redirect them to OneDrive).
KNOWN_FOLDERS = {
    "다운로드": "Downloads", "downloads": "Downloads",
    "바탕화면": "Desktop", "바탕 화면": "Desktop", "desktop": "Desktop",
    "문서": "Documents", "내 문서": "Documents", "documents": "Documents",
    "사진": "Pictures", "pictures": "Pictures",
}
KOREAN_NAMES = {"Downloads": "다운로드", "Desktop": "바탕화면", "Documents": "문서", "Pictures": "사진"}
ONEDRIVE_NAMES = {"Desktop": ("Desktop", "바탕 화면"), "Documents": ("Documents", "문서"), "Pictures": ("Pictures", "사진")}

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "rename_files",
            "description": (
                "폴더 안 문서·이미지 파일 이름을 '날짜_매체코드_페이지'(예: 20260715_ja00_001.pdf) 규칙으로 정리할 때 호출한다. "
                "날짜·매체코드·시작 페이지는 해석하지 말고 사용자가 말한 요청 문장을 그대로 request에 넣는다. "
                "미리보기만 만들고, 실제 변경은 사용자가 확인 버튼을 눌러야 끝난다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "폴더. '다운로드', '바탕화면', '문서' 또는 전체 경로(C:\\Users\\...)"},
                    "request": {"type": "string", "description": "사용자가 말한 정리 요청 그대로. 예: 20260715 ja00 1페이지부터 정리해줘"},
                },
                "required": ["folder", "request"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "undo_rename",
            "description": "마지막으로 정리한 파일 이름을 원래대로 되돌릴 때 호출한다. 사용자가 확인 버튼을 눌러야 되돌려진다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


@dataclass(frozen=True)
class RenameOptions:
    """The user's choices from the "파일 정리 설정" window (CompanionSettings.rename_*)."""

    rule: str = DEFAULT_RULE
    media: str = ""  # used when the request names no media code
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS
    skip_named: bool = True  # leave files already named by the rule and number after them


@dataclass(frozen=True)
class RenameAction:
    kind: str  # "rename" | "undo"
    folder: str
    previews: tuple[RenamePreview, ...] = ()
    count: int = 0

    @property
    def heading(self) -> str:
        return "파일 이름 정리" if self.kind == "rename" else "파일 이름 되돌리기"

    @property
    def when(self) -> str:
        return f"{self.folder} {self.count}개"

    @property
    def title(self) -> str:
        if self.kind == "undo":
            return "마지막 정리 전 이름으로"
        first = next(p for p in self.previews if p.status == "ready")
        more = f" 외 {self.count - 1}개" if self.count > 1 else ""
        return f"{short(first.source.name)} → {first.target.name}{more}"


def short(name: str, limit: int = 18) -> str:
    return name if len(name) <= limit else name[: limit - 1] + "…"


def folder_label(path: Path) -> str:
    """How the character names a folder: '다운로드' rather than 'Downloads'."""

    return KOREAN_NAMES.get(path.name, path.name)


def resolve_folder(text: str, home: Path | None = None) -> Path | None:
    """A spoken folder name or a path -> an existing folder, or None."""

    home = home or Path.home()
    key = text.strip().strip("'\"").removesuffix(" 폴더").removesuffix("폴더").strip()
    if key.lower() in KNOWN_FOLDERS:
        name = KNOWN_FOLDERS[key.lower()]
        candidates = [home / name] + [home / "OneDrive" / alias for alias in ONEDRIVE_NAMES.get(name, ())]
    else:
        candidates = [Path(key).expanduser()]
    return next((path for path in candidates if path.is_absolute() and path.is_dir()), None)


class FileTools(ConfirmingTools[RenameAction]):
    specs = TOOL_SPECS
    action_type = RenameAction

    def __init__(self, history: HistoryStore, options: Callable[[], RenameOptions] = RenameOptions,
                 home: Callable[[], Path] = Path.home) -> None:
        super().__init__()
        self.history = history
        self.options = options
        self.home = home

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        args = clean_args(arguments)
        if name == "rename_files":
            return self._rename(str(args.get("folder", "")), str(args.get("request", "")))
        if name == "undo_rename":
            rows = self.history.latest_active_batch()
            if not rows:
                return {"ok": False, "error": "되돌릴 정리 기록이 없어요."}
            folder = folder_label(Path(rows[0].target_path).parent)
            self.pending.append(RenameAction("undo", folder, count=len(rows)))
            return {"ok": True, "status": "사용자 확인 대기 중 (아직 되돌리지 않음)", "count": len(rows), "folder": folder}
        return unknown_tool(name)

    def _rename(self, folder_text: str, request: str) -> dict[str, Any]:
        folder = resolve_folder(folder_text, self.home())
        if folder is None:
            return {"ok": False, "error": f"'{folder_text}' 폴더를 찾지 못했어요.", "hint": "폴더 전체 경로를 물어본다."}
        options = self.options()
        plan = interpret_file_command(request)
        # A rule said in the request ("매체-날짜 순으로") wins over the one saved in settings.
        rule = plan.rule if plan.rule != DEFAULT_RULE else options.rule
        try:
            validate_rule(rule)
        except RenameError as exc:
            return {"ok": False, "error": f"파일 정리 설정의 이름 형식이 잘못됐어요. {exc}"}
        media = plan.media or options.media
        if rule_uses_media(rule) and not media:
            return {"ok": False, "error": "매체코드가 필요해요.", "hint": "ja00처럼 영문 2자+숫자 2자 매체코드를 물어본다."}
        try:
            paths = scan_files(folder, recursive=plan.recursive, extensions=options.extensions)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        named = rule_pattern(rule)
        done = [path for path in paths if options.skip_named and named.fullmatch(path.stem)]
        paths = [path for path in paths if path not in done]
        if not paths:
            reason = f" (이미 정리된 파일 {len(done)}개)" if done else ""
            return {"ok": False, "error": f"'{folder_label(folder)}'에 정리할 파일이 없어요{reason}."}
        if len(paths) > MAX_FILES:
            return {"ok": False, "error": f"파일이 {len(paths)}개나 돼요.", "hint": "더 좁은 폴더를 물어본다."}
        previews = preview_batch(self._numbered(paths, plan.date, media, int(plan.page), rule))
        ready = [p for p in previews if p.status == "ready"]
        problems = [f"{p.source.name}: {p.message}" for p in previews if p.status in ("conflict", "error")]
        if not ready:
            return {"ok": False, "error": "바꿀 수 있는 파일이 없어요.", "problems": problems[:EXAMPLES]}
        self.pending.append(RenameAction("rename", folder_label(folder), tuple(previews), len(ready)))
        return {
            "ok": True,
            "status": "사용자 확인 대기 중 (아직 바꾸지 않음)",
            "folder": str(folder),
            "count": len(ready),
            "examples": [f"{p.source.name} → {p.target.name}" for p in ready[:EXAMPLES]],
            "already_named": len(done),
            "skipped": len(previews) - len(ready),
            "problems": problems[:EXAMPLES],
        }

    @staticmethod
    def _numbered(paths: list[Path], date: str, media: str, start: int, rule: str) -> list[RenameInput]:
        """Pages count up from start, stepping over names already in the folder (001-005 done -> 006)."""

        items, page = [], start
        for path in paths:
            while True:
                item = RenameInput(path, date, media, str(page).zfill(3), rule)
                page += 1
                try:
                    taken = path.with_name(build_file_name(item)).exists()
                except (RenameError, ValueError):
                    taken = False  # preview_batch reports the error on this file
                if not taken:
                    break
            items.append(item)
        return items

    def confirm(self, action: RenameAction) -> str:
        try:
            if action.kind == "undo":
                restored = undo_last_batch(self.history)
                return f"파일 {len(restored)}개를 원래 이름으로 되돌렸어요."
            changed = apply_batch_rename(list(action.previews), self.history)
        except (RenameError, OSError) as exc:
            return f"파일 이름을 바꾸지 못했어요. {exc}"
        return f"'{action.folder}' 파일 {len(changed)}개 이름을 정리했어요. 되돌리려면 말해 주세요."
