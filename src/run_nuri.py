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
    from nuri_assistant.crashlog import log_exception, show_error

    try:
        if args.classic:
            from nuri_assistant.ui.desktop import run

            run()
        else:
            from nuri_assistant.ui.mascot import run_mascot

            run_mascot()
    except Exception:
        path = log_exception(*sys.exc_info())
        where = f"\n\n자세한 내용: {path}" if path else ""
        show_error("Nuri Assistant 실행 오류", f"앱을 시작하지 못했습니다.\n{sys.exc_info()[1]!r}{where}")
        sys.exit(1)


if __name__ == "__main__":
    main()
