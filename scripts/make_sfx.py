"""Generates the oracle's machine sound effects with ElevenLabs, once, into static/sfx/.

Usage: .venv/bin/python scripts/make_sfx.py   (needs ELEVENLABS_API_KEY with the Sound Effects permission)
Only missing clips are requested. Edit a prompt in server/sfx.py (or delete a file) and
rerun to replace a clip; clips from old prompts are removed. Commit static/sfx/ afterwards.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import config, sfx  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

if not config.ELEVENLABS_API_KEY:
    sys.exit("Set ELEVENLABS_API_KEY in .env first.")
sfx.generate()
for name in sfx.prune():
    print(f"removed stale {name}")
have = sfx.available()
for name, variants in sfx.EFFECTS.items():
    print(f"{name:8} {len(have.get(name, []))}/{len(variants)}")
