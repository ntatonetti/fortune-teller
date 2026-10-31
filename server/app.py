import asyncio
import logging
from contextlib import asynccontextmanager

from dotenv import set_key
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, history, oracle, printer, sfx, spend, variety, voice
from .memory import GuestLog
from .models import Fortune
from .setting_help import HELP

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("app")

guests = GuestLog(config.MEMORY_FILE, max_age_s=config.MEMORY_MAX_AGE_H * 3600)
stock_audio: dict[str, list[str | None]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = [k for k in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID") if not getattr(config, k)]
    if missing:
        raise RuntimeError(f"Set {', '.join(missing)} in .env: she needs Claude and ElevenLabs to run")
    stock_audio.update(await voice.prewarm())
    log.info(
        "Oracle ready: model=%s sfx=%d clips printer=%s guests_remembered=%d",
        config.CLAUDE_MODEL,
        sum(len(urls) for urls in sfx.available().values()),
        config.PRINTER,
        guests.count(),
    )
    yield


app = FastAPI(lifespan=lifespan)


class Heard(BaseModel):
    question: str
    kid: bool = False
    prompt: str = ""  # what she asked them, if this is their answer to her


class Talk(BaseModel):
    she: str  # what she asked them
    guest: str = ""  # what they answered


class Probe(BaseModel):
    kind: str  # "followup" (after their question)
    question: str = ""
    costume: str = ""
    kid: bool = False
    talk: list[Talk] = []
    max_words: int = 0


class Frame(BaseModel):
    image: str  # base64 JPEG, with or without a data: URL prefix
    audience: str = ""
    costume: str = ""
    question: str = ""
    paid_with: str = ""  # "coin" | "secret" | ""
    max_words: int = 0  # debug: cap what she says (?brief in the URL); 0 = full length
    talk: list[Talk] = []  # her questions back, and their answers
    cards: list[str] = []  # the tarot spread they drew: past, present, future


def _b64(image: str) -> str:
    data = image.split(",", 1)[1] if image.startswith("data:") else image
    if len(data) < 100:
        raise HTTPException(400, "image missing")
    return data


def _audio_url(name: str | None) -> str | None:
    return f"/api/audio/{name}" if name else None


@app.get("/api/config")
async def get_config():
    return {
        "name": config.ORACLE_NAME,
        "background": config.BACKGROUND,
        "printer": config.PRINTER,
        "flickers": config.FACE_FLICKERS,
        "flicker_where": config.FLICKER_WHERE,
        "flicker_opacity": config.FLICKER_OPACITY,
        "kid_flicker": config.KID_FLICKER,
        "timings": config.TIMINGS,
        "follow_up": config.FOLLOW_UP,
        "tarot": config.TAROT,
        "audience": config.AUDIENCE,
        "spread": variety.SPREAD[:config.CARDS],  # the places of the cards they may draw
        "deck": {
            "adult": [{"name": n, "img": variety.card_image(n)} for n in variety.TAROT],
        },
        "settings": [
            {"section": s, "name": n, "value": v, "about": a, **config.CONTROLS[n],
             "detail": HELP[n][0], "example": HELP[n][1]}
            for s, n, v, a in config.SETTINGS
        ],
        "voices": _voices(),
        "guests": guests.count(),
        "stock": {
            k: [{"url": _audio_url(name), "text": text} for name, text in zip(names, voice.STOCK_LINES[k])]
            for k, names in stock_audio.items()
        },
        "sfx": sfx.available(),
    }


def _voices() -> list[dict]:
    """The voices to choose from: VOICES, and the one she has if it isn't there."""
    listed = list(config.VOICES)
    if config.ELEVENLABS_VOICE_ID and all(v["id"] != config.ELEVENLABS_VOICE_ID for v in listed):
        listed.insert(0, {"name": "Original", "id": config.ELEVENLABS_VOICE_ID})
    return listed


class Edits(BaseModel):
    values: dict[str, str] = {}


class VoiceTry(BaseModel):
    voice_id: str


@app.post("/api/voice/sample")
async def voice_sample(v: VoiceTry):
    """A line in the given voice, to hear it on the start screen."""
    try:
        config.voices(f"x={v.voice_id}")
    except ValueError:
        raise HTTPException(400, "that isn't an ElevenLabs voice id")
    name = await voice.speak(voice.SAMPLE_LINE, voice_id=v.voice_id)
    if not name:
        raise HTTPException(502, "ElevenLabs wouldn't voice that one")
    return {"url": _audio_url(name)}


@app.post("/api/settings")
async def save_settings(edits: Edits):
    """Writes edited settings into .env, then re-reads .env (hand edits too), so
    the session about to start runs on them without a restart."""
    for name, raw in edits.values.items():
        if name not in config.CASTS:
            raise HTTPException(400, f"{name} isn't a setting she has")
        try:
            if "\n" in raw or "\r" in raw:
                raise ValueError
            config.check(name, raw)
        except ValueError:
            raise HTTPException(400, f"{name}: {raw!r} isn't a valid value")
    # A new voice or voice model must work before she's given it.
    voice_id = edits.values.get("ELEVENLABS_VOICE_ID", config.ELEVENLABS_VOICE_ID).strip()
    model = edits.values.get("ELEVENLABS_MODEL", config.ELEVENLABS_MODEL).strip()
    revoice = (voice_id, model) != (config.ELEVENLABS_VOICE_ID, config.ELEVENLABS_MODEL)
    if revoice and not await voice.speak(voice.SAMPLE_LINE, voice_id=voice_id, model=model):
        raise HTTPException(400, "ElevenLabs wouldn't use that voice with that model")
    for name, raw in edits.values.items():
        quote = "never" if config.CASTS[name] in (int, float, bool) else "auto"
        set_key(config.ENV_FILE, name, raw.strip(), quote_mode=quote)
        log.info("setting %s=%s", name, raw.strip())
    config.reload()
    guests.max_age_s = config.MEMORY_MAX_AGE_H * 3600
    if revoice:
        log.info("voicing her stock lines in the new voice")
        stock_audio.update(await voice.prewarm())
    return await get_config()


@app.post("/api/greet")
async def greet(frame: Frame):
    g = await oracle.greet(_b64(frame.image), max_words=frame.max_words)
    if g is None:
        raise HTTPException(503, "Claude unavailable")
    log.info("greet: audience=%s size=%d costume=%r", g.audience, g.group_size, g.costume)
    audio = await voice.speak(g.greeting) if g.audience != "nobody" else None
    return {**g.model_dump(), "audio": _audio_url(audio)}


@app.post("/api/coin")
async def coin(frame: Frame):
    """Whether they're paying: a coin shown at the glass, or a reach to drop one in."""
    shown = await oracle.coin_shown(_b64(frame.image))
    if shown is None:
        raise HTTPException(503, "Claude unavailable")
    if shown:
        log.info("coin: seen")
    return {"coin": shown}


@app.post("/api/asked")
async def asked(heard: Heard):
    done = await oracle.asked(heard.question, heard.kid, heard.prompt)
    if done is None:
        raise HTTPException(503, "Claude unavailable")
    log.info("%s: %d words, %s", "answered" if heard.prompt else "asked", len(heard.question.split()),
             "finished" if done else "still going")
    return {"done": done}


@app.post("/api/probe")
async def probe(p: Probe):
    """A question she asks them back, and her voice saying it."""
    if p.kind not in oracle.PROBES:
        raise HTTPException(400, f"no such question: {p.kind}")
    line = await oracle.probe(p.kind, p.question, p.costume, p.kid, [t.model_dump() for t in p.talk], max_words=p.max_words)
    if line is None:
        raise HTTPException(503, "Claude unavailable")
    log.info("probe: %s, %d words", p.kind, len(line.split()))
    return {"line": line, "audio": _audio_url(await voice.speak(line))}


@app.post("/api/fortune")
async def fortune(frame: Frame):
    f = await oracle.fortune(
        _b64(frame.image),
        frame.audience,
        frame.costume,
        guests.recent(config.MEMORY_RECALL),
        question=frame.question,
        paid_with=frame.paid_with,
        max_words=frame.max_words,
        talk=[t.model_dump() for t in frame.talk],
        cards=frame.cards,
    )
    if f is None:
        raise HTTPException(503, "Claude unavailable")
    log.info(
        "fortune: audience=%s paid=%s asked=%s cards=%s title=%r",
        f.audience,
        frame.paid_with or "-",
        "yes" if f.question else "no",
        ",".join(f.cards) or "-",
        f.card_title,
    )
    audio, *readings = await asyncio.gather(voice.speak(f.spoken), *(voice.speak(r) for r in f.readings))
    if f.audience != "nobody":
        guests.add(
            f.costume,
            f.audience,
            f.gist,
            title=f.card_title,
            lucky=f.lucky_number,
            task=f.task,
            opener=variety.opener(f.spoken),
        )
    return {**f.model_dump(), "audio": _audio_url(audio), "readings_audio": [_audio_url(a) for a in readings]}


@app.post("/api/print")
async def print_card(f: Fortune):
    return {"status": await asyncio.to_thread(printer.print_card, f)}


@app.get("/api/audio/{name}")
async def audio(name: str):
    path = voice.cached_path(name)
    if path is None:
        raise HTTPException(404)
    return FileResponse(path, media_type="audio/mpeg")


@app.get("/api/guests")
async def list_guests():
    return guests.recent(1000)


@app.delete("/api/guests")
async def clear_guests():
    guests.clear()
    variety.recent_greetings.clear()
    log.info("memory cleared: she has forgotten every guest")
    return {"cleared": True}


@app.get("/api/history")
async def history_days():
    return history.days()


@app.get("/api/history/{day}")
async def history_day(day: str):
    """One day's Claude calls, oldest first; /api/history/<day>.jsonl for the raw file."""
    if day.endswith(".jsonl"):
        path = history.path(day.removesuffix(".jsonl"))
        if path is None:
            raise HTTPException(404)
        return FileResponse(path, media_type="application/x-ndjson", filename=path.name)
    if history.path(day) is None:
        raise HTTPException(404)
    return history.read(day)


@app.get("/api/spend")
async def spend_report(day: str = ""):
    """What each stage of a reading costs, from the history: one day, or every day."""
    if day and history.path(day) is None:
        raise HTTPException(404)
    return spend.report(day)


app.mount("/", StaticFiles(directory=config.ROOT / "static", html=True), name="static")
