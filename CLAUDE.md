# CLAUDE.md

이 저장소에서 작업하는 사람과 AI 에이전트를 위한 안내서입니다. 이 파일은 매 턴(서브 에이전트 포함) 읽히므로 짧게 유지합니다. 상세 내용은 아래 문서에서 필요한 부분만 찾아 읽습니다.

| 문서 | 내용 | 언제 읽나 |
|---|---|---|
| `docs/RULES.md` | 상세 폴더 구조, 코드 관례(기능별 동작 규칙 포함), UI 관례, 캐릭터 표·추가 절차 | 그 영역을 고치기 전에 키워드로 Grep해서 해당 줄만 |
| `docs/TODO.md` | 남은 일, 실사용 확인 전 목록 | 다음 할 일을 정할 때, 일을 끝냈을 때 |
| `HISTORY.md` | 무엇을 왜 바꿨는지(최신이 위) | 새 작업 시작 때 맨 위 한두 항목만(`head`), 끝나면 추가 |
| `assets/characters/README.md` | 캐릭터 시트 규격·생성 프롬프트 | 캐릭터 그림 작업 때 |

**문서 규칙(사용자 지시):** 작업을 하나 끝낼 때마다 문서를 갱신해 같은 커밋에 넣습니다. 바뀐 사실은 성격에 맞는 곳(원칙·명령·분담은 CLAUDE.md, 구조·관례·캐릭터는 `docs/RULES.md`, 남은 일은 `docs/TODO.md`)에, 무엇을 왜 바꿨는지(사용자 요청·원인·결정)는 HISTORY.md 맨 위에 적습니다. 문서만 고치는 작업도 예외가 아닙니다. CLAUDE.md에는 매 작업에 필요한 것만 두고 새 세부 규칙은 `docs/RULES.md`에 넣습니다.

## 프로젝트 요약

바탕화면에 애니메이션풍 캐릭터 비서를 항상 띄워 두고, 내 PC의 로컬 AI(Ollama)와 한국어로 대화하는 Windows용 Tkinter 앱입니다.

**핵심 콘셉트(처음부터의 기획):** 사용자가 무슨 작업을 하든 캐릭터가 **화면 오른쪽 아래(작업 표시줄 바로 위)에 항상 위로 떠 있고**, 마우스를 올리면 바로 아래에 채팅창이 나타나 메신저처럼 대화합니다. 말풍선으로 먼저 알려 주고(일정·잔소리·가격), 확인 카드로 승인받아 앱 기능을 대신 실행합니다. 이 "항상 떠 있는 채팅 비서" 경험을 깨는 변경은 하지 않습니다. 캐릭터가 일정·할 일·집중 타이머·최저가 알림을 관리하고, 일본어 애니 보이스(VOICEVOX)로 말할 수 있습니다. 원래는 문서 파일 이름 일괄 정리 도구였고, 그 기능도 메뉴와 `--classic` 실행으로 남아 있습니다.

- 사용자: 한국어 사용자, PC는 RTX 3060 Ti(8GB VRAM) + RAM 32GB, Windows
- UI 문구와 캐릭터 대사는 모두 한국어, 음성만 일본어
- 올리는 방식(사용자 지시): PR 없이 `main`에 바로 올립니다. 세션의 작업 브랜치(`claude/pensive-archimedes-kwhp16`)에서 커밋하고, 같은 커밋을 작업 브랜치와 `main`에 함께 푸시합니다(`git push origin HEAD:main`, 빨리 감기만. 강제 푸시는 하지 않음)
- 커밋 작성자(사용자 지시): 커밋이 사용자 계정으로 보이게, 세션을 시작하면 커밋 전에 `git config user.name "bammbiy"`와 `git config user.email "83348724+bammbiy@users.noreply.github.com"`(깃허브의 비공개용 주소)을 설정합니다. 컨테이너가 새로 만들어지면 설정이 사라지니 매번 확인합니다

## 실행과 테스트

```bash
python src/run_nuri.py            # 캐릭터 비서 (비서 선택 화면부터). Windows는 start_nuri.bat 더블클릭
python src/run_nuri.py --classic  # 파일 정리 도구만
python src/run_nuri.py --autostart  # 윈도우 시작 때 쓰는 실행(비서 선택 화면 없이 바로). 시작 프로그램 등록은 메뉴에서
python -m nuri_assistant [--classic]   # 같은 실행 (src/ 안에서, 또는 pip install -e . 뒤 어디서나. 설치하면 nuri-assistant 명령도 생김)
pip install -e .[dev]             # 선택: 개발용 설치(pyflakes). 그림이 assets/에 있어서 편집 설치(-e)만 지원
python -m unittest discover -s tests                         # 저장소 루트에서 (테스트는 src.nuri_assistant 로 import)
python -W error::ResourceWarning -m unittest discover -s tests   # SQLite 연결 누수까지 잡기 (현재 256개, tkinter·화면이 없으면 UI 스모크 3개는 건너뜀)
python -m pyflakes src tests tools
python tools/build_exe.py         # Windows 실행 파일 묶음(dist/NuriAssistant/, pyinstaller 필요). 빌드 뒤 --selfcheck로 켜지는지 확인
pip install -r tools/requirements-frames.txt                 # 프레임 생성 도구용 (앱에는 필요 없음)
python tools/build_frames.py nuri|sera|yuki|akane|shizuku|hinata|sakura|reika [출력폴더]   # 캐릭터 프레임 재생성
```

