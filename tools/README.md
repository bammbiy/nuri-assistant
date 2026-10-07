# tools

앱 실행에는 필요 없는 개발용 스크립트입니다.

## build_frames.py

AI로 만든 원본 시트 2장(`reference_sheet`, `reference_expressions`)에서 캐릭터 프레임(상반신 405×344, 전신 405×480)을 만듭니다.

```bash
pip install -r tools/requirements-frames.txt
python tools/build_frames.py nuri|sera|yuki|akane [출력폴더]   # 출력폴더를 생략하면 assets/characters/<id>/
```

- 캐릭터별 좌표는 스크립트 안의 `CHARACTERS` 설정에 있습니다.
- 만든 뒤에는 프레임을 꼭 눈으로 검수합니다(표정끼리 머리 크기·위치, 전신 얼굴). 절차는 `CLAUDE.md`의 "캐릭터"와 `assets/characters/README.md`에 있습니다.
- 배경 제거(rembg)는 실행마다 결과가 아주 약간 다를 수 있으니, 고친 캐릭터의 프레임만 교체합니다.
