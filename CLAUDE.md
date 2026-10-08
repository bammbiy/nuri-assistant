# CLAUDE.md

이 저장소에서 작업하는 사람과 AI 에이전트를 위한 안내서입니다. 지금까지 무엇을 왜 했는지는 [HISTORY.md](HISTORY.md)에 있습니다. 새 작업을 시작하기 전에 두 문서를 먼저 읽으세요.

**문서 규칙(사용자 지시):** 작업을 하나 끝낼 때마다 **CLAUDE.md와 HISTORY.md를 항상 함께 갱신**하고 같은 커밋에 넣습니다. CLAUDE.md에는 바뀐 사실(구조·명령·관례·캐릭터 표·남은 일)을, HISTORY.md에는 무엇을 왜 바꿨는지(사용자 요청·원인·결정)를 최신이 위로 오게 적습니다. 문서만 고치는 작업도 예외가 아닙니다.

## 프로젝트 요약

바탕화면에 애니메이션풍 캐릭터 비서를 항상 띄워 두고, 내 PC의 로컬 AI(Ollama)와 한국어로 대화하는 Windows용 Tkinter 앱입니다.

**핵심 콘셉트(처음부터의 기획):** 사용자가 무슨 작업을 하든 캐릭터가 **화면 오른쪽 아래(작업 표시줄 바로 위)에 항상 위로 떠 있고**, 마우스를 올리면 바로 아래에 채팅창이 나타나 메신저처럼 대화합니다. 말풍선으로 먼저 알려 주고(일정·잔소리·가격), 확인 카드로 승인받아 앱 기능을 대신 실행합니다. 이 "항상 떠 있는 채팅 비서" 경험을 깨는 변경은 하지 않습니다. 캐릭터가 일정·할 일·집중 타이머·최저가 알림을 관리하고, 일본어 애니 보이스(VOICEVOX)로 말할 수 있습니다. 원래는 문서 파일 이름 일괄 정리 도구였고, 그 기능도 메뉴와 `--classic` 실행으로 남아 있습니다.

- 사용자: 한국어 사용자, PC는 RTX 3060 Ti(8GB VRAM) + RAM 32GB, Windows
- UI 문구와 캐릭터 대사는 모두 한국어, 음성만 일본어
- 개발 브랜치: `claude/pensive-archimedes-kwhp16` (원격에 푸시, PR은 요청이 있을 때만)

## 실행과 테스트

```bash
python src/run_nuri.py            # 캐릭터 비서 (비서 선택 화면부터). Windows는 start_nuri.bat 더블클릭
python src/run_nuri.py --classic  # 파일 정리 도구만
python -m nuri_assistant [--classic]   # 같은 실행 (src/ 안에서, 또는 pip install -e . 뒤 어디서나. 설치하면 nuri-assistant 명령도 생김)
pip install -e .[dev]             # 선택: 개발용 설치(pyflakes). 그림이 assets/에 있어서 편집 설치(-e)만 지원
python -m unittest discover -s tests                         # 저장소 루트에서 (테스트는 src.nuri_assistant 로 import)
python -W error::ResourceWarning -m unittest discover -s tests   # SQLite 연결 누수까지 잡기 (현재 102개 통과)
python -m pyflakes src tests tools
pip install -r tools/requirements-frames.txt                 # 프레임 생성 도구용 (앱에는 필요 없음)
python tools/build_frames.py nuri|sera|yuki|akane|shizuku|hinata|sakura|reika [출력폴더]   # 캐릭터 프레임 재생성
```