- Python 3.10 이상(3.11 권장). 앱 실행에 외부 패키지는 필요 없습니다. Pillow는 선택(있으면 썸네일 축소가 부드러움).
- 외부 프로그램: Ollama(기본 모델 `qwen3:8b`, 도구 호출 지원 필요), VOICEVOX(음성, 선택).
- 단위 테스트는 tkinter 없이 돌아가고 `ui/`를 import하지 않습니다. UI는 `tests/test_ui_smoke.py`가 앱을 임시 폴더로 띄워 메뉴의 창을 모두 열어 봅니다(tkinter와 화면이 있을 때만, 없으면 건너뜀). 컨테이너에서는 `xvfb-run -a /usr/bin/python3.12 -m unittest tests.test_ui_smoke`(tkinter가 없으면 `apt-get update && apt-get install -y python3-tk`). 메뉴 항목을 추가하면 이 테스트의 목록에도 넣습니다. UI 파일을 옮기거나 import를 고치면 이 테스트를 돌립니다.
- 푸시하면 GitHub Actions(`.github/workflows/tests.yml`)가 리눅스(3.10·3.12, xvfb)와 Windows(3.12)에서 pyflakes와 전체 테스트를 돌리고, Windows exe 묶음도 빌드해 켜지는지 확인한 뒤 Artifacts(`NuriAssistant-windows`)에 올립니다. `v`로 시작하는 태그를 푸시하면 릴리스에도 올라갑니다(태그는 사용자가 요청할 때만). 푸시 뒤 결과를 확인합니다.
- 패키지 정보는 `pyproject.toml`(버전은 `nuri_assistant.__version__`과 같이 올림), 편집기 설정은 `.editorconfig`(`start_nuri.bat`은 일부러 cp949 + CRLF).
- UI 확인 방법(클라우드 컨테이너): tkinter가 있는 `python3.12`로 `xvfb-run -a -s "-screen 0 1280x1000x24" python3.12 스크립트.py`를 실행하고, `import -window root -crop WxH+X+Y`로 캡처합니다. 가짜 Ollama·네이버·VOICEVOX 서버는 `http.server`로 만들어 `ollama_url`, `NaverShopping.URL`, `voice_url`을 그쪽으로 돌립니다. `MascotApp(app_dir)`에 임시 폴더를 넘기면 사용자 데이터를 건드리지 않습니다.
- 컨테이너에서 확인할 수 없는 것: Windows 투명 배경(`-transparentcolor`), Windows에서 번들 글꼴 등록(`AddFontResourceEx`), 테두리 없는 창의 포커스, 고배율(125%/150%) 화면, 실제 Ollama·VOICEVOX·네이버 API. 이것들은 아직 실사용 확인 전입니다.

## 구조 (요약, 상세는 docs/RULES.md "구조")

- `src/run_nuri.py` 진입점, `src/nuri_assistant/app.py`의 `main()`
- `src/nuri_assistant/`: `companion/`(페르소나·Ollama·대화 루프·도구 라우팅·친밀도), `schedule/` `todo/` `focus/` `memo/` `pricewatch/` `weather/` `fun/` `pcwatch/` `presence/` `voice/`(영역별 저장소·도구·순수 로직), `classic/`(파일 이름 정리 도구), `announcements.py`(AI를 거치지 않는 대사), `services.py`(조립), `paths.py`(모든 경로), `db.py`, `routine.py`, `autostart.py`, `screen.py`
- `ui/`: `character/`(캐릭터 창 `mascot.py`가 앱의 중심, 기능별 메서드는 `*_mixin.py`, 시간 상수는 `timing.py`), `windows/`(메뉴에서 여는 창), `classic/`, `theme.py`. 단위 테스트는 `ui/`를 import하지 않음
- `tests/test_<영역>.py`, `tools/build_frames.py`(캐릭터 프레임), `assets/characters/<id>/`, `reports/`
- 사용자 데이터는 `~/.nuri-assistant/`(설정 `companion.json`, `*.sqlite3`, `error.log`, 개인 캐릭터 그림)

