"""All tunables live here and can be overridden from .env."""

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
_SHELL = dict(os.environ)  # set in the shell: beats .env, as load_dotenv does
load_dotenv(ENV_FILE)


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _cast(raw: str, cast):
    """A setting's text as its type; ValueError if it isn't one."""
    if cast is bool:
        if raw.strip().lower() not in ("1", "true", "yes", "on", "0", "false", "no", "off"):
            raise ValueError(f"not true/false: {raw!r}")
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return cast(raw)


# The settings that change how she behaves, with what each does, listed (and
# editable) on the start screen under the section set last.
SETTINGS: list[tuple[str, str, object, str]] = []  # (section, env name, value, about)
CASTS: dict[str, type] = {}
_DEFS: list[tuple[str, str, object, str, type]] = []
_section = "Her"


def _setting(name: str, default, about: str, cast=float):
    value = _cast(os.getenv(name, str(default)), cast)
    _DEFS.append((_section, name, default, about, cast))
    SETTINGS.append((_section, name, value, about))
    CASTS[name] = cast
    return value


ORACLE_NAME = _setting("ORACLE_NAME", "Madame Mechanika", "her name", str)

# Claude
_section = "Her mind"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = _setting("CLAUDE_MODEL", "claude-opus-5-5", "the Claude model that sees them and writes her words", str)
GREET_EFFORT = _setting("GREET_EFFORT", "low", "how hard Claude thinks over the greeting", str)
FORTUNE_EFFORT = _setting("FORTUNE_EFFORT", "low", "how hard Claude thinks over the fortune", str)
GREET_TIMEOUT_S = _setting("GREET_TIMEOUT_S", 8, "gives up on the greeting after this")
FORTUNE_TIMEOUT_S = _setting("FORTUNE_TIMEOUT_S", 20, "gives up on the fortune after this: \"the spirits are silent\"")
ASKED_MODEL = _setting("ASKED_MODEL", "claude-haiku-5-5", "judges whether a guest has finished asking", str)
ASKED_TIMEOUT_S = _setting("ASKED_TIMEOUT_S", 4, "gives up on that judgement after this")

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
_section = "Her memory"
MEMORY_RECALL = _setting("MEMORY_RECALL", 15, "how many earlier guests she recalls in a reading", int)
MEMORY_MAX_AGE_H = _setting("MEMORY_MAX_AGE_H", 12, "guests older than this many hours are forgotten")

_section = "The guest's face in hers"
FACE_FLICKERS = _setting("FACE_FLICKERS", 3, "times the guest's face flickers over hers while she consults (0 = never)", int)
FLICKER_OPACITY = _setting("FLICKER_OPACITY", 1, "how solid their face is over hers: 1 = their face only, 0.5 = half each")
KID_FLICKER = _setting("KID_FLICKER", False, "kids see their own face in hers too", bool)

