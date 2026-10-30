"""All tunables live here and can be overridden from .env."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


ORACLE_NAME = os.getenv("ORACLE_NAME", "Madame Mechanika")

# Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
GREET_EFFORT = os.getenv("GREET_EFFORT", "low")
FORTUNE_EFFORT = os.getenv("FORTUNE_EFFORT", "low")
# Past these she gives up on the call: no greeting, or "the spirits are silent".
GREET_TIMEOUT_S = float(os.getenv("GREET_TIMEOUT_S", "8"))
FORTUNE_TIMEOUT_S = float(os.getenv("FORTUNE_TIMEOUT_S", "20"))
# The quick "have they finished asking?" check at each pause in their question.
ASKED_MODEL = os.getenv("ASKED_MODEL", "claude-haiku-5-5")
ASKED_TIMEOUT_S = float(os.getenv("ASKED_TIMEOUT_S", "4"))

# Voice
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5")
ELEVENLABS_CONCURRENCY = int(os.getenv("ELEVENLABS_CONCURRENCY", "2"))  # max requests at once

# Printer: "none", "console" (prints the card to the terminal), or "usb"
PRINTER = os.getenv("PRINTER", "console")
PRINTER_USB_VENDOR = int(os.getenv("PRINTER_USB_VENDOR", "0") or "0", 16)
PRINTER_USB_PRODUCT = int(os.getenv("PRINTER_USB_PRODUCT", "0") or "0", 16)
PRINTER_WIDTH_CHARS = int(os.getenv("PRINTER_WIDTH_CHARS", "32"))  # 32 for 58mm, 48 for 80mm
# Bulk endpoints; the 0x0416:0x5011 "POS80" boards (NetumScan NS8360 etc.) use 0x01 out, 0x81 in
PRINTER_USB_OUT_EP = int(os.getenv("PRINTER_USB_OUT_EP", "0x01"), 16)
PRINTER_USB_IN_EP = int(os.getenv("PRINTER_USB_IN_EP", "0x81"), 16)

# Party memory: text descriptions of costumes only, never images
MEMORY_FILE = Path(os.getenv("MEMORY_FILE", str(ROOT / "data" / "guests.json")))
MEMORY_RECALL = int(os.getenv("MEMORY_RECALL", "15"))
MEMORY_MAX_AGE_H = float(os.getenv("MEMORY_MAX_AGE_H", "12"))  # older guests are forgotten

# Glimpses of the guest's face over hers while she consults; 0 turns it off
FACE_FLICKERS = int(os.getenv("FACE_FLICKERS", "3"))
FLICKER_OPACITY = float(os.getenv("FLICKER_OPACITY", "0.8"))  # 1 = their face only, 0.5 = half each
KID_FLICKER = _bool("KID_FLICKER", False)  # kids see their own face in hers too

# Every pause, wait and transition in a reading, in seconds unless noted; each
# is listed with what it does in .env.example. Sent to the browser as
# {"wake_hold": 0.7, ...} (the env name, lowercase, without _S).
_TIMINGS = {
    # sleep and waking
    "WAKE_HOLD_S": 0.7,
    "WAKE_PAUSE_S": 1.9,
    "HEAD_MOVE_S": 0.9,
    "FALL_ASLEEP_S": 1.6,
    "REWAKE_GONE_S": 2.5,
    "REWAKE_ANYWAY_S": 30,
    "PEEK_AFTER_S": 2.5,
    "BECKON_AFTER_S": 7,
    "BECKON_EVERY_S": 60,
    "TWITCH_MIN_S": 9,
    "TWITCH_MAX_S": 25,
    "TWITCH_HOLD_S": 0.9,
    "BLINK_MIN_S": 2.5,
    "BLINK_MAX_S": 7.5,
    "BLINK_S": 0.17,
    # paying
    "PAY_TIMEOUT_S": 40,
    "SECRET_LISTEN_S": 12,
    "COIN_PAUSE_S": 0.8,
    # their question
    "QUESTION_MAX_S": 30,
    "QUESTION_START_S": 10,
    "QUESTION_START_KID_S": 12,
    "QUESTION_PAUSE_S": 2.2,
    "QUESTION_PAUSE_KID_S": 3,
    "QUESTION_TRAILING_S": 2.5,
    "QUESTION_MORE_S": 6,
    "HEARD_SHOW_S": 0.6,
    # consulting, the fortune, the ticket
    "CONSULT_MIN_S": 3.5,
    "GLIMPSE_MIN_S": 0.33,
    "GLIMPSE_MAX_S": 0.58,
    "GLIMPSE_GAP_MIN_S": 0.42,
    "GLIMPSE_GAP_MAX_S": 0.83,
    "GLITCH_S": 1.3,
    "GLITCH_AT_MIN": 0.3,  # fraction of the way through the fortune
    "GLITCH_AT_MAX": 0.55,
    "SHUTDOWN_GLITCH_S": 0.5,
    "TICKET_PAUSE_S": 1.3,
    "SUBTITLE_LINGER_S": 0.7,
    "NO_VOICE_WORD_S": 0.4,
}
TIMINGS = {k.removesuffix("_S").lower(): float(os.getenv(k, str(v))) for k, v in _TIMINGS.items()}

CACHE_DIR = ROOT / "data" / "tts_cache"
SFX_DIR = ROOT / "static" / "sfx"  # committed; regenerate with scripts/make_sfx.py
