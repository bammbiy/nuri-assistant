# CLAUDE.md

이 저장소에서 작업하는 사람과 AI 에이전트를 위한 안내서입니다. 지금까지 무엇을 왜 했는지는 [HISTORY.md](HISTORY.md)에 있습니다. 새 작업을 시작하기 전에 두 문서를 먼저 읽으세요.

## 프로젝트 요약

바탕화면에 애니메이션풍 캐릭터 비서를 항상 띄워 두고, 내 PC의 로컬 AI(Ollama)와 한국어로 대화하는 Windows용 Tkinter 앱입니다. 캐릭터가 일정·할 일·집중 타이머·최저가 알림을 관리하고, 일본어 애니 보이스(VOICEVOX)로 말할 수 있습니다. 원래는 문서 파일 이름 일괄 정리 도구였고, 그 기능도 메뉴와 `--classic` 실행으로 남아 있습니다.

- 사용자: 한국어 사용자, PC는 RTX 3060 Ti(8GB VRAM) + RAM 32GB, Windows
- UI 문구와 캐릭터 대사는 모두 한국어, 음성만 일본어
- 개발 브랜치: `claude/pensive-archimedes-kwhp16` (원격에 푸시, PR은 요청이 있을 때만)

## 실행과 테스트

```bash
python src/run_nuri.py            # 캐릭터 비서 (비서 선택 화면부터). Windows는 start_nuri.bat 더블클릭
python src/run_nuri.py --classic  # 파일 정리 도구만
python -m unittest discover -s tests                         # 저장소 루트에서 (테스트는 src.nuri_assistant 로 import)
python -W error::ResourceWarning -m unittest discover -s tests   # SQLite 연결 누수까지 잡기 (현재 78개 통과)
python -m pyflakes src tests tools
python tools/build_frames.py nuri|sera|yuki|akane [출력폴더]              # 캐릭터 프레임 재생성 (pillow numpy scipy rembg onnxruntime 필요)
```

- Python 3.11 이상. 앱 실행에 외부 패키지는 필요 없습니다. Pillow는 선택(있으면 썸네일 축소가 부드러움).
- 외부 프로그램: Ollama(기본 모델 `qwen3:8b`, 도구 호출 지원 필요), VOICEVOX(음성, 선택).
- 단위 테스트는 tkinter 없이 돌아갑니다. `ui/`는 단위 테스트에서 import하지 않습니다.
- UI 확인 방법(클라우드 컨테이너): tkinter가 있는 `python3.12`로 `xvfb-run -a -s "-screen 0 1280x1000x24" python3.12 스크립트.py`를 실행하고, `import -window root -crop WxH+X+Y`로 캡처합니다. 가짜 Ollama·네이버·VOICEVOX 서버는 `http.server`로 만들어 `ollama_url`, `NaverShopping.URL`, `voice_url`을 그쪽으로 돌립니다. `MascotApp(app_dir)`에 임시 폴더를 넘기면 사용자 데이터를 건드리지 않습니다.
- 컨테이너에서 확인할 수 없는 것: Windows 투명 배경(`-transparentcolor`), 맑은 고딕, 테두리 없는 창의 포커스, 고배율(125%/150%) 화면, 실제 Ollama·VOICEVOX·네이버 API. 이것들은 아직 실사용 확인 전입니다.

## 구조

