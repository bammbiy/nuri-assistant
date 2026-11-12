# Nuri Assistant

English | [한국어](README.ko.md)

The app itself speaks Korean: menus, speech bubbles and character lines are Korean, and the optional voice is Japanese.

## Desktop character assistant

On Windows, double-click `start_nuri.bat` or run `python src/run_nuri.py`. An anime-style character stays on top at the bottom right of your desktop, just above the taskbar. Drag it to move it and the position is remembered (a second monitor works too). Hover over the character and a chat window appears right below it. Move the mouse away and it disappears after a moment. When you talk in the chat window, an AI running on your own PC (Ollama) answers in the character's voice. Your conversations never go out to the internet.

- When you start the app, the assistant selection screen comes first. If you check "다음부터 이 화면 없이 바로 시작" (start directly without this screen next time), it starts with the last assistant right away, and you can change it any time from `비서 선택…` (choose assistant) in the menu.
- 8 assistants:
  - **Nuri**: a kind junior assistant who calls the user 'senpai'. The default character
  - **Sera**: a mature older-sister assistant who calls the user 'little brother/sister'
  - **Yuki**: a soft-spoken, soothing assistant who calls the user 'darling'
  - Akane (tsundere), Shizuku (kuudere), Hinata (white gyaru childhood friend), Sakura (maid), Reika (ojou-sama)
- The expression changes with the content of the reply (neutral, smile, thinking, surprised, sad, angry, shy). The mouth moves while she talks, and she blinks now and then.
- If an error occurs while running, a dialog appears and the details are written to `~/.nuri-assistant/error.log`. If the app does not start, check this file.
- Conversations are saved per character in `~/.nuri-assistant/companion.sqlite3`, and she continues the talk remembering recent conversations.
- Turn on `전신으로 보기` (show full body) in the menu to see the full body instead of the upper body (all 8 characters). Expressions, mouth movement, and blinking work the same in full body, and the window grows upward while keeping the feet in place.
- Drag the character to move it. Click it and it reacts, and you can type into the chat window right away. The position is saved.
- Open the menu with a right click or the `⋯` button on the left of the chat window: choose assistant, show full body, set my name, AI model settings, view schedule, today's schedule briefing, to-dos, focus timer, lowest price alerts, price alert settings, voice settings, view chat history, clear memory, file renaming tool, file/shopping assistant, quit
- All 8 are shown as illustrations (a temporary character drawn with shapes is used if there is no image file). You can see past conversations from `대화 기록 보기` (view chat history) in the right-click or `⋯` menu. How to add images and the AI generation prompts are in [assets/characters/README.md](assets/characters/README.md).
- **Schedule management**: manage it by talking, for example "내일 오후 3시에 치과 잡아줘" (book the dentist tomorrow at 3 PM), "이번 주 일정 알려줘" (tell me this week's schedule), "내일 회의 취소해" (cancel tomorrow's meeting).
  - Adding and cancelling take effect only after you press `등록` (register) or `취소` (cancel) on the confirmation card that appears below the character, or type "응" (yes) or "아니" (no).
  - The AI does not calculate dates and times. The app interprets Korean expressions itself ("다음 주 화요일 10시" next Tuesday at 10, "세 시 반" half past three, "30분 뒤" in 30 minutes, "10월 20일" October 20). If you do not say AM or PM, 1 to 6 o'clock is taken as PM.
  - The character tells you 10 minutes before an event (9 AM that day for all-day events). You can change the notice time, for example "30분 전에 알려줘" (tell me 30 minutes before).
  - The first time you start it each day, it briefs you on today's schedule. In `일정 보기` (view schedule) in the menu you can see the list and delete items.
  - The schedule feature needs a model that supports tool calling. The default model `qwen3:8b` supports it. If you choose a model that does not, only chat works.
