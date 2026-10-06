# CLAUDE.md

이 저장소에서 작업하는 사람과 AI 에이전트를 위한 안내서입니다. 작업 기록은 [HISTORY.md](HISTORY.md)에 남깁니다.

## 프로젝트 한 줄 요약

바탕화면에 애니메이션풍 캐릭터 비서를 띄워, 로컬 AI(Ollama)로 대화하면서 일정 관리, 최저가 알림, 파일 이름 정리를 돕는 Windows용 Tkinter 앱입니다. UI 문구와 캐릭터 대사는 모두 한국어입니다.

## 실행과 테스트

```bash
python src/run_nuri.py            # 캐릭터 비서 (기본)
python src/run_nuri.py --classic  # 파일 정리 도구만
python -m unittest discover -s tests   # 저장소 루트에서 실행 (테스트는 src.nuri_assistant 로 import)
python -W error::ResourceWarning -m unittest discover -s tests   # SQLite 연결 누수까지 잡기
python -m pyflakes src/nuri_assistant
```

- Python 3.11 이상. 외부 의존성 없이 돌아가야 합니다. Pillow는 선택 사항이며, 없으면 Tk의 zoom/subsample로 이미지를 줄입니다.
- 테스트는 tkinter 없이 돌아갑니다. UI 모듈(`ui/`)은 단위 테스트에서 import하지 않습니다.
- UI 확인은 리눅스 컨테이너에서 `xvfb-run -a python3.12 스크립트.py`로 띄우고 `import -window root -crop ...`으로 캡처합니다. 가짜 Ollama/API 서버는 `http.server`로 만들어 붙입니다. Windows 전용 동작(투명 배경 `-transparentcolor`, 맑은 고딕)은 컨테이너에서 확인할 수 없습니다.

## 구조

```text
src/nuri_assistant/
├── companion/   # 캐릭터 대화: personas(성격·말투·대사 틀), llm(Ollama 스트리밍+도구 호출),
│                # brain(도구 루프, 대화 기억), reply(표정 태그·<think> 제거), memory, settings, toolbox
├── schedule/    # 일정: timeparse(한국어 날짜 해석), store(SQLite), tools(add/list/cancel_event)
├── pricewatch/  # 최저가: sources(네이버 쇼핑·쿠팡 파트너스·상품 페이지), store, checker(알림 규칙), tools
├── core/ metadata/ storage/ assistant/ shopping/   # 기존 파일 이름 정리 도구와 구매 비서
└── ui/          # mascot(캐릭터 창), chatbox, confirm_card, picker, schedule_window, price_window,
                 # price_settings, placeholder(그림 없는 캐릭터용 도형), theme(색·공용 위젯), desktop(파일 도구)
assets/characters/<id>/   # 캐릭터 표정 PNG와 원본 시트
tools/build_frames.py     # 원본 시트 → 정렬된 표정 프레임
```

사용자 데이터는 모두 `~/.nuri-assistant/`에 있습니다: `companion.json`(설정·API 키), `companion.sqlite3`(대화·일정·가격 감시), `history.sqlite3`(파일 이름 변경 이력), `characters/`(개인 캐릭터 이미지, 저장소보다 우선).

## 설계 원칙 (꼭 지킬 것)