```text
src/nuri_assistant/
├── companion/   personas(캐릭터 8명: 성격·말투·대사 틀·기본 목소리), llm(Ollama 스트리밍+도구 호출),
│                brain(모델→도구→모델 루프 최대 4회, 대화 기억, 일본어 번역), reply(표정 태그·<think>·<ja> 처리),
│                memory(캐릭터별 대화), settings(companion.json), toolbox(도구 묶음 라우팅)
├── schedule/    timeparse(한국어 날짜 해석), store, tools(add/list/cancel_event)
├── todo/        store(마감·잔소리 시점), tools(add/list/complete/delete_todo)
├── focus/       timer(집중·휴식 단계), tools(start/stop/status) — 확인 카드 없이 바로 실행
├── pricewatch/  sources(네이버 쇼핑 검색 API, 상품 페이지 JSON-LD/메타), store, checker(알림 규칙), tools
├── voice/       voicevox(VOICEVOX 호환 HTTP), speaker(번역→합성→재생 스레드, 최신 대사 우선), player
├── core/ metadata/ storage/ assistant/ shopping/   기존 파일 이름 정리 도구와 구매 비서
└── ui/          mascot(캐릭터 창, 앱의 중심), chatbox, confirm_card, picker(비서 선택), placeholder(그림 없는 캐릭터),
                 schedule_window, todo_window, price_window, price_settings, voice_settings, theme(색·공용 위젯),
                 desktop(파일 정리 도구), assistant(옛 파일/구매 비서 창)
assets/characters/<id>/        상반신 프레임 405×344 + 원본 시트 2장 (reference_sheet, reference_expressions)
assets/characters/<id>/full/   전신 프레임 405×480
tools/build_frames.py          원본 시트 → 정렬된 프레임 (캐릭터별 좌표는 CHARACTERS 설정)
```

사용자 데이터(`~/.nuri-assistant/`): `companion.json`(설정·네이버 API 키, 못 읽으면 `.bak`로 보존), `error.log`(예외 기록), `companion.sqlite3`(대화·일정·할 일·가격 감시), `history.sqlite3`(파일 이름 변경 이력), `characters/<id>/`(개인 캐릭터 이미지, 저장소보다 우선).

## 설계 원칙 (꼭 지킬 것)

1. **AI는 직접 바꾸지 않는다.** 일정·할 일·가격 알림의 추가·완료·삭제는 도구가 대기 액션만 만들고, 사용자가 확인 카드(버튼 또는 "응"/"아니")로 승인해야 반영됩니다. 예외는 집중 타이머(영구 변경이 없음). 파일 이름 변경은 미리보기 → 확인 → 실행 → 되돌리기 흐름을 유지합니다.
2. **날짜 계산은 코드가 한다.** 모델은 사용자 표현("다음 주 화요일 3시", "금요일까지")을 그대로 넘기고 `schedule/timeparse.py`가 해석합니다. 새 표현은 여기에 추가하고 `tests/test_schedule.py`에 사례를 넣습니다.
3. **가격은 지어내지 않고, 무료 출처만 쓴다.** 누구나 무료로 키를 받는 네이버 쇼핑 검색 API, 또는 상품 페이지의 구조화 데이터만 씁니다. 심사가 필요한 API(쿠팡 파트너스)는 넣지 않고, 자동 조회를 막는 사이트(쿠팡 웹)는 우회해서 긁지 않습니다.
4. **로컬 우선.** 대화와 번역은 로컬 Ollama, 음성은 로컬 VOICEVOX. API 키는 로컬 설정 파일에만 저장합니다.
5. **시간이 중요한 알림은 AI를 거치지 않는다.** 일정 알림, 할 일 잔소리, 타이머, 아침 브리핑, 가격 알림은 페르소나의 대사 틀(`reminder`, `todo_nag`, `focus_done`, `break_done`, `all_done`, `briefing`, `price_alert`)로 앱이 바로 말합니다. 음성용 일본어 번역만 로컬 AI를 거치고, 실패해도 말풍선은 나옵니다.
6. **도구를 못 쓰는 모델도 동작해야 한다.** `OllamaToolsUnsupported`가 나면 그 세션은 도구 없이 대화만 합니다.
7. **캐릭터는 오리지널만.** 기존 작품 캐릭터나 실존 작가 그림체를 따라 하지 않습니다. 노출이 있는 이미지는 저장소가 아니라 `~/.nuri-assistant/characters/`에 둡니다.

## 코드 관례