- Python 3.10 이상(3.11 권장). 앱 실행에 외부 패키지는 필요 없습니다. Pillow는 선택(있으면 썸네일 축소가 부드러움).
- 외부 프로그램: Ollama(기본 모델 `qwen3:8b`, 도구 호출 지원 필요), VOICEVOX(음성, 선택).
- 단위 테스트는 tkinter 없이 돌아갑니다. `ui/`는 단위 테스트에서 import하지 않습니다. 그래서 UI 모듈의 import 오류는 테스트로 안 잡히니, UI 파일을 옮기거나 import를 고치면 아래 방법으로 앱을 띄워 메뉴의 창을 모두 열어 봅니다.
- 패키지 정보는 `pyproject.toml`(버전은 `nuri_assistant.__version__`과 같이 올림), 편집기 설정은 `.editorconfig`(`start_nuri.bat`은 일부러 cp949 + CRLF).
- UI 확인 방법(클라우드 컨테이너): tkinter가 있는 `python3.12`로 `xvfb-run -a -s "-screen 0 1280x1000x24" python3.12 스크립트.py`를 실행하고, `import -window root -crop WxH+X+Y`로 캡처합니다. 가짜 Ollama·네이버·VOICEVOX 서버는 `http.server`로 만들어 `ollama_url`, `NaverShopping.URL`, `voice_url`을 그쪽으로 돌립니다. `MascotApp(app_dir)`에 임시 폴더를 넘기면 사용자 데이터를 건드리지 않습니다.
- 컨테이너에서 확인할 수 없는 것: Windows 투명 배경(`-transparentcolor`), Windows에서 번들 글꼴 등록(`AddFontResourceEx`), 테두리 없는 창의 포커스, 고배율(125%/150%) 화면, 실제 Ollama·VOICEVOX·네이버 API. 이것들은 아직 실사용 확인 전입니다.

## 구조

```text
src/run_nuri.py  실행 진입점 (start_nuri.bat이 부름). 내용은 nuri_assistant/app.py의 main()
src/nuri_assistant/
├── app.py       main(): --classic 인자, tkinter 확인, 시작 실패 기록·안내창, UI는 여기서 늦게 import
├── __main__.py  python -m nuri_assistant
├── companion/   personas(캐릭터 8명: 성격·말투·대사 틀·기본 목소리), llm(Ollama 스트리밍+도구 호출),
│                brain(모델→도구→모델 루프 최대 4회, 대화 기억, 일본어 번역), reply(표정 태그·<think>·<ja> 처리),
│                memory(캐릭터별 대화), settings(companion.json),
│                toolbox(도구 묶음 라우팅, ConfirmingTools 기반 클래스, "응"/"아니" 판정 parse_confirmation)
├── schedule/    timeparse(한국어 날짜 해석), store, tools(add/list/cancel_event)
├── todo/        store(마감·잔소리 시점), tools(add/list/complete/delete_todo)
├── focus/       timer(집중·휴식 단계), tools(start/stop/status) — 확인 카드 없이 바로 실행
├── pricewatch/  sources(네이버 쇼핑 검색 API, 상품 페이지 JSON-LD/메타), store, checker(알림 규칙), tools
├── voice/       voicevox(VOICEVOX 호환 HTTP), speaker(번역→합성→재생 스레드, 최신 대사 우선), player
├── classic/     기존 파일 이름 정리 도구와 구매 비서 (--classic, 메뉴 "파일 정리 도구"·"파일/구매 비서")
│                tools(대화 도구 rename_files·undo_rename, 확인 카드로 실행), core(스캔·이름 규칙·미리보기·실행·되돌리기), metadata(파일 이름에서 날짜·매체·면 추정),
│                storage(history.sqlite3 이력, profiles.json 작업 프로필), commands(한국어 요청 → 이름 변경 계획),
│                shopping(구매 체크리스트 점수, 선택 기능인 OpenAI 조사)
├── paths.py     사용자 데이터 경로(APP_DIR, companion.json, *.sqlite3, profiles.json, error.log, characters/)와 ASSETS_DIR
├── db.py        SQLite 연결 헬퍼 connect() (모든 저장소가 씀)
├── services.py  캐릭터 앱의 저장소·가격 확인기·타이머·ToolBox 조립 (Tk 없이 만들 수 있음)
├── announcements.py  AI를 거치지 않는 대사 조립: 일정 알림·잔소리·아침 브리핑·타이머·가격 알림
├── crashlog.py  error.log 기록과 시작 실패 안내창
├── screen.py    창 위치 계산: 작업 영역(작업 표시줄 제외)·모든 모니터 영역, 오른쪽 아래 기본 위치
└── ui/          theme(색·글꼴·공용 위젯·round_rect·draw_pill). ui/__init__은 아무것도 import하지 않음
    ├── character/  mascot(캐릭터 창, 앱의 중심: 창·애니메이션·이벤트 큐·확인 카드 흐름·메뉴),
    │               art(프레임 찾기·캐시), speech_bubble(말풍선), timer_badge(타이머 배지), chatbox, confirm_card,
    │               picker(비서 선택), placeholder(그림 없는 캐릭터)
    ├── windows/    메뉴에서 여는 파스텔 창: schedule, todo, price(최저가), price_settings, voice_settings,
    │               conversation_log(대화 기록), cards(카드 목록 창 공용: 두 번 눌러 삭제, 휠 스크롤)
    └── classic/    desktop(파일 정리 도구), assistant(옛 파일/구매 비서 창)
tests/           test_<영역>.py (classic, companion, schedule, pricewatch, todo_focus_voice, announcements, services, entry, screen)
assets/characters/<id>/        상반신 프레임 405×344 + 원본 시트 2장 (reference_sheet, reference_expressions)
assets/characters/<id>/full/   전신 프레임 405×480
tools/build_frames.py          원본 시트 → 정렬된 프레임 (캐릭터별 좌표는 CHARACTERS 설정, 의존성은 tools/requirements-frames.txt)
tools/key_alpha.py             프레임 알파를 0/255로 (Windows 투명 창의 검은 테두리 방지, 여러 번 돌려도 같음)
```

