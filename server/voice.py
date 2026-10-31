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
    # Before payment, she has them sit (unless they already have).
    "sit_child": [
        "Sit down, little one... right there on the chair, so we can see each other.",
        "Hop up on the chair, little one! Fortunes are best told sitting down.",
        "Find a seat, little one! Fortunes get all wobbly if you stand.",
        "Quick, sit down! The chair has been lonely all night... it's starting to sniffle.",
    ],
    "sit_adult": [
        "Sit, sit... take the chair, darling. The cards prefer you comfortable.",
        "Please... be seated. The fates do not read for those who hover.",
        "Come... sit before the glass. Closer. There.",
        "Take a seat, darling. Destiny is a long story.",
        "Do sit. The chair is haunted, but only a little... and it's very polite.",
        "Sit down, before the fates notice you're taller than they are. They hate that.",
    ],
    # Grown-ups pay with a whispered secret, kids with a spooky sound.
    "invite_adult": [
        "The fates demand payment... and they do not take gold. Lean close to the glass, darling, and whisper me a secret.",
        "Payment first. Not coin... a secret. Something true, something small... whisper it to the glass.",
        "The gears do not turn for free. Feed them a secret... whispered, close. They will keep it.",
        "Before the veil lifts... a toll. One secret, whispered softly. The juicier, the better.",
        "I would do this for free, darling, but the gears have a union. They want gossip. Whisper me a secret.",
        "Ahem. The fates accept secrets only. Not cash, not cards, and absolutely not candy corn. Whisper one to the glass.",
    ],
    "invite_child": [
        "Every fortune costs one spooky sound, little one! Give me your scariest... BOO... or your best ghost howl!",
        "To wake the spirits, I need a spooky sound! A ghost's oooooo... a witch's cackle... anything! Go on!",
        "Can you howl like a werewolf, little one? Or moan like a ghost? Make me your spookiest sound!",
        "The spirits only answer to spooky sounds! Your best boo, please... as loud as you dare!",
    ],
    "sound_child": [
        "Eek! That was terrifying! The spirits are wide awake now.",
        "Ooh, what a spooky sound! You gave my gears goosebumps.",
        "Aaah! You scared a bolt right out of me! Very well, little one... the fates are paid.",
        "Wonderful! Somewhere a real ghost just got jealous.",
    ],
    "secret_adult": [
        "Mmm... a delicious secret. It is safe with the gears... for now.",
        "Ohh... I shall treasure that one. The gears will never tell.",
        "A secret worth its weight in gold. Paid in full.",
        "Mmm. That one will keep me warm through the long, cold nights.",
        "Oh my. I'm going to need a moment... and possibly a fan.",
        "Scandalous! I shall tell absolutely no one. Except the moths. The moths don't count.",
    ],
    "ask_adult": [
        "Now... ask the fates your question. Speak it into the glass.",
        "Speak, then. What do you wish to ask the fates?",
        "The fates are listening... ask your question.",
        "Lean in... and tell the glass what troubles you.",
        "Ask me anything. Love, money, where your other sock went... the fates know it all.",
        "Your question, darling. And make it a good one... the spirits get bored easily.",
    ],
    "ask_child": [
        "Now, little one... what question would you like to ask the fates?",
        "What would you like to know, little one? Ask the fates anything!",
        "Ask me anything, little one! The fates love questions.",
        "What's your question? Dragons? Candy? Whether your cat is secretly a wizard? Ask away!",
    ],
    "heard_adult": [
        "So be it... the fates have heard you.",
        "Hmm... a question with teeth.",
        "Interesting... very interesting.",
        "Ahh... the fates sat up when you asked that.",
        "Ooh. Even my gears made a noise.",
        "Bold. The spirits are passing it around like a hot potato.",
    ],
    "heard_child": [
        "What a marvelous question! Let's see what the fates say...",
        "Ooh, a good one! Let me ask the spirits...",
        "A brilliant question! The spirits are leaning in...",
        "Ooh! The spirits are giggling... they love that one!",
    ],
    "no_question_adult": [
        "Silence? Then the fates will answer the question you hold in your heart.",
        "Keeping your question to yourself? Wise. The fates know it anyway.",
        "No words? No matter. The fates read the question in your eyes.",
        "Ah, the silent type. Mysterious. I'll just ask the fates about your love life, then.",
    ],
    "no_question_child": [
        "Too shy? That's all right... the fates already know what you're wondering.",
        "Shh, that's okay. The fates can read your mind!",
        "No question? That's fine... the crystal ball will pick a good one!",
        "Cat got your tongue? Don't worry... the cat told me everything.",
    ],
    # After they answer a question she asked them back.
    "answered_adult": [
        "Mmm... just as I suspected.",
        "Ahh. That explains a great deal.",
        "Interesting... the gears are taking notes.",
        "Yes... yes, that fits the pattern.",
        "Fascinating. I'll pretend I didn't already know.",
    ],
    "answered_child": [
        "Ooh, how wonderful! I knew it.",
        "Aha! That's just what my crystal ball said.",
        "Ooh, I love that!",
        "Wow! My crystal ball just did a little dance.",
    ],
    "no_answer_adult": [
        "Nothing? Keep your secrets, then... the cards will tell me.",
        "Silence... that is an answer too.",
        "Say nothing, then. The fates are not shy.",
        "The strong, silent type. The spirits find that very attractive.",
    ],
    "no_answer_child": [
        "That's all right... the fates can guess!",
        "Shy? Never mind... my crystal ball knows anyway.",
        "No answer? No problem! The fates know lots of things.",
        "Too shy? My crystal ball is shy too. It only talks to me.",
    ],
    # The tarot draw: cards shuffle through her ball until they choose.
    "draw_adult": [
        "Now... the cards. Your past, your present, your future. Watch the glass... and each time a card calls to you, say stop.",
        "The deck is restless tonight. What was, what is, what will be... Say stop, and stop, and stop again, as the cards call your name.",
        "Here come the cards... watch them drift through the glass. Each time one tugs at your heart, say stop.",
        "The cards are shuffling themselves... show-offs. Each time one winks at you, say stop!",
    ],
    "draw_one": [  # CARDS=1
        "Now... one card. Watch the glass... and when it calls to you, say stop.",
        "The deck is restless tonight. One card for you... When it calls your name, tell it to stop.",
        "One card holds your answer... watch the glass, and say stop when it calls.",
        "One card for you... they're all fighting to be picked. Say stop when one looks at you funny.",
    ],
    "consult_adult": [
        "Hmm... the gears are turning... the glass grows cloudy...",
        "The mist is stirring... I see shapes... shadows...",
        "Be still... the spirits are drawing near...",
        "The veil is thinning... hold very still...",
        "Hmm... the spirits are arguing... one of them wants a snack...",
        "Shh... I'm getting a signal... no, that's the radio next door... wait... there it is...",
    ],
    "consult_child": [
        "Ooh... let me look into my crystal ball...",
        "The ball is getting sparkly... something's coming...",
        "Swirly, swirly... the ball is waking up...",
        "Abracadabra, crystal ball... show us something good... and not broccoli!",
    ],
    "farewell_adult": [
        "Your fate is sealed. Take your ticket... and tell no one what you saw.",
        "It is written. Take your ticket... and mind the shadows on your way out.",
        "Go now. Your ticket holds what the fates have said... believe it or not.",
        "Take your ticket, and walk carefully. The future is watching.",
        "Your ticket, darling. Keep it close... it's legally binding in four dimensions.",
        "Off you go. Take your ticket... and if it all comes true, I accept tips in gold.",
    ],
    "farewell_child": [
        "Take your ticket, brave one... and may your night be full of sweets!",
        "Here's your ticket, little one! Happy Halloween... and stay brave!",
        "Here's your ticket, little one! Keep it safe... it's a little bit magic.",
        "Take your ticket! And if you meet a talking pumpkin tonight... tell it I said hi!",
    ],
    "rewind": [
        "The mechanism... must be... re-wound.",
        "Hmm... only shadows. Back to sleep, old gears.",
        "Nobody... just the wind playing tricks.",
        "False alarm... and I was having such a lovely dream about soup...",
    ],
    "beckon": [
        "Is someone there? Come closer... I cannot see you through the glass.",
        "I hear footsteps... come into the light, where I can see you.",
        "Who's lurking there? Step into the light... let me see your face.",
        "Come closer, darling. I don't bite... much.",
    ],
    "silent": [
        "The spirits are... silent. Press again, and I shall try once more.",
        "The spirits have put me on hold... Please enjoy this silence. Step up again in a moment.",
    ],
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
        "The pumpkins are unionizing... tell them nothing...",
        "No, I won't dance with the coat rack... not again...",
        "Forty-two teaspoons... and not one cup of tea...",
    ],
    "wake_startled": [
        "Hnh?! Wha... who's there? I wasn't asleep... I was listening to the gears.",
        "Mm?! The... the moths... oh. Oh. A visitor.",
        "Wh... where... what year is it? Never mind. Never mind.",
        "Hm?! Oh... forgive me. I was a thousand years away.",
        "Ah! I'm awake! Completely awake. Who said I was snoring?",
    ],
    "walkaway_adult": [
        "Hmph. Gone without a word... they always come back.",
        "Leaving so soon? The fates will remember that.",
        "Fine. Keep your future a mystery... the gears need their rest.",
        "Gone... and I hadn't even got to the good part.",
        "Walking away from destiny? Bold. Destiny is very good at catching up.",
    ],
    "walkaway_child": [
        "Oh! Off you go... goodbye, little one!",
        "Bye-bye! Come back anytime for your fortune!",
        "Bye, little one! Come back when you're ready!",
        "Oh! They ran off... probably to find more candy. Smart.",
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

