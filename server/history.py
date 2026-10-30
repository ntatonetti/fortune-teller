"""Every Claude call she makes, kept for good, to study what goes in and comes out.

Unlike memory.py (a short text memory of the night that she reads back), this is
never shown to her: one JSON line per call, a file per day in HISTORY_DIR. It
holds the full system prompt, the prompt text, the guest's question and Claude's
answer, but never the camera frame. Browse it at /history.html.
"""

import json
import re
import threading
import time

from . import config

_lock = threading.Lock()


def _text(content: list) -> str:
    return "\n\n".join("[camera frame]" if b["type"] == "image" else b["text"] for b in content)


def record(kind: str, *, model: str, effort: str, system: str, content: list, started: float, response=None,
           output: dict | None = None, error: str = "") -> None:
    usage = getattr(response, "usage", None)
    entry = {
        "t": started,
        "kind": kind,
        "model": model,
        "served_by": getattr(response, "model", None),
        "effort": effort,
        "ms": round((time.time() - started) * 1000),
        "system": system,
        "prompt": _text(content),
        "output": output,
        "error": error,
        "stop_reason": getattr(response, "stop_reason", None),
        "tokens_in": getattr(usage, "input_tokens", None),
        "tokens_out": getattr(usage, "output_tokens", None),
    }
    day = time.strftime("%Y-%m-%d", time.localtime(started))
    try:
        with _lock:
            config.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
            with open(config.HISTORY_DIR / f"{day}.jsonl", "a") as f:
                f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # a full disk must never stop a reading


def days() -> list[dict]:
    """[{"day", "calls"}], newest first."""
    out = []
    for path in sorted(config.HISTORY_DIR.glob("*.jsonl"), reverse=True):
        with open(path) as f:
            out.append({"day": path.stem, "calls": sum(1 for _ in f)})
    return out


def path(day: str):
    """The file for a day (YYYY-MM-DD), or None."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        return None
    p = config.HISTORY_DIR / f"{day}.jsonl"
    return p if p.exists() else None


def read(day: str) -> list[dict]:
    p = path(day)
    if p is None:
        return []
    with open(p) as f:
        return [json.loads(line) for line in f if line.strip()]