## 설계 원칙 (꼭 지킬 것)

1. **AI는 직접 바꾸지 않는다.** 일정·할 일·가격 알림·기억 수첩의 추가·완료·삭제는 도구가 대기 액션만 만들고(다운로드 정리 제안·복사한 글 제안도 같은 확인 카드), 사용자가 확인 카드(버튼 또는 "응"/"아니")로 승인해야 반영됩니다. 예외는 집중 타이머(시작·멈춤은 바로 실행. 끝난 집중 블록의 시각·분만 하루 정리용으로 자동 기록). 파일 이름 변경은 미리보기 → 확인 → 실행 → 되돌리기 흐름을 유지합니다(대화로 할 때도 `rename_files`가 미리보기만 만들고 확인 카드 `정리`로 실행, 카드의 `목록`이 전체 미리보기 창, `undo_rename`도 확인 카드).
2. **날짜 계산은 코드가 한다.** 모델은 사용자 표현("다음 주 화요일 3시", "금요일까지")을 그대로 넘기고 `schedule/timeparse.py`가 해석합니다. 새 표현은 여기에 추가하고 `tests/test_schedule.py`에 사례를 넣습니다.
3. **가격·날씨는 지어내지 않고, 무료 출처만 쓴다.** 날씨는 키 없는 Open-Meteo이며 도시를 정했을 때만 호출하고, 밖으로 나가는 것은 도시 이름(좌표 찾기)과 좌표뿐입니다. 원칙 4(로컬 우선)의 예외로, 실패하면 날씨 줄만 빠집니다. 누구나 무료로 키를 받는 네이버 쇼핑 검색 API, 또는 상품 페이지의 구조화 데이터만 씁니다. 심사가 필요한 API(쿠팡 파트너스)는 넣지 않고, 자동 조회를 막는 사이트(쿠팡 웹)는 우회해서 긁지 않습니다.
4. **로컬 우선.** 대화와 번역은 로컬 Ollama, 음성은 로컬 VOICEVOX. API 키는 로컬 설정 파일에만 저장합니다.
5. **시간이 중요한 알림은 AI를 거치지 않는다.** 일정 알림, 할 일 잔소리, 타이머, 아침 브리핑(날씨 문장 포함), 가격 알림, 돌아옴 인사·쉬는 시간·물 알림, 하루 정리는 페르소나의 대사 틀(`reminder`, `todo_nag`, `focus_done`, `break_done`, `all_done`, `briefing`, `price_alert`, `welcome_back`, `take_break`, `drink_water`, `wrapup`, `level_up`, `birthday`, `together`, 혼잣말 `idle_talk`, 쓰다듬기 `pats`, 연타 `pokes_many`, 정각 `chime`, 명절 `holiday`, 계절 첫날 `season`)과 코드가 만든 문장으로 앱이 바로 말합니다. 운세·가위바위보 결과도 코드(`fun/`)가 정하고 모델은 말투만 입힙니다. 음성용 일본어 번역만 로컬 AI를 거치고, 실패해도 말풍선은 나옵니다.
6. **도구를 못 쓰는 모델도 동작해야 한다.** `OllamaToolsUnsupported`가 나면 그 세션은 도구 없이 대화만 합니다.
7. **캐릭터는 오리지널만, 모두 성인.** 비서 앱이라 체형은 글래머로 통일하되 옷은 입은 상태(세라·유키 수준)로 그립니다. 기존 작품 캐릭터나 실존 작가 그림체를 따라 하지 않습니다. 노출이 있는 이미지는 저장소가 아니라 `~/.nuri-assistant/characters/`에 둡니다.

## 꼭 지킬 코드 규칙 (전체는 docs/RULES.md "코드 관례"·"UI 관례")

- SQLite는 매 호출마다 열고 반드시 닫습니다(`db.connect`). 경로는 `paths.py`에만 적습니다.
- 파일 이동은 `classic.core.operations.move_no_clobber`만. 텍스트 파일은 항상 `encoding=` 지정.
- 패키지 안 import는 상대 경로만(`from ..schedule import ...`).
- 백그라운드 작업은 스레드에서, 결과는 `MascotApp.events` 큐로. 스레드에서 Tk 위젯을 만지지 않습니다. `after()` 루프는 `finally`에서 다시 예약.
- 새 도구 묶음은 `ConfirmingTools` 방식으로 만들어 `services.py`의 `ToolBox`에 넣고 페르소나 `abilities`에 한 줄 추가.
- 앱이 스스로 하는 대사는 `announcements.py`에서 조립하고 `tests/test_announcements.py`에 사례 추가.
- 색·글꼴은 `ui/theme.py`(`theme.FONT`)에서만. 새 창은 파스텔 캔버스 카드, 삭제는 두 번 눌러야.
- 설정 항목은 `CompanionSettings`에 기본값과 함께 추가. 밖으로 나가는 데이터가 생기면 개인정보 안내 창 문구도 수정.
- UI 파일을 옮기거나 import를 고치면 `tests/test_ui_smoke.py`를 xvfb로 돌립니다(방법은 위 "실행과 테스트").

