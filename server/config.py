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
# Past these, she uses a canned line rather than keep a guest waiting.
GREET_TIMEOUT_S = float(os.getenv("GREET_TIMEOUT_S", "8"))
FORTUNE_TIMEOUT_S = float(os.getenv("FORTUNE_TIMEOUT_S", "20"))

# Voice
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5")
ELEVENLABS_CONCURRENCY = int(os.getenv("ELEVENLABS_CONCURRENCY", "2"))  # max requests at once
SAY_VOICE = os.getenv("SAY_VOICE", "Grandma (English (US))")
SAY_RATE = int(os.getenv("SAY_RATE", "150"))

# Printer: "none", "console" (prints the card to the terminal), or "usb"
PRINTER = os.getenv("PRINTER", "console")
PRINTER_USB_VENDOR = int(os.getenv("PRINTER_USB_VENDOR", "0") or "0", 16)
PRINTER_USB_PRODUCT = int(os.getenv("PRINTER_USB_PRODUCT", "0") or "0", 16)
PRINTER_WIDTH_CHARS = int(os.getenv("PRINTER_WIDTH_CHARS", "32"))  # 32 for 58mm, 48 for 80mm

# Party memory: text descriptions of costumes only, never images
MEMORY_FILE = Path(os.getenv("MEMORY_FILE", str(ROOT / "data" / "guests.json")))
MEMORY_RECALL = int(os.getenv("MEMORY_RECALL", "15"))
MEMORY_MAX_AGE_H = float(os.getenv("MEMORY_MAX_AGE_H", "12"))  # older guests are forgotten

CACHE_DIR = ROOT / "data" / "tts_cache"
SFX_DIR = ROOT / "assets" / "sfx"  # committed; regenerate with scripts/make_sfx.py
