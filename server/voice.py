"""Text-to-speech with ElevenLabs.

Every clip is cached on disk by a hash of (voice, text), so stock lines are only
paid for once and replays are instant.
"""

import asyncio
import hashlib
import logging
from pathlib import Path

import httpx

from . import config

log = logging.getLogger("voice")

ELEVEN_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

# Lines that don't depend on the guest, in a few wordings each so the people
# waiting in line don't hear the same script twice. Pre-rendered at startup.
STOCK_LINES: dict[str, list[str]] = {
    "invite_adult": [
        "The fates demand payment. A pirate's gold coin, if you have one... drop it in and press the button. If your pockets are empty... whisper me a secret instead.",
        "Payment first, darling. One pirate's gold coin in the slot, then press the button... or, if you carry no gold, confess a secret to the glass.",
        "The gears do not turn for free. A gold coin and the button... or a secret, whispered close. Your choice.",
    ],
    "invite_child": [
        "Do you have a golden pirate coin, little one? Drop it in and press the button! Or... tell me a secret, and I'll keep it safe.",
        "Every fortune costs one golden coin! Pop it in and press the button... or tell me a secret instead.",
    ],
    "secret_adult": [
        "Mmm... a delicious secret. It is safe with the gears... for now.",
        "Ohh... I shall treasure that one. The gears will never tell.",
        "A secret worth its weight in gold. Paid in full.",
    ],
    "secret_child": [
        "Ooh, what a wonderful secret! I'll lock it away in my music box.",
        "What a fantastic secret! It's safe with me, I promise.",
    ],
    "ask_adult": [
        "Now... ask the fates your question. Speak it into the glass.",
        "Speak, then. What do you wish to ask the fates?",
        "The fates are listening... ask your question.",
    ],
    "ask_child": [
        "Now, little one... what question would you like to ask the fates?",
        "What would you like to know, little one? Ask the fates anything!",
    ],
    "heard_adult": [
        "So be it... the fates have heard you.",
        "Hmm... a question with teeth.",
        "Interesting... very interesting.",
    ],
    "heard_child": [
        "What a marvelous question! Let's see what the fates say...",
        "Ooh, a good one! Let me ask the spirits...",
    ],
    "no_question_adult": [
        "Silence? Then the fates will answer the question you hold in your heart.",
        "Keeping your question to yourself? Wise. The fates know it anyway.",
    ],
    "no_question_child": [
        "Too shy? That's all right... the fates already know what you're wondering.",
        "Shh, that's okay. The fates can read your mind!",
    ],
    "consult_adult": [
        "Hmm... the gears are turning... the glass grows cloudy...",
        "The mist is stirring... I see shapes... shadows...",
        "Be still... the spirits are drawing near...",
    ],
    "consult_child": [
        "Ooh... let me look into my crystal ball...",
        "The ball is getting sparkly... something's coming...",
    ],
    "farewell_adult": [
        "Your fate is sealed. Take your ticket... and tell no one what you saw.",
        "It is written. Take your ticket... and mind the shadows on your way out.",
        "Go now. Your ticket holds what the fates have said... believe it or not.",
    ],
    "farewell_child": [
        "Take your ticket, brave one... and may your night be full of sweets!",
        "Here's your ticket, little one! Happy Halloween... and stay brave!",
    ],
    "rewind": [
        "The mechanism... must be... re-wound.",
        "Hmm... only shadows. Back to sleep, old gears.",
    ],
    "beckon": [
        "Is someone there? Come closer... I cannot see you through the glass.",
        "I hear footsteps... come into the light, where I can see you.",
    ],
    "silent": ["The spirits are... silent. Press again, and I shall try once more."],
    # Talking in her sleep: half sense, half nonsense.
    "sleeptalk": [
        "No... no, the spoons go in the clock... the clock goes in the spoons...",
        "Mother... the brass moths are counting the teeth again...",
        "Seven buttons for the drowned man... he only wanted six...",
        "Don't wind me... not yet... the carnival is still on fire...",
        "Who left the moon in the ticket slot... mmm...",
        "Tell the gentleman his hat is a cake... he knows... he knows...",
        "Velvet... velvet tastes like Tuesday...",
        "The pirate owes me a tooth... a gold one... ahh...",
    ],
    "wake_startled": [
        "Hnh?! Wha... who's there? I wasn't asleep... I was listening to the gears.",
        "Mm?! The... the moths... oh. Oh. A visitor.",
        "Wh... where... what year is it? Never mind. Never mind.",
    ],
    "walkaway_adult": [
        "Hmph. Gone without a word... they always come back.",
        "Leaving so soon? The fates will remember that.",
        "Fine. Keep your future a mystery... the gears need their rest.",
    ],
    "walkaway_child": [
        "Oh! Off you go... goodbye, little one!",
        "Bye-bye! Come back anytime for your fortune!",
    ],
}


def _key(text: str) -> str:
    voice = f"eleven:{config.ELEVENLABS_VOICE_ID}:{config.ELEVENLABS_MODEL}"
    return hashlib.sha256(f"{voice}|{text}".encode()).hexdigest()[:24]


def cached_path(name: str) -> Path | None:
    path = (config.CACHE_DIR / name).resolve()
    if path.parent != config.CACHE_DIR.resolve() or not path.exists():
        return None
    return path


# ElevenLabs plans cap simultaneous requests (a few at most), so queue ours and
# retry briefly when told to slow down.
_eleven_slots = asyncio.Semaphore(config.ELEVENLABS_CONCURRENCY)
RETRY_DELAYS_S = (1.0, 2.5)


async def _eleven(text: str) -> bytes:
    async with _eleven_slots, httpx.AsyncClient(timeout=20) as client:
        for delay in (*RETRY_DELAYS_S, None):
            r = await client.post(
                ELEVEN_URL.format(voice_id=config.ELEVENLABS_VOICE_ID),
                params={"output_format": "mp3_44100_128"},
                headers={"xi-api-key": config.ELEVENLABS_API_KEY, "accept": "audio/mpeg"},
                json={
                    "text": text,
                    "model_id": config.ELEVENLABS_MODEL,
                    "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35},
                },
            )
            if r.status_code == 429 and delay is not None:
                await asyncio.sleep(delay)
                continue
            r.raise_for_status()
            return r.content


async def speak(text: str) -> str | None:
    """Render `text` to an audio file and return its cache filename (or None)."""
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{_key(text)}.mp3"
    path = config.CACHE_DIR / name
    if path.exists():
        return name
    try:
        path.write_bytes(await _eleven(text))
        return name
    except (httpx.HTTPError, OSError) as e:
        log.error("ElevenLabs failed: %s", e)
        return None


async def prewarm() -> dict[str, list[str | None]]:
    """Renders every wording of every stock line; returns cache filenames per key."""
    flat = [(key, text) for key, texts in STOCK_LINES.items() for text in texts]
    names = await asyncio.gather(*(speak(text) for _, text in flat))
    out: dict[str, list[str | None]] = {key: [] for key in STOCK_LINES}
    for (key, _), name in zip(flat, names):
        out[key].append(name)
    return out

