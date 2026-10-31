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
        "The fates demand payment. A pirate's gold coin, if you have one... hold it up to the glass, so I can see it shine. If your pockets are empty... whisper me a secret instead.",
        "Payment first, darling. Show me one pirate's gold coin, up to the glass... or, if you carry no gold, confess a secret.",
        "The gears do not turn for free. Hold a gold coin up where I can see it... or whisper a secret, close. Your choice.",
    ],
    "invite_child": [
        "Do you have a golden pirate coin, little one? Hold it up to the glass so I can see it! Or... tell me a secret, and I'll keep it safe.",
        "Every fortune costs one golden coin! Show it to me, up high... or tell me a secret instead.",
    ],
    # She saw the coin they held up: into the cup with it.
    "coin_seen_adult": [
        "Ahh... real pirate gold. Into the cup with it.",
        "I see it gleaming. Drop it in the cup, darling... the fates are paid.",
        "Gold... how it shines. Into the cup, and we may begin.",
    ],
    "coin_seen_child": [
        "Ooh, what a shiny coin! Pop it in the cup for me.",
        "I see it! Real pirate gold! Drop it in the cup, little one.",
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
    # After they answer a question she asked them back.
    "answered_adult": [
        "Mmm... just as I suspected.",
        "Ahh. That explains a great deal.",
        "Interesting... the gears are taking notes.",
    ],
    "answered_child": [
        "Ooh, how wonderful! I knew it.",
        "Aha! That's just what my crystal ball said.",
    ],
    "no_answer_adult": [
        "Nothing? Keep your secrets, then... the cards will tell me.",
        "Silence... that is an answer too.",
    ],
    "no_answer_child": [
        "That's all right... the fates can guess!",
        "Shy? Never mind... my crystal ball knows anyway.",
    ],
    # The tarot draw: cards shuffle through her ball until they choose.
    "draw_adult": [
        "Now... three cards. Your past, your present, your future. Watch the glass... and when a card calls to you, say stop.",
        "The deck is restless tonight. Three cards: what was, what is, what will be. When one calls your name... tell it to stop.",
    ],
    "card_past": ["Your past...", "This one... the past.", "The past..."],
    "card_present": ["Your present...", "And now... the present.", "The present..."],
    "card_future": ["And your future...", "Last of all... the future.", "The future..."],
    "card_chooses": ["Hmm... this one chooses you.", "The card has chosen for you."],
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


# Played on the start screen to hear a voice, and voiced to test a new one.
SAMPLE_LINE = "Come closer, darling... the gears have been waiting for you."


def _key(text: str, voice_id: str, model: str) -> str:
    voice = f"eleven:{voice_id}:{model}"
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


async def _eleven(text: str, voice_id: str, model: str) -> bytes:
    async with _eleven_slots, httpx.AsyncClient(timeout=20) as client:
        for delay in (*RETRY_DELAYS_S, None):
            r = await client.post(
                ELEVEN_URL.format(voice_id=voice_id),
                params={"output_format": "mp3_44100_128"},
                headers={"xi-api-key": config.ELEVENLABS_API_KEY, "accept": "audio/mpeg"},
                json={
                    "text": text,
                    "model_id": model,
                    "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35},
                },
            )
            if r.status_code == 429 and delay is not None:
                await asyncio.sleep(delay)
                continue
            r.raise_for_status()
            return r.content


async def speak(text: str, voice_id: str = "", model: str = "") -> str | None:
    """Render `text` to an audio file and return its cache filename (or None).
    In her voice unless another is given."""
    voice_id = voice_id or config.ELEVENLABS_VOICE_ID
    model = model or config.ELEVENLABS_MODEL
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{_key(text, voice_id, model)}.mp3"
    path = config.CACHE_DIR / name
    if path.exists():
        return name
    try:
        path.write_bytes(await _eleven(text, voice_id, model))
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

