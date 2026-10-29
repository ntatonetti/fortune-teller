"""Machine sound effects: real clips from ElevenLabs instead of the browser synth.

scripts/make_sfx.py generates them once into static/sfx/, where they're committed and
served as static files, so the booth never calls ElevenLabs for them at party time.
Each file is named by a hash of its prompt, so editing a prompt (or deleting a file)
and rerunning the script regenerates just that clip. An effect with no clip uses the synth.
"""

import hashlib
import logging
import sys

import httpx

from . import config

log = logging.getLogger("sfx")

SFX_URL = "https://api.elevenlabs.io/v1/sound-generation"

# effect -> (prompt, seconds) variants; a few each so repeats don't sound identical
EFFECTS: dict[str, list[tuple[str, float]]] = {
    "creak": [
        ("old brass servo hinge creaking slowly, a 1920s carnival automaton turning its head", 1.0),
        ("rusty metal joint creak, short, close up", 0.8),
        ("wooden and brass mechanism creaking as it bends, eerie", 1.2),
    ],
    "grind": [
        ("antique clockwork gears grinding and catching, metal teeth slipping", 2.0),
        ("heavy brass gears grinding to life, ratcheting, old machine waking up", 2.5),
    ],
    "whir": [
        ("steady busy clockwork machinery whirring, many small gears turning, no music", 4.0),
        ("antique mechanical automaton humming and whirring inside a wooden cabinet", 4.0),
    ],
    "coin": [
        ("a gold coin dropping into a metal coin slot, rattling down a chute and clunking", 1.5),
        ("old carnival machine accepting a coin, metallic clink and thunk", 1.2),
    ],
    "ratchet": [
        ("paper ticket being ratcheted out of an antique fortune machine, fast clicking", 2.0),
        ("old mechanical card dispenser clattering out a printed card", 1.8),
    ],
}
LOOPED = frozenset({"whir"})  # plays for as long as she consults, so it must loop seamlessly


def filename(name: str, i: int, prompt: str, duration: float) -> str:
    digest = hashlib.sha256(f"{prompt}|{duration}|{name in LOOPED}".encode()).hexdigest()[:10]
    return f"{name}-{i}-{digest}.mp3"


def _current() -> dict[str, list[str]]:
    return {name: [filename(name, i, p, d) for i, (p, d) in enumerate(variants)] for name, variants in EFFECTS.items()}


def generate() -> None:
    """Requests each missing clip, one at a time. Exits if the key isn't allowed to."""
    config.SFX_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60) as client:
        for name, variants in EFFECTS.items():
            for i, (prompt, duration) in enumerate(variants):
                path = config.SFX_DIR / filename(name, i, prompt, duration)
                if path.exists():
                    continue
                r = client.post(
                    SFX_URL,
                    params={"output_format": "mp3_44100_128"},
                    headers={"xi-api-key": config.ELEVENLABS_API_KEY},
                    json={
                        "text": prompt,
                        "duration_seconds": duration,
                        "prompt_influence": 0.5,
                        "loop": name in LOOPED,
                        "model_id": "eleven_text_to_sound_v2",
                    },
                )
                if r.status_code in (401, 403):
                    sys.exit(f"ElevenLabs refused ({r.status_code}): the API key needs the Sound Effects permission. {r.text[:200]}")
                if r.is_error:
                    log.warning("%s #%d failed (%d %s); rerun to retry it", name, i, r.status_code, r.text[:200])
                    continue
                path.write_bytes(r.content)
                log.info("generated %s", path.name)


def prune() -> list[str]:
    """Deletes clips left over from old prompts; returns their names."""
    keep = {f for files in _current().values() for f in files}
    stale = sorted(p.name for p in config.SFX_DIR.glob("*.mp3") if p.name not in keep)
    for name in stale:
        (config.SFX_DIR / name).unlink()
    return stale


def available() -> dict[str, list[str]]:
    """Effect -> URLs of the clips on disk for the current prompts (stale files are ignored)."""
    out = {name: [f"/sfx/{f}" for f in files if (config.SFX_DIR / f).exists()] for name, files in _current().items()}
    return {name: urls for name, urls in out.items() if urls}
