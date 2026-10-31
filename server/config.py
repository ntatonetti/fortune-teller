"""All tunables live here and can be overridden from .env."""

import os
import re
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = Path(os.getenv("ORACLE_ENV_FILE", str(ROOT / ".env")))  # tests point it elsewhere
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


def voices(raw: str) -> list[dict]:
    """VOICES as [{"name", "id"}]: "Name=voice id, Name=voice id"."""
    out = []
    for part in filter(None, (p.strip() for p in raw.split(","))):
        name, _, vid = (x.strip() for x in part.rpartition("="))
        if not name or not re.fullmatch(r"[A-Za-z0-9]{10,40}", vid):
            raise ValueError(f"not Name=voice id: {part!r}")
        out.append({"name": name, "id": vid})
    return out


# The settings that change how she behaves, with what each does, listed (and
# editable) on the start screen under the section set last.
SETTINGS: list[tuple[str, str, object, str]] = []  # (section, env name, value, about)
CASTS: dict[str, type] = {}
# How each is edited there: {"choices": [...]} for a dropdown, {"range": [min,
# max, step]} for a slider (a typed number may go past it), {"kind": ...} else.
CONTROLS: dict[str, dict] = {}
_DEFS: list[tuple[str, str, object, str, type]] = []
_section = "Her"


def _setting(name: str, default, about: str, cast=float, choices=None, span=None, kind=None):
    value = _cast(os.getenv(name, str(default)), cast)
    _DEFS.append((_section, name, default, about, cast))
    SETTINGS.append((_section, name, value, about))
    CASTS[name] = cast
    CONTROLS[name] = {"choices": choices} if choices else {"range": span} if span else {"kind": kind} if kind else {}
    return value


def check(name: str, raw: str) -> None:
    """ValueError unless `raw` is a value the setting can take."""
    value = _cast(raw, CASTS[name])
    choices = CONTROLS[name].get("choices")
    if choices and value not in choices:
        raise ValueError(f"not one of {choices}")


ORACLE_NAME = _setting("ORACLE_NAME", "Madame Mechanika", "her name", str)
BACKGROUND = _setting("BACKGROUND", True, "her room around her; false shows only her face and crystal ball, on black", bool)

# Claude
_section = "Her mind"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Current Claude models that take every effort level.
MODELS = [
    "claude-opus-5-5", "claude-fable-5-1", "claude-sonnet-5-5", "claude-haiku-5-5",
    "claude-fable-5", "claude-opus-5", "claude-sonnet-5", "claude-opus-4-8", "claude-opus-4-7",
]
EFFORTS = ["low", "medium", "high", "xhigh", "max"]
CLAUDE_MODEL = _setting("CLAUDE_MODEL", "claude-opus-5-5", "the Claude model that sees them and writes her words", str, MODELS)
GREET_EFFORT = _setting("GREET_EFFORT", "low", "how hard Claude thinks over the greeting", str, EFFORTS)
FORTUNE_EFFORT = _setting("FORTUNE_EFFORT", "low", "how hard Claude thinks over the fortune", str, EFFORTS)
GREET_TIMEOUT_S = _setting("GREET_TIMEOUT_S", 8, "gives up on the greeting after this", span=[2, 30, 0.5])
FORTUNE_TIMEOUT_S = _setting("FORTUNE_TIMEOUT_S", 20, "gives up on the fortune after this: \"the spirits are silent\"", span=[5, 60, 1])
ASKED_MODEL = _setting("ASKED_MODEL", "claude-haiku-5-5", "judges whether a guest has finished asking", str, MODELS)
ASKED_TIMEOUT_S = _setting("ASKED_TIMEOUT_S", 4, "gives up on that judgement after this", span=[1, 15, 0.5])
CHAT_MODEL = _setting("CHAT_MODEL", "claude-haiku-5-5", "writes the questions she asks them back, mid-reading", str, MODELS)
COIN_MODEL = _setting("COIN_MODEL", "claude-haiku-5-5", "watches the camera for them sitting down (the name is left over from coins: it no longer looks for one)", str, MODELS)

_section = "The conversation"
AUDIENCE = _setting("AUDIENCE", "auto", "who she reads for: auto (she judges each guest from the camera), child or adult (everyone, no guessing)", str, ["auto", "child", "adult"])
STYLE = _setting("STYLE", "auto", "adults, for testing: auto (each reading tarot or conversation at random, from those on), or every reading tarot, or every reading conversation", str, ["auto", "tarot", "conversation"])
FOLLOW_UP = _setting("FOLLOW_UP", True, "adults: after their question, she asks them one back", bool)
TAROT = _setting("TAROT", True, "adults: they stop CARDS tarot cards in her ball, one after another, then she reads them one by one", bool)
CARDS = _setting("CARDS", 3, "adults: how many tarot cards they draw (3: past, present, future)", int, span=[1, 5, 1])