사용자 데이터(`~/.nuri-assistant/`): `companion.json`(설정·네이버 API 키, 못 읽으면 `.bak`로 보존), `error.log`(예외 기록), `companion.sqlite3`(대화·일정·할 일·가격 감시), `history.sqlite3`(파일 이름 변경 이력), `profiles.json`(파일 정리 도구의 작업 프로필), `characters/<id>/`(개인 캐릭터 이미지, 저장소보다 우선).

## 설계 원칙 (꼭 지킬 것)

1. **AI는 직접 바꾸지 않는다.** 일정·할 일·가격 알림의 추가·완료·삭제는 도구가 대기 액션만 만들고, 사용자가 확인 카드(버튼 또는 "응"/"아니")로 승인해야 반영됩니다. 예외는 집중 타이머(영구 변경이 없음). 파일 이름 변경은 미리보기 → 확인 → 실행 → 되돌리기 흐름을 유지합니다(대화로 할 때도 `rename_files`가 미리보기만 만들고 확인 카드 `정리`로 실행, `undo_rename`도 확인 카드).
2. **날짜 계산은 코드가 한다.** 모델은 사용자 표현("다음 주 화요일 3시", "금요일까지")을 그대로 넘기고 `schedule/timeparse.py`가 해석합니다. 새 표현은 여기에 추가하고 `tests/test_schedule.py`에 사례를 넣습니다.
3. **가격은 지어내지 않고, 무료 출처만 쓴다.** 누구나 무료로 키를 받는 네이버 쇼핑 검색 API, 또는 상품 페이지의 구조화 데이터만 씁니다. 심사가 필요한 API(쿠팡 파트너스)는 넣지 않고, 자동 조회를 막는 사이트(쿠팡 웹)는 우회해서 긁지 않습니다.
4. **로컬 우선.** 대화와 번역은 로컬 Ollama, 음성은 로컬 VOICEVOX. API 키는 로컬 설정 파일에만 저장합니다.
5. **시간이 중요한 알림은 AI를 거치지 않는다.** 일정 알림, 할 일 잔소리, 타이머, 아침 브리핑, 가격 알림은 페르소나의 대사 틀(`reminder`, `todo_nag`, `focus_done`, `break_done`, `all_done`, `briefing`, `price_alert`)로 앱이 바로 말합니다. 음성용 일본어 번역만 로컬 AI를 거치고, 실패해도 말풍선은 나옵니다.
6. **도구를 못 쓰는 모델도 동작해야 한다.** `OllamaToolsUnsupported`가 나면 그 세션은 도구 없이 대화만 합니다.
7. **캐릭터는 오리지널만, 모두 성인.** 비서 앱이라 체형은 글래머로 통일하되 옷은 입은 상태(세라·유키 수준)로 그립니다. 기존 작품 캐릭터나 실존 작가 그림체를 따라 하지 않습니다. 노출이 있는 이미지는 저장소가 아니라 `~/.nuri-assistant/characters/`에 둡니다.

