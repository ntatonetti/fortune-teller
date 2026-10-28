"""The oracle's memory of the night: who she has read, by costume.

Only short text descriptions are kept (never images or questions), so later
fortunes can reference earlier guests ("Beware the pirate...") and avoid
repeating what she already told someone. Entries older than MEMORY_MAX_AGE_H
are forgotten on their own, so a test run days earlier doesn't leak into the party.
"""

import json
import threading
import time
from pathlib import Path


class GuestLog:
    def __init__(self, path: Path, max_age_s: float):
        self.path = path
        self.max_age_s = max_age_s
        self._lock = threading.Lock()
        self._guests: list[dict] = []
        if path.exists():
            try:
                self._guests = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                self._guests = []

    def add(self, costume: str, audience: str, gist: str, **details) -> None:
        """details: title, lucky, task, opener - used to avoid repeating herself."""
        with self._lock:
            self._guests.append({"t": time.time(), "costume": costume, "audience": audience, "gist": gist, **details})
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._guests, indent=1))
            tmp.replace(self.path)

    def _fresh(self) -> list[dict]:
        cutoff = time.time() - self.max_age_s
        return [g for g in self._guests if g.get("t", 0) >= cutoff]

    def recent(self, n: int) -> list[dict]:
        with self._lock:
            return list(self._fresh()[-n:])

    def count(self) -> int:
        with self._lock:
            return len(self._fresh())

    def clear(self) -> None:
        with self._lock:
            self._guests = []
            self.path.unlink(missing_ok=True)
