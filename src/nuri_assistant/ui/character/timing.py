"""Window sizes and timings of the character window (ms unless noted).

Shared by ``mascot.py`` and its mixins so they need not import each other.
"""

from __future__ import annotations

from datetime import timedelta

from .chatbox import HEIGHT as CHAT_HEIGHT
from .placeholder import PLACEHOLDER_HEIGHT


# Character frames are 405px wide and CHAR_BOX is WIDTH - 10, so they show 1:1 with no
# runtime resampling (which is what made the art look soft, especially without Pillow).
WIDTH = 415
CANVAS_HEIGHT = 560
# The chat box appears right under the character, in the strip below CHAR_BOTTOM.
CHAR_BOTTOM = CANVAS_HEIGHT - CHAT_HEIGHT - 18
CHAR_TOP = CHAR_BOTTOM - PLACEHOLDER_HEIGHT
# Images may rise behind the bubble area so a bust-up drawing is shown large.
CHAR_BOX = (WIDTH - 10, CHAR_BOTTOM - 120)
# Full-body frames are 480px tall vs 344px for the bust; the window grows by this much.
FULL_EXTRA = 150
# Timings (ms unless noted); together they set how lively the character feels.
EVENT_POLL_MS = 50
POINTER_POLL_MS = 120
CHAT_HIDE_DELAY_MS = 1200
FIRST_REMINDER_CHECK_MS = 5000
REMINDER_POLL_MS = 20_000
TIMER_TICK_MS = 1000
FIRST_PRICE_CHECK_MS = 30_000
MIN_PRICE_CHECK_MINUTES = 10
PRICE_ALERT_GAP_MS = 9000
BRIEFING_DELAY_MS = 4500
PRESENCE_POLL_MS = 30_000  # idle time is checked this often (Windows only)
ROUTINE_POLL_MS = 30_000   # scheduled briefing / evening wrap-up check
SECOND_LINE_GAP_MS = 9000  # when two presence lines are due at once
LEVEL_UP_DELAY_MS = 2500   # a closeness level-up line follows the reply it came from
MIN_FOCUS_FOR_POINTS = 10  # shorter focus blocks earn no closeness points
MAX_FACTS = 30             # newest remembered facts put into the system prompt
ROUTINE_GAP_S = 60         # a special-day line waits this long after a briefing or wrap-up
DOWNLOADS_POLL_MS = 600_000  # opt-in Downloads check (file names only)
CLIPBOARD_POLL_MS = 2000     # opt-in clipboard check (text is never stored)
CLIPBOARD_GAP_S = 60         # at most one clipboard suggestion a minute
CHATTER_POLL_MS = 30_000     # idle talk / idle glance check
GLANCE_GAP_S = (180, 420)    # now and then a quiet change of face, no words
GLANCE_MS = 2500
HEAD_SHARE = 0.35            # top part of the character counted as the head (pats)
PRIVACY_DELAY_MS = 2500      # first start: privacy notice after the greeting
DAY_WORDS_ONLY = {"오늘", "내일", "모레", "글피", "내일모레"}  # a bare day word is not an appointment
WRAPUP_WINDOW = timedelta(hours=3)  # an app started later than this after the wrap-up time skips it
FIRST_BLINK_MS = 3500
BLINK_MS = 140
BLINK_GAP_MS = (2500, 6000)
LIGHT_SLOWDOWN = 2         # light mode: blink half as often, no idle glances
LIGHT_HISTORY = 10         # light mode: at most this many past messages go to the model
MOUTH_FLAP_MS = 130
# The face relaxes to neutral after a base delay plus a little per character of text.
RELAX_BASE_MS = 6000
RELAX_PER_CHAR_MS = 60
RELAX_MAX_EXTRA_MS = 9000
RELAX_RETRY_MS = 2000
# Notices that arrived while the picker was open are replayed after picking.
HELD_NOTICE_DELAY_MS = 3500
HELD_NOTICE_GAP_MS = 4000
# Pointer travel (px) before a press on the character counts as a drag, not a poke.
DRAG_THRESHOLD_PX = 4
CHAT_GAP = 3  # px between the character's bottom and the chat box
KEEP_ON_TOP_MS = 3000  # re-assert topmost / on-screen
# Windows keys this exact color out of the window. A near-black key keeps
# anti-aliased PNG edges looking like line art instead of a colored halo.
TRANSPARENT_KEY = "#010203"
FALLBACK_BG = "#f3eff7"