## 코드 관례

- SQLite는 매 호출마다 연결을 열고 반드시 닫습니다. 저장소의 `_connect()`는 `db.connect(path, rows=...)`를 돌려주기만 합니다. 안 닫으면 Windows에서 파일이 잠깁니다.
- 사용자 데이터·그림 경로는 `paths.py`에만 적습니다(`Path(__file__).parents[N]`을 다른 곳에 쓰지 않음. 파일을 옮기면 조용히 깨짐). `MascotApp(app_dir)`는 다른 폴더를 받을 수 있으므로 거기서는 파일 이름(`.name`)만 가져다 씁니다.
- 파일 이동은 `classic.core.operations.move_no_clobber`만 씁니다. `Path.rename`은 macOS/Linux에서 기존 파일을 덮어씁니다.
- 새 도구 묶음은 `specs`, `execute`, `take_pending`, `owns`, `confirm`을 갖춘 클래스로 만들어(확인 카드가 필요하면 `ConfirmingTools`를 상속하고 `action_type`만 지정) `services.py`의 `ToolBox([...])`에 넣고, 페르소나 시스템 프롬프트(`personas.py`의 `abilities`)에 쓰임새를 한 줄 추가합니다. 확인 카드는 액션의 `kind`(add/done/rename/undo는 보라 버튼, cancel/delete는 빨간 버튼, 버튼 글자는 `confirm_card.YES_LABELS`), `heading`, `when`, `title`만 읽습니다(`companion.toolbox.ConfirmableAction`).
- 앱이 스스로 하는 대사(원칙 5)는 `announcements.py`에서 조립하고 `tests/test_announcements.py`에 사례를 넣습니다. `MascotApp`은 저장소 갱신과 `talk()`/`say()`만 합니다.
- 캐릭터 창의 시간 값(깜박임, 입 움직임, 표정 복귀, 폴링 주기 등)은 `ui/character/mascot.py` 위쪽 `*_MS` 상수에 모여 있습니다.
- 테스트용 가짜 클라이언트의 `chat_stream`은 `(model, messages, options=None, tools=None)`을 받아야 합니다.
- 오류가 나도 창은 보여야 합니다. 시작 실패는 `app.main()`이 `crashlog`로 `error.log`에 남기고 안내창을 띄웁니다. Tk 콜백 예외는 `MascotApp.report_callback_exception`이 기록하고, 숨겨진 창(비서 선택 중)이면 다시 보이게 합니다. `after()`로 반복하는 루프는 본문을 별도 함수로 빼고 `finally`에서 다시 예약합니다(예외 한 번에 루프가 멈추면 앱이 굳은 것처럼 보임).
- import는 패키지 안에서 상대 경로(`from ..schedule import ...`)만 씁니다. `from nuri_assistant import`처럼 쓰면 테스트(`src.nuri_assistant`)에서 패키지가 두 번 로드됩니다. 순서는 표준 라이브러리 → 점이 많은 상대 import → 점이 적은 상대 import, 그 안에서는 이름순.
- 새 창은 쓰임새에 맞는 `ui/` 하위 폴더에 둡니다: 캐릭터 캔버스에 그리는 것은 `character/`, 메뉴에서 여는 창은 `windows/`, 파일 정리 도구 쪽은 `classic/`. 공용 그리기 함수는 `ui/theme.py`, 카드 목록 창 공용 동작은 `ui/windows/cards.py`에 둡니다(`windows/`의 창끼리는 서로 import하지 않음).
- 최상위 `nuri_assistant/__init__.py`의 이름들은 옛 파일 정리 도구의 API를 호환용으로 다시 내보내는 것입니다. 새 기능은 각 영역 패키지에서 바로 import합니다.
- 텍스트 파일은 항상 `encoding=`을 지정합니다(한국어 Windows 기본은 cp949). 사용자가 메모장으로 고칠 수 있는 파일은 `utf-8-sig`와 cp949도 읽습니다.
- 백그라운드 작업(모델 호출, 가격 조회, 음성 합성)은 스레드에서 돌리고 결과는 `MascotApp.events` 큐에 `("종류", 값...)`으로 넘깁니다. 새 종류는 `_handle_event`의 표에 `_on_<종류>` 메서드로 추가합니다. 스레드에서 Tk 위젯을 직접 만지지 않습니다.
- 말풍선과 음성을 함께 낼 때는 `MascotApp.talk()`, 말풍선만이면 `say()`. 오류·안내 문구는 읽지 않습니다.
- 모델 답변의 일본어 음성 대사는 `<ja>…</ja>`로 받고 `ReplyParser.voice`에 담깁니다(말풍선과 대화 기억에는 남기지 않음).
- 설정 항목을 추가할 때는 `CompanionSettings`에 기본값과 함께 넣습니다. 알 수 없는 키는 로드 시 무시되므로 옛 설정 파일도 열립니다.

