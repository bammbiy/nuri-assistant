from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Nuri Assistant")
    parser.add_argument("--classic", action="store_true", help="캐릭터 없이 파일 정리 도구만 실행합니다.")
    args = parser.parse_args()
    if args.classic:
        from nuri_assistant.ui.desktop import run

        run()
    else:
        from nuri_assistant.ui.mascot import run_mascot

        run_mascot()


if __name__ == "__main__":
    main()
