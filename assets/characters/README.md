# 캐릭터 이미지 넣는 법

이미지가 없으면 앱이 도형으로 그린 임시 캐릭터를 보여 줍니다. 아래 규칙대로 PNG를 넣으면 자동으로 그 이미지를 씁니다.

## 폴더와 파일 이름

이미지는 다음 두 곳 중 한 곳에 넣습니다. 앞쪽 폴더가 우선입니다.

1. `~/.nuri-assistant/characters/<캐릭터 id>/` (개인용, git에 올라가지 않음)
2. 이 폴더: `assets/characters/<캐릭터 id>/`

| 캐릭터 id | 이름 | 컨셉 |
|---|---|---|
| `nuri` | 누리 | 다정한 후배 비서 (기본 캐릭터), 라일락→민트 웨이브 머리 |
| `sera` | 세라 | 어른스러운 누나 비서, 검은 긴 생머리 |
| `yuki` | 유키 | 나긋나긋한 힐링계 비서, 백발 웨이브 장발 |
| `akane` | 아카네 | 츤데레, 빨간 트윈테일 |
| `shizuku` | 시즈쿠 | 쿠데레, 은청색 단발 |
| `hinata` | 히나타 | 활발한 소꿉친구, 주황 포니테일 |
| `sakura` | 사쿠라 | 상냥한 메이드, 분홍 긴 머리 |
| `reika` | 레이카 | 오죠사마, 금발 드릴 머리 |

표정별 파일 이름은 다음과 같습니다. `neutral.png`만 있어도 동작하고, 없는 표정은 `neutral.png`로 대신합니다.

```text
neutral.png  happy.png  thinking.png  surprised.png  sad.png  angry.png  shy.png
```

기본 표정 이미지만 있고 다른 표정 이미지가 없으면, 기본 표정 그림 옆에 만화식 감정 표시(♪ ? ! 땀방울, 화남 표시, 부끄럼 표시)를 띄워 감정을 보여 줍니다.

선택 파일:

- `<표정>_talk.png`: 입을 벌린 버전입니다. 말할 때 기본 이미지와 번갈아 보여 줘서 입이 움직이는 것처럼 보입니다. 예: `happy_talk.png`
- `<표정>_blink.png`: 눈을 감은 버전입니다. 몇 초마다 깜빡일 때 씁니다.

## 이미지 규격

- 배경이 투명한 PNG
- 무릎 위 또는 상반신 구도, 세로 이미지
- 표시 영역은 약 340×340입니다. 큰 이미지도 자동으로 줄이지만, 400~700px 높이로 미리 줄여 두면 가볍습니다.
- `pip install pillow`를 하면 축소 품질이 좋아집니다. 없어도 동작합니다.

## AI로 생성하기 (Stable Diffusion, 애니 계열 SDXL 모델)

RTX 3060 Ti(8GB)라면 ComfyUI나 Forge에서 애니 계열 SDXL 모델(Illustrious, Animagine 계열 등)을 돌릴 수 있습니다. 모델 라이선스는 사용 전에 확인하세요.

**같은 캐릭터를 유지하는 요령**

1. 기본 표정(`neutral`)을 먼저 원하는 그림이 나올 때까지 뽑고, 시드를 고정합니다.
2. 나머지 표정은 같은 프롬프트와 시드에서 표정 태그만 바꾸거나, 기본 이미지로 img2img 또는 얼굴만 인페인팅해서 만듭니다. 이 방법이 일관성이 가장 좋습니다.
3. 배경은 `simple background, white background`로 뽑은 뒤 rembg 같은 배경 제거 도구로 투명하게 만듭니다.
4. 기존 애니 캐릭터 이름이나 작가 이름은 프롬프트에 넣지 않습니다. 오리지널 캐릭터여야 저작권 문제가 없습니다.

**공통 프롬프트**

```text
masterpiece, best quality, 1girl, solo, upper body, looking at viewer, simple background, white background, anime style, clean lineart
```

**공통 네거티브 프롬프트**

```text
lowres, bad anatomy, bad hands, extra fingers, text, watermark, signature, multiple girls, cropped head
```

**캐릭터별 추가 태그**

| id | 태그 |
|---|---|
| akane | `red hair, twintails, hair ribbon, orange eyes, school uniform, navy blazer, tsundere, pout` |
| shizuku | `silver blue hair, short hair, bob cut, hairclip, blue eyes, expressionless, dark cardigan, calm` |
| hinata | `orange hair, ponytail, scrunchie, green eyes, white t-shirt, energetic, bright smile` |
| sakura | `pink hair, long hair, maid headdress, maid, apron, red purple eyes, gentle smile` |
| reika | `blonde hair, drill hair, tiara, purple eyes, elegant dress, ojou-sama, confident` |

**표정 태그**