## UI 관례

- 색과 공용 위젯은 `ui/theme.py` (파스텔 라일락: 배경 `#f6f2fb`, 강조 `#a68ae0`, 글자 `#2f2640`, 오늘/달성 `#3fae94`, 위험 `#e06c8a`). 새 창은 기본 ttk 표 대신 이 톤의 캔버스 카드로 만듭니다(일정·할 일·최저가 창 참고). 삭제는 두 번 눌러야 되게 합니다(`ui/windows/cards.py`의 `CardListMixin`). 색·글꼴은 `theme`에서 가져오고, 일부러 다른 색만 모듈에 따로 둡니다.
- 말풍선은 **모모톡(블루 아카이브 메신저) 스타일**: 캐릭터 말은 남회색 `MOMO_BUBBLE` 바탕에 흰 글씨, 내 말은 파란 `MOMO_USER`, 머리 위 말풍선의 이름표는 핑크 `MOMO_PINK`(모두 `theme.py`). 대화 기록 창은 동그란 얼굴(`CharacterArt.face`, 상반신 frame의 눈 위치 기준으로 잘라 원형 마스크, Pillow 없으면 이름만)과 이름, 말 차례의 첫 말풍선에만 꼬리. 그 밖의 창(일정·할 일·설정 등)은 파스텔 라일락 그대로.
- 글꼴은 앱에 같이 들어 있는 **나눔스퀘어라운드**(`assets/fonts/`, OFL 1.1, 블루 아카이브 모모톡 같은 둥근 고딕 느낌, Regular·Bold만). `theme.FONT` 하나만 쓰고 글꼴 이름을 직접 적지 않습니다. Windows는 `AddFontResourceEx(FR_PRIVATE)`로 이 프로세스에만 등록하고(설치 안 함), 실패하면 맑은 고딕. 새 Tk 루트를 만들면 `apply_default_fonts(root)`로 메뉴·대화상자·ttk 글꼴도 맞춥니다. 컨테이너에서 화면을 찍을 때는 `~/.local/share/fonts`에 복사하고 `fc-cache -f`.
- 캐릭터 창 캔버스 겹침 순서: 캐릭터 → 타이머 배지(`timer`) → 말풍선(`bubble`) → 확인 카드(`confirm`) → 채팅창(`chat`). 캐릭터를 다시 그린 뒤 이 순서로 `tag_raise`합니다.
- 창 위치(`screen.py`, Tk 없음, `tests/test_screen.py`): 처음엔 주 모니터 **작업 영역**(작업 표시줄 제외, Windows `SPI_GETWORKAREA`)의 오른쪽 아래, 가장자리에서 16px. 사용자가 끌어다 놓은 위치는 저장하고, 다음 실행 때 **모든 모니터를 합친 영역**(가상 화면) 안에 80px 이상 보이면 그대로 둡니다(두 번째 모니터 유지). 화면 밖이면(모니터를 뺐을 때 등) 다시 오른쪽 아래로.
- 항상 위: `-topmost`에 더해 3초마다(`KEEP_ON_TOP_MS`) 다시 걸고 화면 밖으로 사라졌는지 확인합니다(Windows는 전체 화면 앱·다른 항상 위 창 뒤에 맨 위가 풀림). 우리 창(일정·설정 등)이 열려 있거나 끌고 있을 때는 건너뜁니다.
- 채팅창은 캐릭터에 마우스를 올렸을 때만 보이고, 마우스만으로는 입력 포커스를 가져오지 않습니다.
- 프레임은 1:1로 보여 줍니다(상반신 405×344, 전신 405×480, 창 폭 `WIDTH = 415`). 실행 중 리샘플링은 화질을 떨어뜨리니 크기를 바꾸려면 `tools/build_frames.py`의 `W, H`/`FULL_W, FULL_H`와 `WIDTH`를 같이 바꿉니다.
- 전신 모드(`display_mode = "full"`)는 캔버스가 `FULL_EXTRA`(150px) 커지고 창이 위로 늘어납니다. 레이아웃 좌표는 `self.char_bottom`, `self.extra`를 씁니다. 전신 그림이 없는 캐릭터는 상반신으로 나옵니다.
- Windows 투명 키 색 `#010203`은 캐릭터 창 배경 외에는 쓰지 않습니다. 캐릭터 창 배경은 Windows에서 이 색이 뚫려 **배경 없이 캐릭터만** 보입니다(컨테이너 스크린샷의 연보라 사각형은 리눅스에 투명 기능이 없어 보이는 `FALLBACK_BG`일 뿐).
- 이 방식은 한 색만 뚫기 때문에 반투명 픽셀이 거의 검정인 키 색과 섞여 **검은 테두리**가 생깁니다. 그래서 캐릭터 프레임의 알파는 0 또는 255만 씁니다: 가장자리는 110에서 자르고, 상반신 아래 40줄의 흐려지는 부분은 잘라 내 일자로 끝나게 합니다(`tools/key_alpha.py`, `build_frames.py`가 저장할 때 자동 적용. 점무늬 디더링은 채팅창 위에서 지저분해 보여서 버림).
- 캐릭터는 그림의 실제 아래 끝(상반신 자른 선·전신 발끝, `CharacterArt.content_bottom`으로 계산)이 채팅창 위 `CHAT_GAP`(3px)에 오도록 놓습니다. 프레임 아래쪽 투명 줄 수와 상관없이 붙으므로 개인 그림도 같습니다. 개인 그림은 Pillow가 있으면 실행 중에 같은 컷을 적용합니다(`CharacterArt(hard_edges=...)`). 화면 확인은 키 색으로 그린 뒤 키 색 픽셀만 배경으로 바꿔 Windows를 흉내 냅니다.

