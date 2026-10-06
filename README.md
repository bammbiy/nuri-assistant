# Nuri Assistant

## 데스크톱 캐릭터 비서

`python src/run_nuri.py`를 실행하면 바탕화면 위에 애니메이션풍 캐릭터가 항상 떠 있습니다. 캐릭터에 마우스를 올리면 바로 아래에 채팅창이 나타나고, 마우스를 치우면 잠시 뒤 사라집니다. 채팅창에 말을 걸면 내 PC에서 돌아가는 AI(Ollama)가 캐릭터 말투로 대답합니다. 대화 내용은 인터넷으로 나가지 않습니다.

- 앱을 켜면 비서 선택 화면이 먼저 나옵니다. "다음부터 이 화면 없이 바로 시작"을 체크하면 마지막 비서로 바로 시작하고, 메뉴의 `비서 선택…`에서 언제든 바꿀 수 있습니다.
- 비서 7명:
  - **누리**: 다정한 후배 비서, 사용자를 '선배'라고 부름. 기본 캐릭터
  - **세라**: 어른스러운 누나 비서, 사용자를 '동생'이라고 부름
  - 아카네(츤데레), 시즈쿠(쿠데레), 히나타(활발한 소꿉친구), 사쿠라(메이드), 레이카(오죠사마)
- 답변 내용에 따라 표정이 바뀝니다 (기본, 웃음, 생각, 놀람, 슬픔, 화남, 부끄럼). 말하는 동안 입이 움직이고, 가끔 눈을 깜빡입니다.
- 대화는 캐릭터별로 `~/.nuri-assistant/companion.sqlite3`에 저장되고, 최근 대화를 기억한 채 이어서 말합니다.
- 캐릭터를 드래그하면 위치를 옮길 수 있고, 클릭하면 반응하면서 채팅창에 바로 입력할 수 있게 됩니다. 위치는 저장됩니다.
- 오른쪽 클릭이나 채팅창 왼쪽의 `⋯` 버튼으로 메뉴를 엽니다: 캐릭터 변경, 내 이름 설정, AI 모델 설정, 대화 기록, 기억 지우기, 파일 정리 도구, 종료
- 누리는 일러스트 이미지로 나오고, 다른 캐릭터는 그림을 넣기 전까지 도형으로 그린 임시 캐릭터가 나옵니다. 오른쪽 클릭이나 `⋯` 메뉴의 `대화 기록 보기`에서 지난 대화를 볼 수 있습니다. 그림 넣는 법과 AI 생성 프롬프트는 [assets/characters/README.md](assets/characters/README.md)에 있습니다.
- **일정 관리**: "내일 오후 3시에 치과 잡아줘", "이번 주 일정 알려줘", "내일 회의 취소해" 처럼 말로 관리합니다.
  - 등록과 취소는 캐릭터 아래에 뜨는 확인 카드에서 `등록`/`취소`를 누르거나 "응", "아니"라고 입력해야 실제로 반영됩니다.
  - 날짜와 시간은 AI가 계산하지 않고, 앱이 한국어 표현("다음 주 화요일 10시", "세 시 반", "30분 뒤", "10월 20일")을 직접 해석합니다. 오전·오후를 말하지 않으면 1~6시는 오후로 봅니다.
  - 일정 10분 전(하루 종일 일정은 그날 오전 9시)에 캐릭터가 먼저 알려 줍니다. "30분 전에 알려줘"처럼 알림 시간을 바꿀 수 있습니다.
  - 그날 처음 켜면 오늘 일정을 브리핑합니다. 메뉴의 `일정 보기`에서 목록을 보고 삭제할 수 있습니다.
  - 일정 기능은 도구 호출(tool calling)을 지원하는 모델이 필요합니다. 기본 모델 `qwen3:8b`는 지원합니다. 지원하지 않는 모델을 고르면 대화만 됩니다.
