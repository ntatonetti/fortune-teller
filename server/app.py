import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, oracle, printer, sfx, variety, voice
from .memory import GuestLog
from .models import Fortune

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


class Frame(BaseModel):
    image: str  # base64 JPEG, with or without a data: URL prefix
    audience: str = ""
    costume: str = ""
    question: str = ""
    paid_with: str = ""  # "coin" | "secret" | ""
    max_words: int = 0  # debug: cap what she says (?brief in the URL); 0 = full length


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
        "printer": config.PRINTER,
        "flickers": config.FACE_FLICKERS,
        "flicker_opacity": config.FLICKER_OPACITY,
        "timings": config.TIMINGS,
        "guests": guests.count(),
        "stock": {
            k: [{"url": _audio_url(name), "text": text} for name, text in zip(names, voice.STOCK_LINES[k])]
            for k, names in stock_audio.items()
        },
        "sfx": sfx.available(),
    }


@app.post("/api/greet")
async def greet(frame: Frame):
    g = await oracle.greet(_b64(frame.image), max_words=frame.max_words)
    if g is None:
        raise HTTPException(503, "Claude unavailable")
    log.info("greet: audience=%s size=%d costume=%r", g.audience, g.group_size, g.costume)
    audio = await voice.speak(g.greeting) if g.audience != "nobody" else None
    return {**g.model_dump(), "audio": _audio_url(audio)}


@app.post("/api/asked")
async def asked(heard: Heard):
    done = await oracle.asked(heard.question, heard.kid)
    if done is None:
        raise HTTPException(503, "Claude unavailable")
    log.info("asked: %d words, %s", len(heard.question.split()), "finished" if done else "still going")
    return {"done": done}


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
    )
    if f is None:
        raise HTTPException(503, "Claude unavailable")
    log.info(
        "fortune: audience=%s paid=%s asked=%s title=%r",
        f.audience,
        frame.paid_with or "-",
        "yes" if f.question else "no",
        f.card_title,
    )
    audio = await voice.speak(f.spoken)
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
    return {**f.model_dump(), "audio": _audio_url(audio)}


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


app.mount("/", StaticFiles(directory=config.ROOT / "static", html=True), name="static")