- **Lowest price alerts**: say things like "에어팟 프로 30만원 아래로 떨어지면 알려줘" (tell me if AirPods Pro drops below 300,000 won) or "로지텍 마우스 최저가 얼마야?" (what is the lowest price of the Logitech mouse?).
  - Prices are fetched only from free sources: the Naver Shopping search API (free for anyone to get, 25,000 calls per day, lowest prices from the many stores listed on Naver Shopping). You can also watch by product link (no key needed), but sites that block automated lookups, such as Coupang, must be watched by product name.
  - In `가격 알림 설정…` (price alert settings) in the menu, enter the Naver API key and the check interval (default 60 minutes). The key is saved only in `~/.nuri-assistant/companion.json`.
  - The character tells you when the price falls to the target price or below (or, if there is no target price, when the lowest price drops to a new low), and clicking the speech bubble opens the product page.
  - In the `최저가 알림` (lowest price alerts) window in the menu you can add and delete items directly without the AI, and see the current price and the lowest price so far.
- **To-dos**: if you say "보고서 금요일까지 해야 해" (I have to finish the report by Friday), it is added after a confirmation card. If you say "보고서 끝냈어" (I finished the report), a completion card appears.
  - The character nags you at 7 PM the evening before the deadline and at 9 AM on the day. Overdue to-dos appear in the morning briefing.
  - In the `할 일` (to-dos) window in the menu you can add items directly, click the circle to complete them, and see the D-day.
