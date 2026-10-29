"""Machine sound effects: real clips from ElevenLabs instead of the browser synth.

Each variant is generated once into data/sfx/, named by a hash of its prompt, so
editing a prompt (or deleting a file) regenerates just that clip. Without a key,
or if generation fails, the browser keeps its synthesized sounds.
"""

import asyncio
import hashlib
import logging
from pathlib import Path

import httpx

from . import config, voice

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

_denied = False  # the key lacks the Sound Effects permission: skip the remaining requests


def filename(name: str, i: int, prompt: str, duration: float) -> str:
    digest = hashlib.sha256(f"{prompt}|{duration}|{name in LOOPED}".encode()).hexdigest()[:10]
    return f"{name}-{i}-{digest}.mp3"


def clip_path(name: str) -> Path | None:
    path = (config.SFX_DIR / name).resolve()
    if path.parent != config.SFX_DIR.resolve() or not path.exists():
        return None
    return path


async def _generate(prompt: str, duration: float, loop: bool) -> bytes | None:
    # Shares the TTS request slots, so the plan's concurrency cap covers both.
    async with voice._eleven_slots, httpx.AsyncClient(timeout=30) as client:
        if _denied:
            return None
        for delay in (*voice.RETRY_DELAYS_S, None):
            r = await client.post(
                SFX_URL,
                params={"output_format": "mp3_44100_128"},
                headers={"xi-api-key": config.ELEVENLABS_API_KEY, "accept": "audio/mpeg"},
                json={
                    "text": prompt,
                    "duration_seconds": duration,
                    "prompt_influence": 0.5,
                    "loop": loop,
                    "model_id": "eleven_text_to_sound_v2",
                },
            )
            if r.status_code == 429 and delay is not None:
                await asyncio.sleep(delay)
                continue
            r.raise_for_status()
            return r.content


async def _render(name: str, i: int, prompt: str, duration: float) -> None:
    path = config.SFX_DIR / filename(name, i, prompt, duration)
    tmp = path.with_suffix(".part")
    global _denied
    try:
        data = await _generate(prompt, duration, name in LOOPED)
        if data is None:
            return
        tmp.write_bytes(data)
        tmp.replace(path)  # never leave a half-written clip that looks finished
        log.info("generated sound effect %s", path.name)
    except httpx.HTTPStatusError as e:
        if e.response.status_code not in (401, 403):
            log.warning("sound effect %s #%d failed (%s); the synth sound stands in", name, i, e)
        elif not _denied:
            _denied = True
            log.warning(
                "ElevenLabs refused sound effects (%d: %s). The API key needs the Sound Effects permission"
                " (Developers -> API Keys -> edit the key); using the synth sounds for now.",
                e.response.status_code,
                e.response.text[:200],
            )
    except (httpx.HTTPError, OSError) as e:
        log.warning("sound effect %s #%d failed (%s); the synth sound stands in", name, i, e)
        tmp.unlink(missing_ok=True)


async def prewarm() -> None:
    """Generates any missing clips. Existing files are never re-requested."""
    global _denied
    if not config.ELEVENLABS_API_KEY:
        return
    _denied = False
    config.SFX_DIR.mkdir(parents=True, exist_ok=True)
    await asyncio.gather(
        *(
            _render(name, i, prompt, duration)
            for name, variants in EFFECTS.items()
            for i, (prompt, duration) in enumerate(variants)
            if not (config.SFX_DIR / filename(name, i, prompt, duration)).exists()
        )
    )


def available() -> dict[str, list[str]]:
    """Effect -> URLs of the clips on disk for the current prompts (stale files are ignored)."""
    out: dict[str, list[str]] = {}
    for name, variants in EFFECTS.items():
        files = [filename(name, i, p, d) for i, (p, d) in enumerate(variants)]
        urls = [f"/api/sfx/{f}" for f in files if (config.SFX_DIR / f).exists()]
        if urls:
            out[name] = urls
    return out
