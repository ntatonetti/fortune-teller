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
    stock, _ = await asyncio.gather(voice.prewarm(), sfx.prewarm())
    stock_audio.update(stock)
    log.info(
        "Oracle ready: model=%s claude=%s voice=%s sfx=%d clips printer=%s guests_remembered=%d",
        config.CLAUDE_MODEL,
        bool(config.ANTHROPIC_API_KEY),
        voice.provider(),
        sum(len(urls) for urls in sfx.available().values()),
        config.PRINTER,
        guests.count(),
    )
    yield


app = FastAPI(lifespan=lifespan)


class Frame(BaseModel):
    image: str  # base64 JPEG, with or without a data: URL prefix
    audience: str = ""
    costume: str = ""
    question: str = ""
    paid_with: str = ""  # "coin" | "secret" | ""


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
        "claude": bool(config.ANTHROPIC_API_KEY),
        "voice": voice.provider(),
        "printer": config.PRINTER,
        "guests": guests.count(),
        "stock": {
            k: [{"url": _audio_url(name), "text": text} for name, text in zip(names, voice.STOCK_LINES[k])]
            for k, names in stock_audio.items()
        },
        "sfx": sfx.available(),
    }


@app.post("/api/greet")
async def greet(frame: Frame):
    g = await oracle.greet(_b64(frame.image))
    log.info("greet: audience=%s size=%d costume=%r source=%s", g.audience, g.group_size, g.costume, g.source)
    audio = await voice.speak(g.greeting) if g.audience != "nobody" else None
    return {**g.model_dump(), "audio": _audio_url(audio)}


@app.post("/api/fortune")
async def fortune(frame: Frame):
    f = await oracle.fortune(
        _b64(frame.image),
        frame.audience,
        frame.costume,
        guests.recent(config.MEMORY_RECALL),
        question=frame.question,
        paid_with=frame.paid_with,
    )
    log.info(
        "fortune: audience=%s paid=%s asked=%s title=%r source=%s",
        f.audience,
        frame.paid_with or "-",
        "yes" if f.question else "no",
        f.card_title,
        f.source,
    )
    audio = await voice.speak(f.spoken)
    if f.source == "claude" and f.audience != "nobody":
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
    return FileResponse(path, media_type="audio/mpeg" if path.suffix == ".mp3" else "audio/wav")


@app.get("/api/sfx/{name}")
async def sfx_clip(name: str):
    path = sfx.clip_path(name)
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