# Voice
_section = "Her voice"
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = _setting("ELEVENLABS_VOICE_ID", "", "the voice she speaks in: press Use this voice on one below", str, kind="voice")
VOICES = _setting("VOICES", "", "the ElevenLabs voices to choose from: add one with its voice ID from elevenlabs.io", voices, kind="voices")
ELEVENLABS_MODEL = _setting(
    "ELEVENLABS_MODEL", "eleven_flash_v2_5", "the ElevenLabs model that voices her (flash is quickest, v4 the most expressive)", str,
    ["eleven_flash_v2_5", "eleven_flash_v2", "eleven_turbo_v2_5", "eleven_turbo_v2",
     "eleven_multilingual_v2", "eleven_v3", "eleven_v4_turbo", "eleven_v4"],
)
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
# Every Claude call, prompts and answers, a file per day; see server/history.py
HISTORY_DIR = Path(os.getenv("HISTORY_DIR", str(ROOT / "data" / "history")))
_section = "Her memory"
MEMORY_RECALL = _setting("MEMORY_RECALL", 15, "how many earlier guests she recalls in a reading", int, span=[0, 50, 1])
MEMORY_MAX_AGE_H = _setting("MEMORY_MAX_AGE_H", 12, "guests older than this many hours are forgotten", span=[1, 48, 1])

_section = "The guest's face in hers"
FLICKER_WHERE = _setting("FLICKER_WHERE", "ball", "where the guest's face flickers up: ball = in her crystal ball, face = over her face", str, ["ball", "face"])
FACE_FLICKERS = _setting("FACE_FLICKERS", 3, "times the guest's face flickers up while she consults (0 = never)", int, span=[0, 10, 1])
FLICKER_OPACITY = _setting("FLICKER_OPACITY", 1, "how solid their face is: 1 = solid, 0.5 = half mist", span=[0, 1, 0.05])
KID_FLICKER = _setting("KID_FLICKER", False, "kids see their own face too", bool)