| 파일 | 태그 |
|---|---|
| neutral | `light smile, closed mouth` |
| happy | `happy, smile, closed eyes, open mouth` |
| thinking | `thinking, hand on own chin, looking up` |
| surprised | `surprised, wide-eyed, open mouth` |
| sad | `sad, frown, teary eyes` |
| angry | `angry, v-shaped eyebrows, pout` |
| shy | `blush, embarrassed, looking away` |
| `*_talk` | 같은 표정 이미지에서 입 부분만 인페인팅: `open mouth, talking` |
| `*_blink` | 같은 표정 이미지에서 눈 부분만 인페인팅: `closed eyes` |

## 새 캐릭터 추가하기

`src/nuri_assistant/companion/personas.py`의 `PERSONAS`에 `Persona`를 하나 추가하고, 같은 id로 이미지 폴더를 만들면 메뉴에 나타납니다. 성격과 말투는 `summary`와 `speech_style`에 적으면 시스템 프롬프트에 그대로 들어갑니다.

## 누리 이미지 현황

`nuri/` 폴더의 이미지는 AI로 생성한 시트 두 장에서 잘라 만들었습니다.

- 원본: `reference_sheet.webp` (기본 표정, 1024×572 시트를 2000×1116으로 업스케일), `reference_expressions.webp` (표정 6종, 2000×1116)
- 표정 7종: `neutral`, `happy`, `thinking`, `surprised`, `sad`, `angry`, `shy`
  - 배경 제거에는 rembg의 `isnet-anime` 모델을 썼습니다.
  - 두 시트의 캐릭터 크기가 달라서, 눈 위치와 눈 사이 거리를 기준으로 크기와 위치를 맞추고 모두 머리부터 가슴까지로 같은 구도로 잘랐습니다.
- 덧그린 프레임
  - 말하는 입: `neutral_talk`, `thinking_talk`, `sad_talk`
  - 눈 감은 모습: `neutral_blink`
  - 입을 이미 벌린 표정(기쁨, 놀람, 부끄럼)은 그 자체로 말하는 것처럼 보이므로 따로 만들지 않았습니다.
- 대답이 끝나고 몇 초가 지나면 기본 표정으로 돌아가, 다시 눈을 깜빡입니다.

이제 기본 표정과 표정 6종 모두 고화질 시트에서 잘라 냅니다.

이 이미지들은 아래 명령으로 다시 만들 수 있습니다. 시트를 새로 뽑았다면, `tools/build_frames.py`의 `CHARACTERS` 설정에 적힌 자르는 위치와 눈 위치를 먼저 새로 재야 합니다.

```bash
pip install pillow numpy scipy rembg onnxruntime
python tools/build_frames.py nuri   # 세라는 sera, 유키는 yuki
```

## 세라 이미지 현황

`sera/` 폴더도 누리와 같은 방식으로 만들었습니다 (`python tools/build_frames.py sera`).

- 원본: `reference_sheet.webp` (기본 표정, 2000×1116), `reference_expressions.webp` (표정 6종, 1024×572 시트를 2000×1117로 업스케일)
- 말하는 입: `neutral_talk`, `thinking_talk`, `sad_talk`. 화남은 삐친 입 모양이라 입 벌린 그림을 덧그리면 어색해서 만들지 않았습니다.
- 눈 감은 모습: `neutral_blink`

## 유키 이미지 현황

`yuki/` 폴더도 같은 방식으로 만들었습니다 (`python tools/build_frames.py yuki`).

- 원본: `reference_sheet.webp`, `reference_expressions.webp` (둘 다 2000×1116)
- 표정 시트의 칸마다 얼굴 크기가 달라서, 표정별로 눈 사이 거리를 따로 적었습니다(`dist`가 표정별 값). 머리 꼭대기 높이를 기본 표정과 맞추는 방식으로 쟀습니다.
- 칸 아래 한글·영어 이름표가 프레임에 들어오지 않게 자르는 줄(`rows`)을 이름표 위에서 끊었습니다.
- 말하는 입: `neutral_talk`, `thinking_talk`, `sad_talk`, `angry_talk`
- 눈 감은 모습은 눈 양옆 피부색을 줄마다 이어 칠하는 방식(`skin="lerp"`)입니다. 볼 홍조가 있는 그림은 한 가지 색으로 덮으면 눈 자리에 얼룩이 보여서입니다.
- 전신: 머리 옆에 붙은 포스트잇과 배경판의 반투명 잔상을 `erase` 범위에서 지웁니다(불투명한 머리카락은 남음).
- 전신 얼굴은 상반신 얼굴과 비율이 같아서(눈 사이·코·입·턱이 모두 한 배율로 맞음), 눈·입만 붙이지 않고 얼굴 전체를 윤곽선까지 바꿉니다(`full["face"]`). 상반신 눈에 전신 원래 코·턱이 섞이면 위치가 어긋나 보이기 때문입니다. 생각 표정은 턱에 손이 있어 턱 위에서 끊습니다.