1. **AI는 직접 바꾸지 않는다.** 일정 등록·취소, 가격 알림 등록·해제 같은 변경은 도구가 `pending` 액션만 만들고, 사용자가 확인 카드(버튼 또는 "응"/"아니" 입력)로 승인해야 반영됩니다. 파일 이름 변경도 미리보기 → 확인 → 실행 → 되돌리기 흐름을 유지합니다.
2. **날짜 계산은 코드가 한다.** 작은 로컬 모델은 날짜 계산을 틀리므로, 모델은 사용자 표현("다음 주 화요일 3시")을 그대로 넘기고 `schedule/timeparse.py`가 해석합니다. 새 표현은 여기에 추가하고 `tests/test_schedule.py`에 사례를 넣습니다.
3. **가격은 지어내지 않는다.** 가격은 공식 API(네이버 쇼핑 검색, 쿠팡 파트너스) 또는 상품 페이지의 구조화된 데이터에서만 가져옵니다. 자동 조회를 막는 사이트(쿠팡 웹페이지 등)를 우회해서 긁지 않습니다.
4. **로컬 우선.** 대화는 로컬 Ollama로만 합니다. API 키는 로컬 설정 파일에만 저장하고 저장소에 올리지 않습니다.
5. **시간이 중요한 알림은 AI를 거치지 않는다.** 일정 알림, 아침 브리핑, 가격 알림은 앱이 페르소나의 대사 틀(`reminder`, `briefing`, `price_alert`)로 바로 말합니다.
6. **도구를 못 쓰는 모델도 동작해야 한다.** `OllamaToolsUnsupported`가 나면 그 세션은 도구 없이 대화만 합니다.

## 코드 관례

- SQLite는 매 호출마다 연결을 열고 반드시 닫습니다(`_connect()` 컨텍스트 매니저). 안 닫으면 Windows에서 파일이 잠깁니다.
- 파일 이동은 `core.operations.move_no_clobber`만 씁니다. `Path.rename`은 macOS/Linux에서 기존 파일을 덮어씁니다.
- 테스트용 가짜 클라이언트의 `chat_stream`은 `(model, messages, options=None, tools=None)`을 받아야 합니다.
- 새 도구 묶음은 `specs`, `execute`, `take_pending`, `owns`, `confirm`을 갖춘 클래스로 만들고 `ToolBox`에 넣습니다. 확인 카드는 액션의 `kind`, `heading`, `when`, `title` 속성만 읽습니다.
- 백그라운드 작업(모델 호출, 가격 조회)은 스레드에서 돌리고 결과는 `MascotApp.events` 큐로 UI 스레드에 넘깁니다. 스레드에서 Tk 위젯을 직접 만지지 않습니다.

## UI 관례

- 색과 공용 위젯은 `ui/theme.py`에 있습니다 (파스텔 라일락: 배경 `#f6f2fb`, 강조 `#a68ae0`, 글자 `#2f2640`, 오늘/달성 `#3fae94`, 위험 `#e06c8a`). 새 창은 기본 ttk 위젯 대신 이 톤의 캔버스 카드로 만듭니다.
- 캐릭터 창 캔버스의 겹침 순서: 캐릭터 → 말풍선(`bubble`) → 확인 카드(`confirm`) → 채팅창(`chat`). 캐릭터를 다시 그린 뒤에는 이 순서로 `tag_raise`합니다.
- 채팅창은 캐릭터에 마우스를 올렸을 때만 보입니다. 마우스만 올려서는 입력 포커스를 가져오지 않습니다(다른 프로그램의 키 입력을 뺏지 않도록).
- Windows 투명 키 색은 `#010203`입니다. 캐릭터 창 배경 외에는 이 색을 쓰지 않습니다.

## 캐릭터 추가

1. `companion/personas.py`의 `PERSONAS`에 `Persona`를 추가합니다 (이름, 성격, 말투, 인사·반응 대사, 알림·브리핑·가격 알림 대사 틀, 임시 그림 색).
2. 그림이 있으면 기본 시트(큰 상반신)와 3×2 표정 시트를 `assets/characters/<id>/`에 넣고, `tools/build_frames.py`의 `CHARACTERS`에 눈 위치·자르기 좌표를 적은 뒤 `python tools/build_frames.py <id>`로 프레임을 만듭니다. 좌표 재는 법과 이미지 규격은 `assets/characters/README.md`에 있습니다.
3. 노출이 있는 이미지는 저장소가 아니라 `~/.nuri-assistant/characters/<id>/`에 둡니다.

## 남은 일

- 실제 Ollama 모델(qwen3:8b)과 Windows에서의 종합 확인
- 백발 캐릭터 추가 (시트 대기 중)
- 파일 정리 기능을 대화 도구로 연결 (미리보기·확인 카드 재사용)
- 대화 기록 창을 파스텔 디자인으로 교체