# Every pause, wait and transition in a reading, in seconds unless noted.
# Sent to the browser as {"wake_hold": 0.7, ...} (the env name, lowercase,
# without _S).
_SECTIONS = {
    "WAKE_HOLD_S": "Sleep and waking",
    "LOOK_SIDE": "Her looks",
    "PAY_TIMEOUT_S": "Paying",
    "QUESTION_MAX_S": "Their question",
    "DRAW_WAIT_S": "Drawing the cards",
    "CONSULT_MIN_S": "Consulting, the fortune, the ticket",
}
_TIMINGS = {
    # sleep and waking
    "WAKE_HOLD_S": (0.7, "a face must stay at the booth this long before she wakes", (0, 5, 0.1)),
    "WAKE_PAUSE_S": (1.9, "after waking she looks at them at least this long before the greeting", (0, 6, 0.1)),
    "DIM_S": (0.9, "her light fading down asleep or coming up awake", (0.1, 3, 0.1)),
    "FALL_ASLEEP_S": (1.6, "after a reading, until she's asleep and can be woken again", (0, 8, 0.1)),
    "REWAKE_GONE_S": (2.5, "the last guest out of sight this long is gone: then even they can wake her again", (0, 15, 0.5)),
    "REWAKE_ANYWAY_S": (30, "the last guest still lingering this long after their reading is greeted again", (5, 180, 5)),
    "SAME_GUEST": (0.6, "how alike (0-1) a face's costume colours must be to the last guest's to count as them, not someone new: lower it if she greets the guest who just left, raise it if she ignores the next one", (0.2, 0.95, 0.05)),
    "PEEK_AFTER_S": (2.5, "someone lingering out of range: her eyes follow them after this", (0, 15, 0.5)),
    "BECKON_AFTER_S": (7, "still lingering: she calls them over after this", (1, 30, 0.5)),
    "BECKON_EVERY_S": (60, "at most one call-over per this", (10, 300, 5)),
    "BLINK_MIN_S": (2.5, "awake, shortest gap between blinks", (0.5, 15, 0.5)),
    "BLINK_MAX_S": (7.5, "longest gap between blinks", (1, 20, 0.5)),
    "BLINK_S": (0.17, "eyes shut per blink", (0.05, 0.6, 0.01)),
    "SLEEP_TALK": (0.2, "share of her sleep, with no one about, spent talking in it (0 = never)", (0, 1, 0.05)),
    "SLEEP_MUMBLE": (0.5, "share of that sleep talk muffled to an unintelligible murmur", (0, 1, 0.05)),
    "WAKE_STARTLE": (0.35, "share of wakings where she snorts awake, dazed (0 = never)", (0, 1, 0.05)),
    "WAKE_DAZED_S": (1.6, "how long she looks around, dazed, after a startled waking", (0, 5, 0.1)),
    # her looks
    "LOOK_SIDE": (0.35, "how far off-centre her gaze must be (0-1) before her eyes turn to look that way", (0.05, 1, 0.05)),
    "MOUTH_OPEN": (3, "her widest mouth: 1 parted, 2 half dropped, 3 dropped to her teeth", (1, 3, 1)),
    "GLANCE_MIN_S": (5, "awake, shortest gap between her glances away (left, right, up or down)", (1, 60, 1)),
    "GLANCE_MAX_S": (14, "longest gap between glances away", (1, 90, 1)),
    "GLANCE_S": (0.9, "how long a glance away holds (0 = she never glances away)", (0, 3, 0.1)),
    # paying
    "SIT_WAIT_S": (20, "standing guests: once she asks them to sit, how long she waits for it (looking every COIN_LOOK_EVERY_S) before going on anyway", (0, 60, 1)),
    "PAY_TIMEOUT_S": (40, "no secret (or spooky sound from a kid) by then: she goes back to sleep", (5, 120, 5)),
    "SECRET_LISTEN_S": (12, "each stretch of listening for a whispered secret, or a kid's spooky sound", (3, 30, 1)),
    "COIN_LOOK_EVERY_S": (1.5, "waiting for them to sit, how often she looks (the name is left over from coins; it's only the sit check now. 0 = never: she waits all of SIT_WAIT_S unless she sees their face drop)", (0, 5, 0.25)),
    "COIN_PAUSE_S": (0.8, "after the button is pressed, before she asks their question", (0, 3, 0.1)),
    # their question
    "QUESTION_MAX_S": (30, "longest she listens to a question", (5, 60, 1)),
    "QUESTION_START_S": (10, "gives up if an adult hasn't started talking by then", (2, 30, 1)),
    "QUESTION_START_KID_S": (12, "gives up if a kid hasn't started talking by then", (2, 30, 1)),
    "QUESTION_PAUSE_S": (2.2, "a pause this long ends an adult's question", (0.5, 6, 0.1)),
    "QUESTION_PAUSE_KID_S": (3, "a pause this long ends a kid's question", (0.5, 8, 0.1)),
    "QUESTION_TRAILING_S": (2.5, "added to the pause if they trailed off (\"will I...\")", (0, 6, 0.1)),
    "QUESTION_MORE_S": (6, "added if Claude says the question isn't finished", (0, 15, 0.5)),
    "HEARD_SHOW_S": (0.6, "their question stays on screen this long before she answers", (0, 3, 0.1)),
    # drawing the cards
    "DRAW_WAIT_S": (12, "nobody says stop by then: the card showing is theirs", (2, 40, 1)),
    "CARD_SHUFFLE_S": (0.42, "each card shows this long as they shuffle through her ball", (0.1, 2, 0.02)),
    "CARD_HOLD_S": (0.8, "a chosen card stays in the ball this long before the next shuffles", (0, 4, 0.1)),
    # consulting, the fortune, the ticket
    "CONSULT_MIN_S": (3.5, "shortest consult, even if the fortune comes back sooner", (0, 15, 0.5)),
    "GLIMPSE_MIN_S": (0.33, "shortest glimpse of their face", (0.05, 2, 0.01)),
    "GLIMPSE_MAX_S": (0.58, "longest glimpse of their face", (0.05, 2, 0.01)),
    "GLIMPSE_GAP_MIN_S": (0.42, "shortest gap between glimpses", (0.05, 3, 0.01)),
    "GLIMPSE_GAP_MAX_S": (0.83, "longest gap between glimpses", (0.05, 3, 0.01)),
    "GLITCH_S": (1.3, "her mid-fortune seizure: voice stops, head shakes, their face stutters", (0, 4, 0.1)),
    "GLITCH_AT_MIN": (0.3, "earliest the seizure comes (fraction of the fortune)", (0, 1, 0.05)),
    "GLITCH_AT_MAX": (0.55, "latest the seizure comes (fraction of the fortune)", (0, 1, 0.05)),
    "SHUTDOWN_GLITCH_S": (0.5, "the shudder when a guest walks away mid-reading", (0, 3, 0.1)),
    "TICKET_PAUSE_S": (1.3, "the ticket printing, before her farewell", (0, 6, 0.1)),
    "SUBTITLE_LINGER_S": (0.7, "subtitles stay up this long after she stops talking", (0, 4, 0.1)),
    "NO_VOICE_WORD_S": (0.4, "per word, if a voice clip fails and only subtitles show", (0.1, 1.5, 0.05)),
}
TIMINGS = {}
for _k, (_v, _about, _span) in _TIMINGS.items():
    _section = _SECTIONS.get(_k, _section)
    TIMINGS[_k.removesuffix("_S").lower()] = _setting(_k, _v, _about, span=list(_span))

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