- SQLite는 매 호출마다 연결을 열고 반드시 닫습니다(`_connect()` 컨텍스트 매니저). 안 닫으면 Windows에서 파일이 잠깁니다.
- 파일 이동은 `core.operations.move_no_clobber`만 씁니다. `Path.rename`은 macOS/Linux에서 기존 파일을 덮어씁니다.
- 새 도구 묶음은 `specs`, `execute`, `take_pending`, `owns`, `confirm`을 갖춘 클래스로 만들어 `MascotApp`의 `ToolBox([...])`에 넣고, 페르소나 시스템 프롬프트(`personas.py`의 `abilities`)에 쓰임새를 한 줄 추가합니다. 확인 카드는 액션의 `kind`(add/done/cancel/delete), `heading`, `when`, `title`만 읽습니다.
- 테스트용 가짜 클라이언트의 `chat_stream`은 `(model, messages, options=None, tools=None)`을 받아야 합니다.
- 오류가 나도 창은 보여야 합니다. 시작 실패는 `run_nuri.py`가 `crashlog`로 `error.log`에 남기고 안내창을 띄웁니다. Tk 콜백 예외는 `MascotApp.report_callback_exception`이 기록하고, 숨겨진 창(비서 선택 중)이면 다시 보이게 합니다. `after()`로 반복하는 루프는 본문을 별도 함수로 빼고 `finally`에서 다시 예약합니다(예외 한 번에 루프가 멈추면 앱이 굳은 것처럼 보임).
- 텍스트 파일은 항상 `encoding=`을 지정합니다(한국어 Windows 기본은 cp949). 사용자가 메모장으로 고칠 수 있는 파일은 `utf-8-sig`와 cp949도 읽습니다.
- 백그라운드 작업(모델 호출, 가격 조회, 음성 합성)은 스레드에서 돌리고 결과는 `MascotApp.events` 큐로 넘깁니다. 스레드에서 Tk 위젯을 직접 만지지 않습니다.
- 말풍선과 음성을 함께 낼 때는 `MascotApp.talk()`, 말풍선만이면 `say()`. 오류·안내 문구는 읽지 않습니다.
- 모델 답변의 일본어 음성 대사는 `<ja>…</ja>`로 받고 `ReplyParser.voice`에 담깁니다(말풍선과 대화 기억에는 남기지 않음).
- 설정 항목을 추가할 때는 `CompanionSettings`에 기본값과 함께 넣습니다. 알 수 없는 키는 로드 시 무시되므로 옛 설정 파일도 열립니다.

## UI 관례

- 색과 공용 위젯은 `ui/theme.py` (파스텔 라일락: 배경 `#f6f2fb`, 강조 `#a68ae0`, 글자 `#2f2640`, 오늘/달성 `#3fae94`, 위험 `#e06c8a`). 새 창은 기본 ttk 표 대신 이 톤의 캔버스 카드로 만듭니다(일정·할 일·최저가 창 참고). 삭제는 두 번 눌러야 되게 합니다.
- 캐릭터 창 캔버스 겹침 순서: 캐릭터 → 타이머 배지(`timer`) → 말풍선(`bubble`) → 확인 카드(`confirm`) → 채팅창(`chat`). 캐릭터를 다시 그린 뒤 이 순서로 `tag_raise`합니다.
- 채팅창은 캐릭터에 마우스를 올렸을 때만 보이고, 마우스만으로는 입력 포커스를 가져오지 않습니다.
- 프레임은 1:1로 보여 줍니다(상반신 405×344, 전신 405×480, 창 폭 `WIDTH = 415`). 실행 중 리샘플링은 화질을 떨어뜨리니 크기를 바꾸려면 `tools/build_frames.py`의 `W, H`/`FULL_W, FULL_H`와 `WIDTH`를 같이 바꿉니다.
- 전신 모드(`display_mode = "full"`)는 캔버스가 `FULL_EXTRA`(150px) 커지고 창이 위로 늘어납니다. 레이아웃 좌표는 `self.char_bottom`, `self.extra`를 씁니다. 전신 그림이 없는 캐릭터는 상반신으로 나옵니다.
- Windows 투명 키 색 `#010203`은 캐릭터 창 배경 외에는 쓰지 않습니다.

## 캐릭터

