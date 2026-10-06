# 캐릭터 이미지 넣는 법

이미지가 없으면 앱이 도형으로 그린 임시 캐릭터를 보여 줍니다. 아래 규칙대로 PNG를 넣으면 자동으로 그 이미지를 씁니다.

## 폴더와 파일 이름

이미지는 다음 두 곳 중 한 곳에 넣습니다. 앞쪽 폴더가 우선입니다.

1. `~/.nuri-assistant/characters/<캐릭터 id>/` (개인용, git에 올라가지 않음)
2. 이 폴더: `assets/characters/<캐릭터 id>/`

| 캐릭터 id | 이름 | 컨셉 |
|---|---|---|
| `nuri` | 누리 | 다정한 후배 비서 (기본 캐릭터), 라일락→민트 웨이브 머리 |
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

- 원본: `reference_sheet.webp` (기본 표정), `reference_expressions.jpg` (표정 6종)
- 표정 7종: `neutral`, `happy`, `thinking`, `surprised`, `sad`, `angry`, `shy`
  - 배경 제거에는 rembg의 `isnet-anime` 모델을 썼습니다.
  - 두 시트의 캐릭터 크기가 달라서, 눈 위치와 눈 사이 거리를 기준으로 크기와 위치를 맞추고 모두 머리부터 가슴까지로 같은 구도로 잘랐습니다.
- 덧그린 프레임
  - 말하는 입: `neutral_talk`, `thinking_talk`, `sad_talk`
  - 눈 감은 모습: `neutral_blink`
  - 입을 이미 벌린 표정(기쁨, 놀람, 부끄럼)은 그 자체로 말하는 것처럼 보이므로 따로 만들지 않았습니다.
- 대답이 끝나고 몇 초가 지나면 기본 표정으로 돌아가, 다시 눈을 깜빡입니다.

원본 해상도가 낮아서(1024×572) 크게 보면 살짝 흐립니다. 같은 구도로 고해상도 시트를 다시 뽑으면 똑같은 방식으로 다시 잘라 넣을 수 있습니다.