# Every pause, wait and transition in a reading, in seconds unless noted.
# Sent to the browser as {"wake_hold": 0.7, ...} (the env name, lowercase,
# without _S).
_SECTIONS = {
    "WAKE_HOLD_S": "Sleep and waking",
    "PAY_TIMEOUT_S": "Paying",
    "QUESTION_MAX_S": "Their question",
    "CONSULT_MIN_S": "Consulting, the fortune, the ticket",
}
_TIMINGS = {
    # sleep and waking
    "WAKE_HOLD_S": (0.7, "a face must stay at the booth this long before she wakes"),
    "WAKE_PAUSE_S": (1.9, "after waking she looks at them at least this long before the greeting"),
    "HEAD_MOVE_S": (0.9, "her head dropping asleep or lifting awake"),
    "FALL_ASLEEP_S": (1.6, "after a reading, until she's asleep and can be woken again"),
    "REWAKE_GONE_S": (2.5, "the last guest must be gone this long before she wakes again"),
    "REWAKE_ANYWAY_S": (30, "...or this long since she fell asleep"),
    "PEEK_AFTER_S": (2.5, "someone lingering out of range: one eye opens after this"),
    "BECKON_AFTER_S": (7, "still lingering: she calls them over after this"),
    "BECKON_EVERY_S": (60, "at most one call-over per this"),
    "TWITCH_MIN_S": (9, "earliest twitch in her sleep"),
    "TWITCH_MAX_S": (25, "latest twitch"),
    "TWITCH_HOLD_S": (0.9, "how long a twitch holds her head tilted"),
    "BLINK_MIN_S": (2.5, "awake, shortest gap between blinks"),
    "BLINK_MAX_S": (7.5, "longest gap between blinks"),
    "BLINK_S": (0.17, "eyes shut per blink"),
    "SLEEP_TALK": (0.2, "share of her sleep, with no one about, spent talking in it (0 = never)"),
    "SLEEP_MUMBLE": (0.5, "share of that sleep talk muffled to an unintelligible murmur"),
    "WAKE_STARTLE": (0.35, "share of wakings where she snorts awake, dazed (0 = never)"),
    "WAKE_DAZED_S": (1.6, "how long she looks around, dazed, after a startled waking"),
    # paying
    "PAY_TIMEOUT_S": (40, "no coin or secret by then: she goes back to sleep"),
    "SECRET_LISTEN_S": (12, "each stretch of listening for a whispered secret"),
    "COIN_PAUSE_S": (0.8, "after the coin drops, before she asks their question"),
    # their question
    "QUESTION_MAX_S": (30, "longest she listens to a question"),
    "QUESTION_START_S": (10, "gives up if an adult hasn't started talking by then"),
    "QUESTION_START_KID_S": (12, "gives up if a kid hasn't started talking by then"),
    "QUESTION_PAUSE_S": (2.2, "a pause this long ends an adult's question"),
    "QUESTION_PAUSE_KID_S": (3, "a pause this long ends a kid's question"),
    "QUESTION_TRAILING_S": (2.5, "added to the pause if they trailed off (\"will I...\")"),
    "QUESTION_MORE_S": (6, "added if Claude says the question isn't finished"),
    "HEARD_SHOW_S": (0.6, "their question stays on screen this long before she answers"),
    # consulting, the fortune, the ticket
    "CONSULT_MIN_S": (3.5, "shortest consult, even if the fortune comes back sooner"),
    "GLIMPSE_MIN_S": (0.33, "shortest glimpse of their face"),
    "GLIMPSE_MAX_S": (0.58, "longest glimpse of their face"),
    "GLIMPSE_GAP_MIN_S": (0.42, "shortest gap between glimpses"),
    "GLIMPSE_GAP_MAX_S": (0.83, "longest gap between glimpses"),
    "GLITCH_S": (1.3, "her mid-fortune seizure: voice stops, head shakes, their face stutters"),
    "GLITCH_AT_MIN": (0.3, "earliest the seizure comes (fraction of the fortune)"),
    "GLITCH_AT_MAX": (0.55, "latest the seizure comes (fraction of the fortune)"),
    "SHUTDOWN_GLITCH_S": (0.5, "the shudder when a guest walks away mid-reading"),
    "TICKET_PAUSE_S": (1.3, "the ticket printing, before her farewell"),
    "SUBTITLE_LINGER_S": (0.7, "subtitles stay up this long after she stops talking"),
    "NO_VOICE_WORD_S": (0.4, "per word, if a voice clip fails and only subtitles show"),
}
TIMINGS = {}
for _k, (_v, _about) in _TIMINGS.items():
    _section = _SECTIONS.get(_k, _section)
    TIMINGS[_k.removesuffix("_S").lower()] = _setting(_k, _v, _about)

CACHE_DIR = ROOT / "data" / "tts_cache"
SFX_DIR = ROOT / "static" / "sfx"  # committed; regenerate with scripts/make_sfx.py


def reload() -> None:
    """Re-read .env, so changes made since the server started take effect."""
    env = {**dotenv_values(ENV_FILE), **_SHELL}
    SETTINGS.clear()
    for section, name, default, about, cast in _DEFS:
        raw = env.get(name)
        value = _cast(raw if raw is not None else str(default), cast)
        SETTINGS.append((section, name, value, about))
        if name in _TIMINGS:
            TIMINGS[name.removesuffix("_S").lower()] = value
        else:
            globals()[name] = value