- **최저가 알림**: "에어팟 프로 30만원 아래로 떨어지면 알려줘", "로지텍 마우스 최저가 얼마야?"처럼 말합니다.
  - 가격은 무료로 쓸 수 있는 곳에서만 가져옵니다: 네이버 쇼핑 검색 API(누구나 무료 발급, 하루 25,000회, 네이버 쇼핑에 올라온 여러 쇼핑몰의 최저가). 상품 링크로도 감시할 수 있지만(키 불필요), 쿠팡처럼 자동 조회를 막는 사이트는 상품 이름으로 감시해야 합니다.
  - 메뉴의 `가격 알림 설정…`에서 네이버 API 키와 확인 주기(기본 60분)를 넣습니다. 키는 `~/.nuri-assistant/companion.json`에만 저장됩니다.
  - 목표가 이하가 되거나(목표가가 없으면) 최저가가 새로 내려가면 캐릭터가 알려 주고, 말풍선을 누르면 상품 페이지가 열립니다.
  - 메뉴의 `최저가 알림` 창에서 AI 없이 직접 추가·삭제하고 현재 가격과 지금까지의 최저가를 볼 수 있습니다.
- **할 일**: "보고서 금요일까지 해야 해"라고 하면 확인 카드를 거쳐 추가됩니다. "보고서 끝냈어"라고 하면 완료 카드가 뜹니다.
  - 마감 전날 저녁 7시와 당일 아침 9시에 캐릭터가 잔소리합니다. 기한이 지난 할 일은 아침 브리핑에 나옵니다.
  - 메뉴의 `할 일` 창에서 직접 추가하고, 동그라미를 눌러 완료하고, D-day를 볼 수 있습니다.
