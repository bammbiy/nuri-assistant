"""Command-line entry point: `python src/run_nuri.py`, `python -m nuri_assistant` and the
`nuri-assistant` launcher all end up in main()."""
from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Nuri Assistant")
    parser.add_argument("--classic", action="store_true", help="캐릭터 없이 파일 정리 도구만 실행합니다.")
    args = parser.parse_args()
    try:
        import tkinter  # checked first: some Python installs ship without it
    except ImportError:
        sys.exit(
            "이 Python에는 tkinter(화면 라이브러리)가 없습니다.\n"
            "python.org에서 Windows용 Python을 받아 설치할 때 'tcl/tk and IDLE'을 체크해 주세요."
        )
    del tkinter
    from .crashlog import log_exception, show_error

    # The UI is imported only here, after the tkinter check, so a broken import still ends up
    # in error.log and an error box instead of a console that closes at once.
    try:
        if args.classic:
            from .ui.classic.desktop import run

            run()
        else:
            from .ui.character.mascot import run_mascot

            run_mascot()
    except Exception:
        path = log_exception(*sys.exc_info())
        where = f"\n\n자세한 내용: {path}" if path else ""
        show_error("Nuri Assistant 실행 오류", f"앱을 시작하지 못했습니다.\n{sys.exc_info()[1]!r}{where}")
        sys.exit(1)
