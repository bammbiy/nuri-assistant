from __future__ import annotations

import errno
import os
from datetime import datetime
from pathlib import Path

from ..storage.history import HistoryStore
from .models import RenameError, RenamePreview


def move_no_clobber(source: Path, target: Path) -> None:
    """Move a file without ever replacing an existing target.

    Path.rename silently overwrites on macOS/Linux, and the target can appear
    between preview and execution, so the check has to happen at move time.
    """

    if not source.exists():
        raise RenameError(f"원본 파일을 찾을 수 없습니다: {source.name}")
    if target.exists():
        raise RenameError(f"대상 파일명이 이미 존재합니다: {target.name}")
    if os.name == "nt":
        # Windows rename already refuses to replace an existing file.
        os.rename(source, target)
        return
    try:
        # link() fails atomically when the target exists, closing the race window.
        os.link(source, target)
    except FileExistsError as exc:
        raise RenameError(f"대상 파일명이 이미 존재합니다: {target.name}") from exc
    except OSError as exc:
        if exc.errno not in {errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EXDEV, errno.EMLINK}:
            raise
        # Filesystems without hard links: fall back to the checked rename above.
        os.rename(source, target)
        return
    os.unlink(source)


def apply_batch_rename(previews: list[RenamePreview], history: HistoryStore) -> list[Path]:
    ready = [preview for preview in previews if preview.status == "ready"]
    if not ready:
        raise RenameError("변경 가능한 파일이 없습니다.")

    batch_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    changed: list[RenamePreview] = []
    try:
        for preview in ready:
            move_no_clobber(preview.source, preview.target)
            history.record(preview.source, preview.target, batch_id=batch_id)
            changed.append(preview)
    except Exception as exc:
        for preview in reversed(changed):
            if preview.target.exists() and not preview.source.exists():
                move_no_clobber(preview.target, preview.source)
        raise RenameError(f"배치 변경 중 오류가 발생해 이전 변경을 되돌렸습니다: {exc}") from exc

    return [preview.target for preview in ready]


def undo_last_batch(history: HistoryStore) -> list[Path]:
    rows = history.latest_active_batch()
    if not rows:
        raise RenameError("되돌릴 배치 이력이 없습니다.")

    batch_id = rows[0].batch_id
    for row in rows:
        source = Path(row.source_path)
        target = Path(row.target_path)
        if not target.exists():
            raise RenameError(f"되돌릴 대상 파일을 찾을 수 없습니다: {target.name}")
        if source.exists():
            raise RenameError(f"원래 파일명이 이미 존재해서 되돌릴 수 없습니다: {source.name}")

    restored: list[Path] = []
    for row in rows:
        source = Path(row.source_path)
        target = Path(row.target_path)
        move_no_clobber(target, source)
        restored.append(source)

    history.mark_batch_undone(batch_id)
    return restored