- **Focus timer**: say "25분 집중 모드" (25-minute focus mode) or "50분 집중 10분 휴식 2번" (50 minutes focus, 10 minutes rest, twice), or press `집중 타이머 시작` (start focus timer) in the menu. A badge with the remaining time appears next to the character (click it to stop), and the character tells you each time a focus or rest period ends.
- **Japanese voice**: the speech bubble is in Korean, and the voice is a Japanese anime voice.
  - Install and run the free voice engine [VOICEVOX](https://voicevox.hiroshiba.jp/), then turn on `음성으로 말하기` (speak with voice) in `음성 설정…` (voice settings) in the menu. AivisSpeech, which works the same way, can also be used.
  - For AI replies, the AI writes a Japanese line along with the reply (`<ja>…</ja>`, not shown in the speech bubble) and it is read as is. For lines the app makes itself (reminders, briefings, and so on), the local AI translates them into Japanese and reads them.
  - Each character has a default voice that suits her (for example Akane = 四国めたん ツンツン), and you can change it and preview it in the voice settings.
  - When using VOICEVOX character voices in public content, you must follow each character's terms of use, such as the 'VOICEVOX:character name' credit.
- **Daily life notices** (menu `생활 알림 설정…`, life notice settings): at a set time (or when the app starts), a morning briefing with weather, umbrella, and clothing advice (if you enter a city, using a free weather service that needs no key), and in the evening a daily wrap-up of "focus sessions today, things finished, tomorrow's first event" (any time from `오늘 하루 정리` (today's wrap-up) in the menu). On Windows, she welcomes you back when you return after being away for more than 30 minutes, suggests a break when you have been sitting a long time, and says to drink water at the interval you set (she only looks at the time you last used the keyboard or mouse and does not read what you type, and she holds off during a focus timer).
- **Closeness and memory notebook**: the more you talk and finish to-dos and focus sessions, the closer you become to the character (first meeting, friendly, close, best friends; menu `우리 사이` (our relationship)), and she says special lines when you reach a new stage. If you say something like "나 고양이 알레르기 있어" (I'm allergic to cats), she asks on a confirmation card whether she may remember it, and she brings up what you approved naturally in conversation (see and delete in the menu `기억 수첩` (memory notebook)).
- **Copied text and download helper** (off by default): when you copy text that contains a date, a schedule card appears, and when you copy a shopping link, a price alert card appears (in the life notice settings). When unsorted files pile up in the Downloads folder, it shows a cleanup preview once a day (in the file renaming settings). Copied text is not saved, and for downloads only the file names are looked at.
- **Fun**: "오늘 운세 봐줘" (tell my fortune today), "가위바위보 하자, 바위!" (let's play rock-paper-scissors, rock! The app decides the result and the character delivers it in her voice), and the menu `오늘의 운세` (today's fortune). She also congratulates you on your birthday (if you enter it in the life notice settings) and on days like 100 days or 1 year since you first met.
- **Awareness and reactions**: if you leave her idle, she sometimes talks to herself (many, normal, few, or off in the life notice settings, with greetings, level-ups, and anniversaries switchable separately), and she reacts when you pet her head with the mouse or click many times. When a game or video is full screen, she does not come to the top and waits quietly. When you start it for the first time, she tells you what leaves your PC and what is not looked at (menu `개인정보 안내`, privacy notice).
- **Faster voice and small pleasures**: she does not wait for the reply to finish and speaks the Japanese voice one sentence at a time right away. If you want, she tells you the time on the hour (in the life notice settings), and she says a few words on days like Lunar New Year, Chuseok, and Christmas, and on the first day of each season.
- **Light mode and auto start**: on a slow PC, use `가벼운 모드` (light mode) in the AI settings (voice off, less motion, a smaller model suggested). With the menu `윈도우 시작할 때 켜기` (start when Windows starts), the assistant appears as soon as you turn on the PC (turning it off removes it cleanly).
- **More convenient menus**: `집중 타이머…` (focus timer: time, break time, repeats, stop), `AI 설정…` (AI settings: model, Ollama address, how long the chat memory is), adding directly in the schedule window, and a price change graph in the lowest price window.
- **File renaming**: if you say something like "다운로드 폴더 20260715 ja00 3페이지부터 이름 정리해줘" (rename the files in the Downloads folder starting from page 3 of 20260715 ja00), it shows a preview of renaming document and image files to the `20260715_ja00_003.pdf` pattern, and the names change only after you press `정리` (organize) on the confirmation card. Press `목록` (list) on the card to see all the files that will change (original name to new name, and files that collide) in a window, where you can organize or cancel right away. With "방금 거 되돌려줘" (undo the last one) you can restore the last renaming (also after confirmation). The folder can be Downloads, Desktop, Documents, Pictures, or a full path, up to 300 files at a time. In `파일 정리 설정…` (file renaming settings) in the menu you can set the name format (`{날짜}_{매체}_{페이지}`, `{연도}-{월}-{일}_{페이지}`, and so on, put together by clicking the boxes, with an example shown right away), the default media code to use when you do not say one, the file types to organize, and whether to skip files that are already organized and continue the numbering.
- Development guides are in [CLAUDE.md](CLAUDE.md) (Korean), and the development log is in [HISTORY.md](HISTORY.md) (Korean).

### Running without Python (Windows exe)

On the GitHub repository's Actions tab, open the most recent `tests` run, download `NuriAssistant-windows` from Artifacts, unzip it, and run `NuriAssistant.exe`. Python is included, so you do not need to install it separately. Prepare Ollama (and VOICEVOX if you want voice) separately as described below. Because this is an unsigned program, if Windows shows a warning on the first run, click "추가 정보" (More info) and then choose "실행" (Run anyway). To build it yourself, run `pip install pyinstaller pillow` and then `python tools/build_exe.py`.

If your display scaling is 125% or 150% and the character looks blurry, right-click the character, turn on "선명하게 보기 (고배율 화면)" (sharp view, high-scaling displays), and restart the app. It becomes clear but looks a little smaller.

### Setting up Ollama (once, the first time)

1. Install Ollama for Windows from https://ollama.com. After installing, it runs automatically in the background.
2. Download the model in a terminal. The default model is `qwen3:8b`, chosen for the RTX 3060 Ti (8GB VRAM).

```powershell
ollama pull qwen3:8b
```

3. (Recommended) Install Pillow so character images are scaled down smoothly. It runs without it.

```powershell
pip install pillow
```

4. Run the app.

```powershell
python src/run_nuri.py           # character assistant
python src/run_nuri.py --classic # file renaming tool only, without the character
```

To use another model, change the name in `AI 모델 설정` (AI model settings) in the menu. For example, `exaone3.5:7.8b`, which is strong in Korean, also fits in 8GB VRAM. Settings are saved in `~/.nuri-assistant/companion.json`.

## File renaming tool (earlier feature)

This is the document file name batch renaming tool that existed before the character assistant. Open it from `파일 정리 도구` (file renaming tool) in the menu or with `python src/run_nuri.py --classic`.

When you add files, it shows the planned new file names based on the date, media code, and page number, checks for conflicts, and then runs a batch rename. The change history is saved in SQLite (`~/.nuri-assistant/history.sqlite3`), and the last batch can be undone.

The `파일/구매 비서` (file/shopping assistant) window in the menu has two tabs. The file assistant picks out the organizing conditions from a sentence like "20260715 ja00 1부터 하위 폴더까지 정리해줘" (organize from 20260715 ja00 page 1, including subfolders) and shows a preview (it runs only after confirmation). The shopping assistant compares the candidate products you enter by price, rating, number of reviews, and warranty period, and adds web research if there is an OpenAI API key (`OPENAI_API_KEY` or typed into the window, not saved to a file). This part has an English screen and uses an external API, not the local AI.

## Key features

- Select multiple PDFs and ordinary files
- Folder scan and scan including subfolders
- Create file names based on `{DATE}_{MEDIA}_{PAGE}`
- Presets of file name rules for real work
- Save and load work profiles
- Automatic inference of date, media code, and page number
- Preview of planned file names
- Preview filters by search term and status
- Remove selected items from the list
- Color display by status
- Save the preview result as CSV
- Detect target file name conflicts and duplicates within a batch
- SQLite-based rename history
- Undo the whole last batch
- Tkinter GUI that runs without external packages

## File name rules

The default rule is as follows.

```text
{DATE}_{MEDIA}_{PAGE}
```

Example:

```text
20260628_ja00_001.pdf
```

You can change it in the rule input box like this:

```text
{MEDIA}-{DATE}-{PAGE}
```

Result:

```text
ja00-20260628-001.pdf
```

Supported tokens:

- `{DATE}`: `YYYYMMDD`
- `{MEDIA}`: 2 letters + 2 digits, for example `ja00`
- `{PAGE}`: 3-digit page number, for example `001`

## Working flow

1. Add the targets with `파일 추가` (add files) or `폴더 불러오기` (load folder).
2. If needed, turn on `하위폴더 포함` (include subfolders) and load the folder again.
3. Check the date, media code, and start page.
4. Decide the file name rule with a preset or by typing it.
5. For repeated work, save the current settings with `작업 프로필` (work profile).
6. In `미리보기` (preview), review the `ready`, `conflict`, and `error` states.
7. Use the search term or status filter to check only specific files and problem items.
8. For files to exclude, select them and press `선택 제거` (remove selected).
9. If approval or sharing is needed, save the planned change list with `CSV 저장` (save CSV).
10. If there are no problems, press `변경 실행` (run changes).
11. If you made a mistake, undo the last group of work with `마지막 배치 취소` (cancel last batch).

## Work profiles

You can save frequently used work conditions as a profile. A profile includes these settings:

- Date
- Media code
- Start page
- File name rule
- Whether to include subfolders

Profile files are saved in `.nuri-assistant/profiles.json` in the user's home folder.

## Development

Python 3.10 or later (3.11 recommended). The app needs no external packages to run. From the repository root:

```bash
python src/run_nuri.py                    # character assistant
python src/run_nuri.py --classic          # file renaming tool only
python -m unittest discover -s tests      # unit tests (run without tkinter)
pip install -e .                          # optional: after installing, run anywhere as nuri-assistant / python -m nuri_assistant
```

Design principles and ways of working are in [CLAUDE.md](CLAUDE.md), the folder structure and code conventions are in [docs/RULES.md](docs/RULES.md) (Korean), the remaining work is in [docs/TODO.md](docs/TODO.md) (Korean), and the log of work so far is in [HISTORY.md](HISTORY.md).
