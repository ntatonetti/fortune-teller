"""What her readings cost, stage by stage. Browse it at /spend.html.

Worked out from the history (history.py), so it only covers calls made since that
was kept. Claude is priced from the tokens each call used. The voice is priced from
the words she said: every greeting and fortune is new text, so ElevenLabs renders it
fresh, at the voice model set now (the history doesn't record which one spoke).
Stock lines are rendered once per voice and model and then cached, so they are a
one-off cost, shown apart.

List prices in US dollars, October 2026. They change: check them now and then.
"""

from . import config, history, voice

# $ per million tokens: (input, output). Thinking is billed as output, and the
# camera frame is part of the input.
CLAUDE_PRICES = {
    "claude-fable-5-1": (10.00, 50.00),
    "claude-fable-5": (10.00, 50.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

# $ per thousand characters through the ElevenLabs API.
VOICE_PRICES = {
    "eleven_flash_v2_5": 0.04, "eleven_flash_v2": 0.04, "eleven_turbo_v2_5": 0.04, "eleven_turbo_v2": 0.04,
    "eleven_v4_turbo": 0.04, "eleven_multilingual_v2": 0.08, "eleven_v3": 0.08, "eleven_v4": 0.08,
}

STAGES = [
    ("greet", "Greeting: Claude looks at them"),
    ("coin", "Coin held up? (Claude looks while they pay)"),
    ("asked", "Finished asking? (each pause)"),
    ("probe", "Her questions back: Claude writes them"),
    ("fortune", "Fortune: Claude reads them"),
    ("voice_greet", "Greeting: her voice"),
    ("voice_probe", "Her questions back: her voice"),
    ("voice_fortune", "Fortune: her voice"),
]


def _claude_cost(call: dict) -> float | None:
    price = CLAUDE_PRICES.get(call.get("served_by") or "") or CLAUDE_PRICES.get(call["model"])
    if price is None:
        return None
    return ((call.get("tokens_in") or 0) * price[0] + (call.get("tokens_out") or 0) * price[1]) / 1e6


def _spoken(call: dict) -> str:
    """The words of this call that ElevenLabs voiced ("" if none)."""
    out = call.get("output") or {}
    if call["kind"] == "greet" and out.get("audience") != "nobody":
        return out.get("greeting", "")
    if call["kind"] == "probe":
        return out.get("line", "")
    if call["kind"] == "fortune":
        # a tarot reading is spoken card by card, then the close
        return " ".join(out.get(k, "") for k in ("past", "present", "future", "spoken") if out.get(k))
    return ""


def report(day: str = "") -> dict:
    """Cost per stage for one day (YYYY-MM-DD), or every day kept if none is given."""
    days = [day] if day else [d["day"] for d in history.days()]
    calls = [c for d in days for c in history.read(d)]
    voice_price = VOICE_PRICES.get(config.ELEVENLABS_MODEL)
    rows = {key: {"stage": key, "label": label, "calls": 0, "failed": 0, "tokens_in": 0, "tokens_out": 0,
                  "chars": 0, "cost": 0.0} for key, label in STAGES}
    unpriced = set()
    for c in calls:
        row = rows.get(c["kind"])
        if row is None:
            continue
        row["calls"] += 1
        row["failed"] += bool(c.get("error"))
        row["tokens_in"] += c.get("tokens_in") or 0
        row["tokens_out"] += c.get("tokens_out") or 0
        cost = _claude_cost(c)
        if cost is None:
            unpriced.add(c.get("served_by") or c["model"])
        else:
            row["cost"] += cost
        text = _spoken(c)
        if text:
            v = rows["voice_" + c["kind"]]
            v["calls"] += 1
            v["chars"] += len(text)
    for key in ("voice_greet", "voice_probe", "voice_fortune"):
        rows[key]["cost"] = rows[key]["chars"] * (voice_price or 0) / 1000
    total = sum(r["cost"] for r in rows.values())
    readings = sum(1 for c in calls if c["kind"] == "fortune" and not c.get("error"))
    for r in rows.values():
        r["share"] = r["cost"] / total if total else 0
        r["per_reading"] = r["cost"] / readings if readings else None
    stock_chars = sum(len(t) for texts in voice.STOCK_LINES.values() for t in texts)
    return {
        "day": day,
        "days": len(days),
        "readings": readings,
        "total": total,
        "per_reading": total / readings if readings else None,
        "rows": list(rows.values()),
        "claude_model": config.CLAUDE_MODEL,
        "asked_model": config.ASKED_MODEL,
        "coin_model": config.COIN_MODEL,
        "chat_model": config.CHAT_MODEL,
        "voice_model": config.ELEVENLABS_MODEL,
        "voice_price_per_1k": voice_price,
        "stock_chars": stock_chars,
        "stock_cost": stock_chars * (voice_price or 0) / 1000,
        "unpriced": sorted(unpriced),
    }