## 캐릭터

| id | 이름 | 컨셉 | 부르는 말 | 그림 | 기본 목소리(VOICEVOX id) |
|---|---|---|---|---|---|
| nuri | 누리 | 다정한 후배 비서 (기본) | 선배 | 상반신+전신 | 春日部つむぎ (8) |
| sera | 세라 | 어른스러운 누나 비서 | 동생 | 상반신+전신 | 九州そら セクシー (17) |
| yuki | 유키 | 나긋나긋한 힐링계 | 자기 | 상반신+전신 (2026-10-07 시트 재생성) | WhiteCUL ノーマル (23) |
| akane | 아카네 | 츤데레 | 너 | 상반신+전신 | 四国めたん ツンツン (6) |
| shizuku | 시즈쿠 | 쿠데레 | 너 | 상반신+전신 | 冥鳴ひまり (14) |
| hinata | 히나타 | 백갸루 소꿉친구 (금발 사이드 포니테일·비취색 포인트) | 너 | 상반신+전신 | 雨晴はう (10) |
| sakura | 사쿠라 | 상냥한 메이드 | 주인님 | 상반신+전신 | 九州そら あまあま (15) |
| reika | 레이카 | 오죠사마 | 당신 | 상반신+전신 | 四国めたん ノーマル (2) |

목소리 id는 VOICEVOX 기본값 기준이며 실제 설치본에서 확인 전입니다. 8명 모두 그림이 있어 도형 임시 캐릭터(`ui/character/placeholder.py`)는 이제 그림 파일이 없을 때(개인 폴더만 쓰거나 파일이 빠졌을 때)의 대비용입니다.