## 새 캐릭터 시트 뽑는 요령 (잘라 넣기 쉬운 형식)

누리 때처럼 시트 두 장을 뽑으면 됩니다.

1. **기본 시트:** 오른쪽에 큰 상반신, 왼쪽에 전신이 있는 캐릭터 시트
2. **표정 시트:** 3열×2줄, 칸마다 상반신 한 명과 이름표 (기쁨, 생각, 놀람 / 슬픔, 화남, 부끄럼)

잘라 넣기 쉽게 하려면 다음을 지켜 주세요.

- 머리카락과 겹치는 포스트잇, 아이콘, 효과선은 없을수록 좋습니다. 따로 떨어진 장식은 자동으로 지워지지만, 머리에 붙은 것은 남습니다.
- 두 눈이 모두 보여야 합니다. 앞머리로 한쪽 눈을 가리는 디자인은 표정끼리 위치를 맞추기 어렵습니다.
- 가로 2000px 이상의 고화질로 뽑아 주세요.

## 세라 이미지 프롬프트

### ChatGPT나 Gemini 같은 대화형 이미지 생성기

**기본 시트**

```text
오리지널 애니메이션 스타일 버츄얼 캐릭터 디자인 시트. 성인 여성, 어른스럽고 글래머러스한 누나 비서 캐릭터.
허리까지 오는 윤기 나는 검은 생머리, 옆으로 넘긴 앞머리(두 눈이 모두 보이게), 붉은 눈, 눈 밑 점, 붉은 립, 여유로운 미소.
몸에 딱 맞는 검은 터틀넥 니트, 하이웨스트 펜슬 스커트, 검은 스타킹, 하이힐, 작은 골드 귀걸이, 한쪽 귀에 무선 헤드셋, 태블릿을 든 비서 느낌.
키가 크고 볼륨감 있는 체형, 세련되고 우아한 분위기.
왼쪽에 전신, 오른쪽에 크게 상반신. 배경은 연한 단색으로 깔끔하게, 캐릭터와 겹치는 소품이나 아이콘은 넣지 말 것.
고화질, 깨끗한 선화, 부드러운 조명.
```

**표정 시트**

```text
방금 만든 캐릭터와 완전히 같은 디자인으로 표정 시트를 만들어 줘.
3열 2줄, 칸마다 같은 구도의 상반신 한 명씩: 기쁨, 생각(턱에 손), 놀람 / 슬픔, 화남(삐짐), 부끄럼.
칸 아래에 한글 이름표. 배경은 연한 단색, 머리카락과 겹치는 아이콘이나 효과선은 넣지 말 것. 가로 2000px 이상 고화질.
```

### Stable Diffusion (애니 계열 SDXL 모델)

**포지티브**

```text
masterpiece, best quality, very aesthetic, absurdres, 1girl, solo, original, mature female, adult, tall, curvy, large breasts, wide hips, narrow waist,
long hair, black hair, straight hair, swept bangs, red eyes, mole under eye, red lips, light smile, confident, half-closed eyes,
gold earrings, wireless headset, black turtleneck, ribbed sweater, taut clothes, high-waist skirt, pencil skirt, black pantyhose, high heels, holding tablet, office lady,
upper body, looking at viewer, simple background, white background, clean lineart, soft lighting
```

**네거티브**

```text
lowres, worst quality, bad quality, bad anatomy, bad hands, extra fingers, text, watermark, signature, multiple girls, hair over eyes, child, loli, petite, nsfw, nude
```

표정은 위의 "표정 태그" 표와 같은 방식으로 바꿔서 뽑으면 됩니다.

## 전신 프레임 (`full/`)

`nuri/full/`, `sera/full/`, `yuki/full/`에는 전신 모드용 프레임(405×480)이 들어 있습니다. `python tools/build_frames.py <id>`가 상반신 프레임과 함께 만듭니다.

- 기본 시트 왼쪽의 전신 그림을 잘라 배경을 지우고, 키가 462px이 되게 줄입니다.
- 표정 7종, 말하는 입, 눈 깜빡임은 상반신 프레임에서 **얼굴(눈썹·눈 띠와 입 주변)만** 떼어 눈 위치에 맞춰 붙입니다. 턱과 볼은 잘라 내서, 상반신 표정의 손동작(턱에 손, 볼 감싸기)은 전신에 따라오지 않습니다.
- 설정은 `CHARACTERS[id]["full"]`에 있습니다: 자르는 범위, 전신 그림의 머리 꼭대기·발끝 y, 전신 얼굴의 눈 사이 중점과 거리.
- `full/neutral.png`가 없는 캐릭터는 전신 모드에서도 상반신으로 나옵니다 (상반신과 전신 이미지를 섞어 쓰지 않음).
