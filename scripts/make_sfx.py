"""Generates the oracle's machine sound effects with ElevenLabs, once, into assets/sfx/.

Usage: .venv/bin/python scripts/make_sfx.py   (needs ELEVENLABS_API_KEY with the Sound Effects permission)
Only missing clips are requested, so rerunning is cheap. Edit a prompt in server/sfx.py
(or delete a file) and rerun to replace a clip; clips from old prompts are removed.
Commit assets/sfx/ afterwards.
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import config, sfx  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

if not config.ELEVENLABS_API_KEY:
    sys.exit("Set ELEVENLABS_API_KEY in .env first.")

asyncio.run(sfx.generate())
for name in sfx.prune():
    print(f"removed stale {name}")
have = sfx.available()
want = {name: len(variants) for name, variants in sfx.EFFECTS.items()}
for name, n in want.items():
    print(f"{name:8} {len(have.get(name, []))}/{n}")
if any(len(have.get(name, [])) < n for name, n in want.items()):
    sys.exit("Some clips are missing (see the warnings above); rerun to retry just those.")
print(f"All clips are in {config.SFX_DIR.relative_to(config.ROOT)}/. Commit them.")