캐릭터 추가 절차:
1. `companion/personas.py`의 `PERSONAS`에 `Persona` 추가 (대사 틀, `voice_id`, 임시 그림 색 포함).
2. 그림: 기본 시트(왼쪽 전신·오른쪽 큰 상반신)와 3×2 표정 시트를 `assets/characters/<id>/`에 두고, `tools/build_frames.py`의 `CHARACTERS`에 좌표를 적습니다. 좌표는 원본을 확대한 좌표 격자 이미지를 보고 손으로 잽니다(눈 사이 중점·거리, 입 중심, 눈 상자, 전신 머리끝·발끝). 업스케일한 시트는 배치가 같으면 기존 좌표에 배율만 곱하면 됩니다. 자세한 규격과 생성 프롬프트는 `assets/characters/README.md`.
3. 비서 선택 화면에 모든 캐릭터를 나란히 놓고 **그림체가 혼자 다르지 않은지** 먼저 봅니다(선 굵기·채색·눈·얼굴 비율). 다르면 좌표 작업 전에 시트를 다시 뽑습니다(유키 사례).
4. 프레임 결과를 꼭 검수합니다. 문제는 설정으로 고치고, 손으로 이미지를 고치지 않습니다.
   - **표정끼리 머리 크기·위치:** 눈 사이 거리만으로 맞추면 표정 시트 칸마다 얼굴 크기가 달라 표정을 바꿀 때 머리가 커졌다 작아집니다. 기본 표정의 머리 윤곽을 다른 표정 위에 겹쳐 그려 보고(어니언 스킨), 머리카락 윤곽과 얼굴 피부 영역이 가장 잘 겹치는 배율·이동을 찾아 `expressions["adjust"]`에 (배율, dx, dy)로 넣습니다. 보정 후 표정별 머리 폭 차이는 ±2% 안이어야 합니다.
   - **전신 얼굴:** 전신 `mid`/`dist`는 눈동자 중심을 10배 확대해서 재고, 코·입·턱이 상반신과 같은 배율(눈 사이 거리의 배수)인지 확인합니다. 어긋나면 눈·입만 맞아 보이고 얼굴이 이상해집니다. 붙이는 범위는 `full["face"]`(타원 + 표정별 아래 한계)이고, 그 안에서도 얼굴 피부와 앞머리·눈 띠만 가져옵니다(머리카락·헤드셋 줄·손·소매는 전신 그림 것).
   - 그 밖에: 이름표 글자는 `rows`로 끊기, 배경 번짐(어두운 머리 둘레 안개, 턱과 머리카락 사이 회색 그림자)은 `alpha`(`haze_lum`), 이미 입을 벌린 기본 표정은 `talk=None`, 전신 주변 잔상은 `full["erase"]`, 홍조 있는 얼굴의 눈 감기는 `skin="lerp"`.
5. 새 프레임은 `build_frames.py`가 알파를 0/255로 바꿔 저장합니다. 손으로 만든 프레임을 넣었다면 `python tools/key_alpha.py <폴더>`를 돌립니다.
6. 배경 제거(rembg)는 실행마다 아주 약간 결과가 달라질 수 있으니, 고친 캐릭터의 프레임만 교체합니다.

## 남은 일

- 실제 PC(Windows)에서 종합 확인: Ollama 도구 호출, VOICEVOX 음성과 기본 목소리 id, 네이버 API(쿠팡 상품 포함 여부), 투명 배경, 고배율 화면(앱이 DPI 인식을 하지 않아 125%·150%에서 Windows가 창을 늘려 그림이 흐릴 수 있음 — 확인 후 `SetProcessDpiAwareness` 검토), 오른쪽 아래 위치·항상 위 유지
- 대화 파일 정리의 다음 단계(원하면): 확인 카드에는 예시 한 개만 보이니 전체 목록 미리보기 창, 파일 이름에서 날짜·매체를 파일마다 읽는 모드(파일 정리 도구의 `infer_metadata` 방식), 실제 Windows 폴더(OneDrive 바탕 화면 등)에서 확인
- 캐릭터 그림은 8명 모두 완료(2026-10-07). 새 캐릭터를 더 만들 때 시트 생성 프롬프트는 기존 시트를 첨부하고 그림체를 문장으로 고정해야 함(제미나이가 그림체를 잘 못 맞춤, `assets/characters/README.md`. 표정 시트는 새 대화에서 그 캐릭터 기본 시트 한 장만 첨부해야 함(여러 장 붙이면 첨부 이미지를 겹쳐 넣음). 끝까지 겹치면 표정을 한 칸씩 6장 받아 3×2로 이어 붙여 씀)