- **집중 타이머**: "25분 집중 모드", "50분 집중 10분 휴식 2번"처럼 말하거나 메뉴의 `집중 타이머 시작`을 누릅니다. 캐릭터 옆에 남은 시간 배지가 뜨고(누르면 멈춤), 집중·휴식이 끝날 때마다 캐릭터가 알려 줍니다.
- **일본어 음성**: 말풍선은 한국어, 목소리는 일본어 애니 보이스입니다.
  - 무료 음성 엔진 [VOICEVOX](https://voicevox.hiroshiba.jp/)를 설치해서 켜 두고, 메뉴의 `음성 설정…`에서 `음성으로 말하기`를 켭니다. 같은 방식으로 동작하는 AivisSpeech도 쓸 수 있습니다.
  - AI 답변은 AI가 일본어 대사를 함께 써서(`<ja>…</ja>`, 말풍선에는 안 보임) 그대로 읽고, 앱이 만드는 대사(알림, 브리핑 등)는 로컬 AI가 일본어로 번역해서 읽습니다.
  - 캐릭터마다 어울리는 기본 목소리가 정해져 있고(예: 아카네 = 四国めたん ツンツン), 음성 설정에서 바꾸고 미리 들어볼 수 있습니다.
  - VOICEVOX 캐릭터 음성을 공개 콘텐츠에 쓸 때는 'VOICEVOX:캐릭터명' 표기 등 각 캐릭터의 이용 규약을 따라야 합니다.
- 파일 정리 같은 그 밖의 작업을 캐릭터가 직접 실행하는 기능은 다음 단계에서 붙입니다.
- 개발 안내는 [CLAUDE.md](CLAUDE.md), 개발 기록은 [HISTORY.md](HISTORY.md)에 있습니다.

### Ollama 준비 (최초 1회)

1. https://ollama.com 에서 Windows용 Ollama를 설치합니다. 설치하면 백그라운드에서 자동 실행됩니다.
2. 터미널에서 모델을 받습니다. 기본 모델은 RTX 3060 Ti(8GB VRAM)에 맞춘 `qwen3:8b`입니다.

```powershell
ollama pull qwen3:8b
```

3. (권장) 캐릭터 이미지를 부드럽게 축소하도록 Pillow를 설치합니다. 없어도 실행됩니다.

```powershell
pip install pillow
```

4. 앱을 실행합니다.

```powershell
python src/run_nuri.py           # 캐릭터 비서
python src/run_nuri.py --classic # 캐릭터 없이 파일 정리 도구만
```

다른 모델을 쓰려면 메뉴의 `AI 모델 설정`에서 이름을 바꿉니다. 예를 들어 한국어에 강한 `exaone3.5:7.8b`도 8GB VRAM에 들어갑니다. 설정은 `~/.nuri-assistant/companion.json`에 저장됩니다.

## Assistant Mode

Nuri Assistant combines file organization and purchase decisions in one review-first desktop workflow.

- File assistant: choose a folder and type a request such as `20260715 ja00 1부터 하위 폴더까지 정리해줘`. The app extracts the date, media code, page number, naming order, and recursive option, then shows a rename preview before any files change.
- Purchase assistant: add the product you are considering plus alternatives. It ranks products from the price, rating, review count, warranty, and your fit score. The result only uses the facts entered in the app; it does not claim live prices, reviews, or market research.

The built-in score works offline from the facts you enter. The AI Research panel adds live web research when an OpenAI API key is supplied, while keeping the same flow: collect sources, show the evidence, recommend, and leave the final purchase decision to you.

### AI shopping research

The Purchase Assistant includes an `AI Research` panel. Enter a product name or product link, optionally add your own candidates, then enter an OpenAI API key for the current session and press `AI Research`.

- The key is never written to a project file or profile.
- The request sends `store: false` and asks the model to research current web evidence before recommending a purchase.
- The response should be treated as research support: always recheck the current price, seller, warranty, and delivery conditions before buying.

You can also set the key once for the current Windows terminal before starting the app:

```powershell
$env:OPENAI_API_KEY = "your_api_key"
python src/run_nuri.py
```

반복되는 문서 파일명 정리 작업을 빠르고 안전하게 처리하기 위한 데스크톱 파일 관리 도구입니다.

파일을 추가하면 날짜, 매체코드, 페이지 번호를 기반으로 변경 예정 파일명을 미리 보여주고, 충돌 여부를 확인한 뒤 일괄 rename을 실행합니다. 변경 이력은 SQLite에 저장되며 마지막 변경은 되돌릴 수 있습니다.

## 핵심 기능

- PDF 및 일반 파일 다중 선택
- 폴더 스캔 및 하위폴더 포함 스캔
- `{DATE}_{MEDIA}_{PAGE}` 기반 파일명 규칙 생성
- 실무용 파일명 규칙 프리셋
- 작업 프로필 저장 및 불러오기
- 날짜, 매체코드, 페이지 번호 자동 추론
- 변경 예정 파일명 미리보기
- 검색어 및 상태별 미리보기 필터
- 목록에서 선택 항목 제거
- 상태별 색상 표시
- 미리보기 결과 CSV 저장
- 대상 파일명 충돌 및 배치 내 중복 감지
- SQLite 기반 rename 히스토리 저장
- 마지막 작업 배치 전체 되돌리기
- 외부 패키지 없이 실행 가능한 Tkinter GUI

## 파일명 규칙

기본 규칙은 다음과 같습니다.

```text
{DATE}_{MEDIA}_{PAGE}
```

예시:

```text
20260628_ja00_001.pdf
```

규칙 입력창에서 다음처럼 바꿀 수 있습니다.

```text
{MEDIA}-{DATE}-{PAGE}
```

결과:

```text
ja00-20260628-001.pdf
```

지원하는 토큰:

- `{DATE}`: `YYYYMMDD`
- `{MEDIA}`: 영문 2자 + 숫자 2자, 예: `ja00`
- `{PAGE}`: 3자리 페이지 번호, 예: `001`

## 실행 방법

Python 3.11 이상을 권장합니다.

```bash
cd nuri-assistant
python src/run_nuri.py
```

## 실무 사용 흐름

1. `파일 추가` 또는 `폴더 불러오기`로 작업 대상을 추가합니다.
2. 필요하면 `하위폴더 포함`을 켜고 폴더를 다시 불러옵니다.
3. 날짜, 매체코드, 시작 페이지를 확인합니다.
4. 프리셋 또는 직접 입력으로 파일명 규칙을 정합니다.
5. 반복 작업이면 `작업 프로필`로 현재 설정을 저장합니다.
6. `미리보기`에서 `ready`, `conflict`, `error` 상태를 검수합니다.
7. 검색어 또는 상태 필터로 특정 파일과 문제 항목만 확인합니다.
8. 제외할 파일은 선택 후 `선택 제거`를 누릅니다.
9. 승인/공유가 필요하면 `CSV 저장`으로 변경 예정 목록을 남깁니다.
10. 문제가 없으면 `변경 실행`을 누릅니다.
11. 실수한 경우 `마지막 배치 취소`로 직전 작업 묶음을 되돌립니다.

## 작업 프로필

자주 쓰는 작업 조건은 프로필로 저장할 수 있습니다. 프로필에는 다음 설정이 포함됩니다.

- 날짜
- 매체코드
- 시작 페이지
- 파일명 규칙
- 하위폴더 포함 여부

프로필 파일은 사용자 홈의 `.nuri-assistant/profiles.json`에 저장됩니다.

## 테스트

```bash
cd nuri-assistant
python -m unittest discover -s tests
```

## 프로젝트 구조

```text
nuri-assistant/
├── README.md
├── src/
│   ├── run_nuri.py
│   └── nuri_assistant/
│       ├── __init__.py
│       ├── companion/
│       │   ├── brain.py
│       │   ├── llm.py
│       │   ├── memory.py
│       │   ├── personas.py
│       │   ├── reply.py
│       │   └── settings.py
│       ├── core/
│       │   ├── export.py
│       │   ├── models.py
│       │   ├── naming.py
│       │   ├── operations.py
│       │   ├── planner.py
│       │   └── scanner.py
│       ├── pricewatch/
│       │   ├── checker.py
│       │   ├── sources.py
│       │   ├── store.py
│       │   └── tools.py
│       ├── schedule/
│       │   ├── store.py
│       │   ├── timeparse.py
│       │   └── tools.py
│       ├── metadata/
│       │   ├── patterns.py
│       │   └── inference.py
│       ├── storage/
│       │   ├── history.py
│       │   └── profiles.py
│       └── ui/
│           ├── assistant.py
│           ├── desktop.py
│           ├── mascot.py
│           └── placeholder.py
├── assets/
│   └── characters/
│       └── README.md
└── tests/
    ├── test_companion.py
    └── test_nuri_assistant.py
```

## 설계 방향

기존 MVP는 하나의 엔진 파일에 검증, 추론, 미리보기, 실행, 히스토리 저장이 모두 섞여 있었습니다. 현재 구조는 기능 확장을 염두에 두고 역할별로 나눴습니다.

- `core`: 파일명 생성, 검증, 미리보기, rename/undo 실행
- `core.export`: 검수용 CSV 저장
- `core.scanner`: 폴더 내 문서/이미지 파일 스캔
- `metadata`: 파일명에서 날짜, 매체코드, 페이지를 추론하는 규칙
- `storage`: SQLite 히스토리 저장소, 배치 단위 이력, 작업 프로필
- `companion`: 캐릭터 설정(페르소나), 로컬 Ollama 연결, 표정 태그 해석, 대화 기억, 설정 저장
- `schedule`: 한국어 날짜/시간 해석, 일정 저장소(SQLite), AI가 부르는 일정 도구(등록·조회·취소, 확인 대기)
- `pricewatch`: 가격 출처(네이버 쇼핑 검색 API·상품 페이지), 감시 저장소, 알림 규칙, AI가 부르는 가격 도구
- `ui`: Tkinter 데스크톱 화면 (`mascot.py`: 캐릭터 창, `desktop.py`: 파일 정리 도구)

이 구조를 기준으로 다음 단계에서는 폴더 감시, OCR 필요 여부 검사, 업로드 상태 모니터링 같은 기능을 독립 모듈로 붙일 수 있습니다.

## 개발 로드맵

### 1단계: File Rename MVP

- 파일 선택
- 규칙 기반 파일명 생성
- 미리보기
- 일괄 rename
- 히스토리 저장
- 마지막 변경 취소

### 2단계: Folder Watcher

- 다운로드 폴더 감시
- 새 PDF 자동 감지
- rename 후보 자동 생성
- 처리 완료 알림

### 3단계: OCR Inspector

- PDF 텍스트 존재 여부 검사
- OCR 필요 파일 분류
- OCR 처리 도구 연동 준비

### 4단계: Upload Monitor

- 업로드 성공, 실패, 재시도 이력 관리
- 작업 현황 대시보드 제공

### 5단계: NewsFlow

Nuri Assistant, Folder Watcher, OCR Inspector, Upload Monitor를 하나의 문서 처리 파이프라인으로 통합합니다.

## 포트폴리오 포인트

이 프로젝트는 단순 파일명 변경 도구에서 시작하지만, 장기적으로는 콘텐츠 제작 업무에서 발생하는 문서 처리 흐름을 자동화하는 파이프라인으로 확장할 수 있습니다. 핵심은 `미리보기 -> 실행 -> 이력 기록 -> 되돌리기` 흐름을 안전하게 제공하는 것입니다.