| id | 이름 | 컨셉 | 부르는 말 | 그림 | 기본 목소리(VOICEVOX id) |
|---|---|---|---|---|---|
| nuri | 누리 | 다정한 후배 비서 (기본) | 선배 | 상반신+전신 | 春日部つむぎ (8) |
| sera | 세라 | 어른스러운 누나 비서 | 동생 | 상반신+전신 | 九州そら セクシー (17) |
| yuki | 유키 | 나긋나긋한 힐링계 | 자기 | 상반신+전신 | WhiteCUL ノーマル (23) |
| akane | 아카네 | 츤데레 | 너 | 상반신+전신 | 四国めたん ツンツン (6) |
| shizuku | 시즈쿠 | 쿠데레 | 너 | 도형 임시 | 冥鳴ひまり (14) |
| hinata | 히나타 | 활발한 소꿉친구 | 너 | 도형 임시 | 雨晴はう (10) |
| sakura | 사쿠라 | 상냥한 메이드 | 주인님 | 도형 임시 | 九州そら あまあま (15) |
| reika | 레이카 | 오죠사마 | 당신 | 도형 임시 | 四国めたん ノーマル (2) |

목소리 id는 VOICEVOX 기본값 기준이며 실제 설치본에서 확인 전입니다.

캐릭터 추가 절차:
1. `companion/personas.py`의 `PERSONAS`에 `Persona` 추가 (대사 틀, `voice_id`, 임시 그림 색 포함).
2. 그림: 기본 시트(왼쪽 전신·오른쪽 큰 상반신)와 3×2 표정 시트를 `assets/characters/<id>/`에 두고, `tools/build_frames.py`의 `CHARACTERS`에 좌표를 적습니다. 좌표는 원본을 확대한 좌표 격자 이미지를 보고 손으로 잽니다(눈 사이 중점·거리, 입 중심, 눈 상자, 전신 머리끝·발끝). 업스케일한 시트는 배치가 같으면 기존 좌표에 배율만 곱하면 됩니다. 자세한 규격과 생성 프롬프트는 `assets/characters/README.md`.
3. 프레임 결과를 꼭 검수합니다. 문제는 설정으로 고치고, 손으로 이미지를 고치지 않습니다.
   - **표정끼리 머리 크기·위치:** 눈 사이 거리만으로 맞추면 표정 시트 칸마다 얼굴 크기가 달라 표정을 바꿀 때 머리가 커졌다 작아집니다. 기본 표정의 머리 윤곽을 다른 표정 위에 겹쳐 그려 보고(어니언 스킨), 머리카락 윤곽과 얼굴 피부 영역이 가장 잘 겹치는 배율·이동을 찾아 `expressions["adjust"]`에 (배율, dx, dy)로 넣습니다. 보정 후 표정별 머리 폭 차이는 ±2% 안이어야 합니다.
   - **전신 얼굴:** 전신 `mid`/`dist`는 눈동자 중심을 10배 확대해서 재고, 코·입·턱이 상반신과 같은 배율(눈 사이 거리의 배수)인지 확인합니다. 어긋나면 눈·입만 맞아 보이고 얼굴이 이상해집니다. 붙이는 범위는 `full["face"]`(타원 + 표정별 아래 한계)이고, 그 안에서도 얼굴 피부와 앞머리·눈 띠만 가져옵니다(머리카락·헤드셋 줄·손·소매는 전신 그림 것).
   - 그 밖에: 이름표 글자는 `rows`로 끊기, 배경 번짐은 `alpha`, 전신 주변 잔상은 `full["erase"]`, 홍조 있는 얼굴의 눈 감기는 `skin="lerp"`.
4. 배경 제거(rembg)는 실행마다 아주 약간 결과가 달라질 수 있으니, 고친 캐릭터의 프레임만 교체합니다.

## 남은 일

- 실제 PC(Windows)에서 종합 확인: Ollama 도구 호출, VOICEVOX 음성과 기본 목소리 id, 네이버 API(쿠팡 상품 포함 여부), 투명 배경, 고배율 화면
- 파일 정리 기능을 대화 도구로 연결 (미리보기·확인 카드 재사용)
- 대화 기록 창을 파스텔 디자인으로 교체
- 나머지 4명 캐릭터 그림 (시즈쿠·히나타·사쿠라·레이카). 시트 생성 프롬프트는 기존 시트를 첨부하고 그림체를 문장으로 고정해야 함(제미나이가 그림체를 잘 못 맞춤, `assets/characters/README.md`)