## 모델 역할 분담 (사용자 지시)

메인 모델(Fable)이 전체 틀을 잡고, 실제 일은 `.claude/agents/`의 서브 에이전트에 나눕니다. 각 에이전트의 모델은 파일의 `model:`로 고정되어 메인 모델 선택과 상관없이 그대로 돕니다.

| 담당 | 모델 | 맡는 일 |
|---|---|---|
| 메인 | Fable | 요구 파악, 설계·범위 결정, 일 쪼개기와 지시서 작성, 결과 확인(diff와 테스트를 직접), 사용자 대화, 문서 갱신, 커밋·푸시. 눈으로 판단하는 일(캐릭터 좌표·표정 검수) |
| `expert` | Opus | 고난도 작업: 여러 모듈에 걸친 구현, 동시성·스트리밍·상태 흐름처럼 틀리기 쉬운 코드, 원인 모를 버그 추적, 까다로운 리팩터링, 캐릭터 대사 쓰기 |
| `worker` | Sonnet | 범위가 분명한 구현: 함수 추가·수정, 테스트 작성, 정해진 규칙대로 여러 파일 고치기, 실패 테스트 고치기 |
| `reviewer` | Sonnet | 커밋 전 변경 검토(읽기만). 지적만 하고 반영 여부는 메인이 정함 |
| `searcher` | Haiku | 코드 검색·여러 파일 훑어보기(읽기만) |
| `helper` | Haiku | 테스트·pyflakes 실행과 결과 요약, 지정된 기계적 치환, 정해진 스크립트 실행 |

- 일을 맡길 때는 그 일을 해낼 수 있는 가장 싼 모델을 고릅니다: Haiku로 되면 Haiku, 아니면 Sonnet, 그래도 어려우면 Opus. 메인은 구현을 직접 길게 하지 않습니다.
- 서브 에이전트는 커밋·푸시·문서(CLAUDE.md·HISTORY.md·docs/) 수정을 하지 않습니다. 보고는 그대로 믿지 않고 메인이 diff와 테스트로 확인한 뒤 반영합니다.

## 한도 아끼기 (사용자 지시)

- 가장 싼 길부터. 몇 줄 고치면 끝나는 일은 메인이 바로 고칩니다. 서브 에이전트는 시작할 때마다 문맥을 새로 읽으니 작은 일에는 오히려 비쌉니다.
- 서브 에이전트는 큰 일에만, 한 번에 2개까지. 지시서에 파일·함수·줄 번호를 적어 다시 검색하지 않게 하고, 끝에 "보고는 25줄 이내"를 붙입니다.
- 큰 파일은 통째로 읽지 않습니다(`ui/character/mascot.py`와 믹스인은 필요한 파일만, `companion/personas.py`, `announcements.py`, `tools/build_frames.py`, `HISTORY.md`, `docs/RULES.md`, `README.md`). Grep으로 위치를 찾고 그 부분만 offset/limit으로 읽습니다.
- 테스트·로그·diff는 결과 줄만 봅니다(`tail`, `grep`, `git diff --stat`). 전체를 쏟아내지 않습니다.
- 서로 상관없는 명령은 한 번에 묶어 실행합니다. 이미 본 파일·이미지는 다시 열지 않습니다. 스크린샷은 필요한 부분만 잘라서 봅니다(이미지는 토큰이 큼).
- 문서 기록과 커밋·푸시는 작업 끝에 한 번에. 사용자 보고는 짧게, 요점만.
- 주제가 바뀌면 `/clear`로 새로 시작합니다(긴 대화는 매 턴 전체가 다시 읽힘). 이어서 할 일은 `docs/TODO.md`와 HISTORY.md에 남겨 두면 됩니다.

## 글쓰기

깃허브에서 바로 보이는 글은 영어로 씁니다(사용자 지시): `README.md`(한국어판은 `README.ko.md`, 둘을 같이 고침), 커밋 메시지, `pyproject.toml` 설명, 워크플로·코드 주석. 작업 문서(CLAUDE.md, HISTORY.md, `docs/`)와 앱 화면 문구·대사는 한국어 그대로입니다.

README·HISTORY·문서·커밋 메시지는 사람이 쓴 것처럼 평이하게 씁니다. 꾸밈 기호·이모지·항목마다 붙는 굵은 이름표·과장된 표현을 쓰지 않고, 사실과 숫자를 적습니다.
