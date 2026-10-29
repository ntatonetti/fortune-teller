# ElevenLabs Sound Effects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Madame Mechanika stops speaking sound effects aloud, and her machine sounds become real ElevenLabs-generated clips with the existing synth sounds as fallback.

**Architecture:** The server tells Claude not to write noises and scrubs any that slip through before TTS. A new `server/sfx.py` generates a small fixed clip library once via ElevenLabs `/v1/sound-generation`, caches it in `data/sfx/`, and advertises it in `/api/config`. In the browser, `sound.js` plays a random clip variant when one is loaded and otherwise runs its current synth code.

**Tech Stack:** Python 3 / FastAPI / httpx / pytest; browser WebAudio (ES modules); `node --test` for pure JS helpers.

**Spec:** `docs/superpowers/specs/2026-10-28-elevenlabs-sfx-design.md`

## Global Constraints

- With `ELEVENLABS_API_KEY` blank, or any generation/fetch failure, behaviour is exactly today's synth sounds. Nothing raises into a reading.
- Sound-effects generation needs only `ELEVENLABS_API_KEY` (no voice ID).
- API: `POST https://api.elevenlabs.io/v1/sound-generation`, query `output_format=mp3_44100_128`, JSON `{text, duration_seconds, prompt_influence: 0.5, loop, model_id: "eleven_text_to_sound_v2"}`, header `xi-api-key`. `duration_seconds` must be 0.5–30. `loop: true` only for `whir`.
- Share `voice._eleven_slots` (the concurrency semaphore) with TTS so total ElevenLabs requests in flight stay ≤ `ELEVENLABS_CONCURRENCY`; retry 429s using `voice.RETRY_DELAYS_S`.
- Clips live in `config.SFX_DIR = ROOT / "data" / "sfx"` (already gitignored via `data/`), served at `/api/sfx/<file>`.
- Only `creak`, `grind`, `whir`, `coin`, `ratchet` change. Music box, bells (`cue`), `shimmer`, `tick`, `clock` stay synth.
- Effect clips go into the existing `this.sfx` bus (it bypasses the phonograph filter and the jaw analyser).
- Public signatures of `creak(vol)`, `grind(duration, vol)`, `whir(on)`, `coin()`, `ratchet(seconds)` don't change.

## Review Focus

1. **Stale clips after editing a prompt.** The old file is still on disk, but `available()` must list only files that match the current `EFFECTS`, so an edited prompt is never served with old audio. Test in Task 2.
2. **Partial library** (some variants failed at startup). Only the clips that succeeded are advertised, the next startup retries just the missing ones, and existing files are never re-requested. Test in Task 2.
3. **Path traversal on `/api/sfx/../...`** must return 404, not a file. Test in Task 2.
4. **A sound fragment at the very start of a line** ("Whirrr... the gears...") must leave a capitalized, punctuation-clean sentence, because it shows in subtitles. Test in Task 1.
5. **`whir(true)` called while a whir is already running, or clips failing to decode in the browser.** There must never be two stacked loops, and a failed effect must fall back to synth. The variant-picking helper is unit-tested in Task 3; stacking and decode failure are covered in the Task 4 manual pass.

---

### Task 1: Keep sound words out of her speech

**Files:**
- Modify: `server/oracle.py` (`PERSONA`, greeting prompt text at ~line 161, `greet()` and `fortune()` success paths)
- Test: `tests/test_server.py`

**Interfaces:**
- Produces: `oracle.scrub_spoken(text: str) -> str`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_server.py`)

```python
import pytest

@pytest.mark.parametrize("raw, clean", [
    ("*creak* Ah... a visitor.", "Ah... a visitor."),
    ("Creak... whirrr... Ah, a pirate! Come closer...", "Ah, a pirate! Come closer..."),
    ("Creak, creak! The gears wake.", "The gears wake."),
    ("Whirrr... the gears remember you.", "The gears remember you."),
    ("Hmm [gears grinding] your future glows.", "Hmm your future glows."),
    ("Your fate is sealed... clank! Beware the raven.", "Your fate is sealed... Beware the raven."),
    ("(a long hiss) Lucky seven.", "Lucky seven."),
    ("The gears whir in the dark... your ticket awaits.", "The gears whir in the dark... your ticket awaits."),
    ("*whirrr*", "*whirrr*"),
])
def test_scrub_spoken(raw, clean):
    assert oracle.scrub_spoken(raw) == clean


def test_claude_lines_are_scrubbed(monkeypatch):
    async def fake_ask(schema, *a, **k):
        if schema is oracle.GREET_SCHEMA:
            return {"audience": "adult", "group_size": 1, "costume": "a pirate", "greeting": "*creak* Ahoy... come closer."}
        return {"audience": "adult", "group_size": 1, "costume": "a pirate", "spoken": "Clank! Seven ravens.",
                "card_title": "The Raven", "card_text": "*whirr* Seven ravens.", "lucky_number": 7,
                "task": "Toast a ghost.", "gist": "ravens"}
    monkeypatch.setattr(oracle, "_ask", fake_ask)
    g = asyncio.run(oracle.greet("x" * 200))
    assert g.greeting == "Ahoy... come closer."
    f = asyncio.run(oracle.fortune("x" * 200, "adult", "a pirate", []))
    assert f.spoken == "Seven ravens." and f.card_text == "Seven ravens."


def test_persona_forbids_sound_effects():
    assert "Never write sound effects" in oracle.PERSONA
```

- [ ] **Step 2: Run them and check they fail**

Run: `.venv/bin/pytest tests/test_server.py -k "scrub or sound_effects" -v`
Expected: FAIL, `AttributeError: module 'server.oracle' has no attribute 'scrub_spoken'`

- [ ] **Step 3: Implement**

- Add this to `PERSONA`, after the paragraph about how she speaks: `Your words are spoken aloud by your voice box. Never write sound effects, noises, or stage directions (no creak, whirr, clank, no asterisks or brackets). Your machinery makes its own sounds.`
- In the greeting prompt, replace `you are creaking awake` with `you are stirring awake`.
- Add `scrub_spoken(text: str) -> str` near `is_childlike`, then:
  1. Remove `\*[^*]*\*`, `\[[^\]]*\]` and `\([^)]*\)`.
  2. Remove fragment sound words until nothing changes. A sound word is removed, together with its trailing punctuation and spaces, only when it comes at the start of the text or after punctuation plus a space, and is followed by punctuation or the end of the text. A word inside a sentence ("the gears whir in") is never touched.
     ```python
     _SOUND = r"(?:c+r+e+a+k+|w+h+i+r+|c+l+a+n+k+|c+l+i+n+k+|c+l+i+c+k+|c+l+a+c+k+|t+i+c+k+|t+o+c+k+|g+r+i+n+d+|b+z+t+|h+i+s+s+|d+i+n+g+|c+l+u+n+k+)"
     _FRAGMENT = re.compile(rf"(^|(?<=[.,!?…—-])\s+){_SOUND}[.,!?…—\-]+(\s+|$)", re.I)
     # substitute with r"\1" in a loop until stable
     ```
  3. Tidy up: collapse repeated whitespace, strip leading punctuation and spaces, strip the ends, and capitalize the first character.
  4. If the result is empty, return the original `text`.
- In `greet()`, after `Greeting(**data)` is validated, set `g.greeting = scrub_spoken(g.greeting)`. In `fortune()`, after `Fortune(...)` is validated, scrub `result.spoken` and `result.card_text`. Don't scrub the fallback lines.

- [ ] **Step 4: Run the tests and check they pass**

Run: `.venv/bin/pytest -q`
Expected: all pass, including the existing tests.

- [ ] **Step 5: Commit**

```bash
git add server/oracle.py tests/test_server.py
git commit -m "Keep spoken sound effects out of the oracle's lines"
```

---

### Task 2: Sound-effect library on the server

**Files:**
- Create: `server/sfx.py`
- Modify: `server/config.py` (add `SFX_DIR`), `server/app.py` (lifespan, route, `/api/config`), `README.md` ("Keys and voices")
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `voice._eleven_slots`, `voice.RETRY_DELAYS_S`, `config.ELEVENLABS_API_KEY`
- Produces:
  - `sfx.EFFECTS: dict[str, list[tuple[str, float]]]`, mapping effect name → `(prompt, duration_seconds)` variants
  - `sfx.LOOPED: frozenset[str] = frozenset({"whir"})`
  - `sfx.filename(name: str, i: int, prompt: str, duration: float) -> str`, giving `f"{name}-{i}-{hash10}.mp3"`, where `hash10` is the first 10 hex characters of sha256 of `f"{prompt}|{duration}|{name in LOOPED}"`
  - `async sfx.prewarm() -> None`
  - `sfx.available() -> dict[str, list[str]]`, mapping effect name → `"/api/sfx/<file>"` URLs, for current files only. Effects with no files are left out.
  - `sfx.clip_path(name: str) -> Path | None`, with the same safety rules as `voice.cached_path`, but checked against `config.SFX_DIR`
  - `GET /api/sfx/{name}` returns `audio/mpeg`, or 404
  - `/api/config` gains a `"sfx"` field holding `sfx.available()`

- [ ] **Step 1: Write the failing tests**

```python
import httpx

def _sfx_env(monkeypatch, tmp_path, key="k"):
    from server import sfx, voice
    monkeypatch.setattr(sfx.config, "SFX_DIR", tmp_path)
    monkeypatch.setattr(sfx.config, "ELEVENLABS_API_KEY", key)
    monkeypatch.setattr(voice, "RETRY_DELAYS_S", (0.01,))
    return sfx

def _mock_eleven(monkeypatch, sfx, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(sfx.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))

def test_sfx_prewarm_without_key_does_nothing(monkeypatch, tmp_path):
    sfx = _sfx_env(monkeypatch, tmp_path, key="")
    asyncio.run(sfx.prewarm())
    assert sfx.available() == {} and list(tmp_path.iterdir()) == []

def test_sfx_prewarm_generates_every_variant_with_loop_only_for_whir(monkeypatch, tmp_path):
    sfx = _sfx_env(monkeypatch, tmp_path)
    seen = []
    def handler(req):
        body = json.loads(req.content)
        seen.append(body)
        assert req.url.path == "/v1/sound-generation" and req.headers["xi-api-key"] == "k"
        return httpx.Response(200, content=b"ID3sfx")
    _mock_eleven(monkeypatch, sfx, handler)
    asyncio.run(sfx.prewarm())
    total = sum(len(v) for v in sfx.EFFECTS.values())
    assert len(seen) == total
    assert all(b["loop"] == (b["text"] in [p for p, _ in sfx.EFFECTS["whir"]]) for b in seen)
    assert all(0.5 <= b["duration_seconds"] <= 30 and b["model_id"] == "eleven_text_to_sound_v2" for b in seen)
    assert set(sfx.available()) == {"creak", "grind", "whir", "coin", "ratchet"}

def test_sfx_partial_failure_is_skipped_then_retried_only_for_missing(monkeypatch, tmp_path):
    sfx = _sfx_env(monkeypatch, tmp_path)
    creak_prompts = {p for p, _ in sfx.EFFECTS["creak"]}
    def flaky(req):
        failing = json.loads(req.content)["text"] in creak_prompts
        return httpx.Response(500) if failing else httpx.Response(200, content=b"ID3")
    _mock_eleven(monkeypatch, sfx, flaky)
    asyncio.run(sfx.prewarm())  # must not raise
    assert "creak" not in sfx.available() and "coin" in sfx.available()
    second = []
    _mock_eleven(monkeypatch, sfx, lambda req: second.append(json.loads(req.content)["text"]) or httpx.Response(200, content=b"ID3"))
    asyncio.run(sfx.prewarm())
    assert sorted(second) == sorted(creak_prompts)  # only the missing variants are requested
    assert len(list(tmp_path.iterdir())) == sum(len(v) for v in sfx.EFFECTS.values())

def test_sfx_stale_files_are_not_advertised(monkeypatch, tmp_path):
    sfx = _sfx_env(monkeypatch, tmp_path)
    (tmp_path / "creak-0-deadbeef00.mp3").write_bytes(b"old")
    assert sfx.available() == {}

def test_sfx_route_serves_clips_and_blocks_traversal(monkeypatch, tmp_path):
    sfx = _sfx_env(monkeypatch, tmp_path)
    prompt, dur = sfx.EFFECTS["coin"][0]
    name = sfx.filename("coin", 0, prompt, dur)
    (tmp_path / name).write_bytes(b"ID3coin")
    client = TestClient(app_module.app)
    assert client.get(f"/api/sfx/{name}").content == b"ID3coin"
    assert client.get("/api/sfx/..%2F..%2F.env").status_code == 404
    assert client.get("/api/config").json()["sfx"]["coin"] == [f"/api/sfx/{name}"]
```

- [ ] **Step 2: Run them and check they fail**

Run: `.venv/bin/pytest tests/test_server.py -k sfx -v`
Expected: FAIL, `ImportError: cannot import name 'sfx'`

- [ ] **Step 3: Implement `server/sfx.py`, config, and app wiring**

- Write the module docstring in the same style as `voice.py`.
- Use these `EFFECTS` prompts as the exact text:
  - `creak`: ("old brass servo hinge creaking slowly, a 1920s carnival automaton turning its head", 1.0), ("rusty metal joint creak, short, close up", 0.8), ("wooden and brass mechanism creaking as it bends, eerie", 1.2)
  - `grind`: ("antique clockwork gears grinding and catching, metal teeth slipping", 2.0), ("heavy brass gears grinding to life, ratcheting, old machine waking up", 2.5)
  - `whir`: ("steady busy clockwork machinery whirring, many small gears turning, no music", 4.0), ("antique mechanical automaton humming and whirring inside a wooden cabinet", 4.0)
  - `coin`: ("a gold coin dropping into a metal coin slot, rattling down a chute and clunking", 1.5), ("old carnival machine accepting a coin, metallic clink and thunk", 1.2)
  - `ratchet`: ("paper ticket being ratcheted out of an antique fortune machine, fast clicking", 2.0), ("old mechanical card dispenser clattering out a printed card", 1.8)
- `_generate(prompt, duration, loop) -> bytes`: read `voice.RETRY_DELAYS_S` and `voice._eleven_slots` through the `voice` module when the call runs, not by importing their values, so the test monkeypatches take effect. Use the same `async with voice._eleven_slots, httpx.AsyncClient(timeout=30)` and 429-retry loop as `voice._eleven`, with the request shape given in Global Constraints.
- `prewarm()`: return right away if there's no key. `mkdir` `SFX_DIR`. `asyncio.gather` one coroutine per variant whose file is missing. Each one catches `(httpx.HTTPError, OSError)`, logs a warning, and returns. Write each file to a temp name, then `replace` it, so an interrupted write never leaves a half-written file that looks valid.
- `config.py`: add `SFX_DIR = ROOT / "data" / "sfx"` under `CACHE_DIR`.
- `app.py`: import `sfx`. In `lifespan`, run `voice.prewarm()` and `sfx.prewarm()` together with `asyncio.gather`, and add `sfx=%d clips` to the ready log line. Add the `/api/sfx/{name}` route next to `/api/audio/{name}`, and add `"sfx": sfx.available()` to `get_config`.
- README "Keys and voices", ElevenLabs paragraph: add one paragraph. It should say the same key also generates her machine sounds (creaks, grinding gears, whirring, the coin drop, the ticket ratchet) once at startup into `data/sfx/`, that this is about 11 one-time generations, that deleting a file regenerates it, and that without a key she uses the built-in synthesized sounds.

- [ ] **Step 4: Run the tests and check they pass**

Run: `.venv/bin/pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add server/sfx.py server/config.py server/app.py tests/test_server.py README.md
git commit -m "Generate machine sound effects with ElevenLabs and serve them"
```

---

### Task 3: Play the clips in the browser

**Files:**
- Modify: `static/js/sound.js` (constructor, new methods, `creak`/`grind`/`whir`/`coin`/`ratchet`), `static/js/main.js` (~line 701, startup warm-up)
- Create: `tests/js/sound.test.mjs`

**Interfaces:**
- Consumes: the `server.sfx` map from `/api/config`, shaped `{ [effect]: string[] }`
- Produces:
  - `export function pickVariant(n: number, last: number, rand = Math.random): number`. Returns an index in `[0, n)`, never equal to `last` when `n > 1`, and `0` when `n === 1`.
  - `Sound#loadEffects(map: Record<string, string[]>): Promise<void>`. Fills `this._clips[name] = AudioBuffer[]` using `this.load(url)`. A clip that fails to fetch or decode is dropped, with a `console.warn`. It never rejects.
  - `Sound#_playClip(name: string, { vol = 1, seconds = null, loop = false }): { src: AudioBufferSourceNode, gain: GainNode } | null`. Returns `null` when that effect has no clips.

- [ ] **Step 1: Write the failing test** in `tests/js/sound.test.mjs`

(`sound.js` has no imports and only creates its `AudioContext` in the constructor, so node can import it.)

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { pickVariant } from "../../static/js/sound.js";

test("single variant always 0", () => {
  assert.equal(pickVariant(1, 0), 0);
  assert.equal(pickVariant(1, -1), 0);
});

test("never repeats the last variant", () => {
  for (let last = 0; last < 3; last++)
    for (const r of [0, 0.34, 0.5, 0.99]) {
      const i = pickVariant(3, last, () => r);
      assert.ok(i >= 0 && i < 3 && i !== last);
    }
});
```

- [ ] **Step 2: Run it and check it fails**

Run: `node --test tests/js/*.test.mjs`
Expected: FAIL, `pickVariant` is not exported

- [ ] **Step 3: Implement**

- `pickVariant`: when `n > 1`, pick from the `n - 1` indices other than `last` (`i = floor(rand() * (n - 1))`, then `if (i >= last) i++`).
- In the constructor, add `this._clips = {}` and `this._lastClip = {}`, plus a module-level `CLIP_GAIN = { creak: 1, grind: 1, whir: 0.6, coin: 1, ratchet: 1 }`. These are starting values, to be tuned by ear in Task 4.
- `_playClip`: choose the buffer with `pickVariant`, then route `AudioBufferSourceNode → GainNode → this.sfx`, with gain `CLIP_GAIN[name] * vol`. With `seconds`, stop at `seconds` after a 0.15 s fade. With `loop`, set `src.loop = true`.
- Each of the five methods tries the clip first and keeps its synth body as the fallback. `vol` is relative to the method's own default:
  - `creak(vol = 0.25)` uses `_playClip("creak", { vol: vol / 0.25 })`
  - `grind(duration = 1.2, vol = 0.5)` uses `_playClip("grind", { vol: vol / 0.5, seconds: duration })`
  - `coin()` uses `_playClip("coin")`
  - `ratchet(seconds = 1.6)` uses `_playClip("ratchet", { seconds })`
  - `whir(on)`: keep the existing stop block at the top so an earlier whir always stops before a new one starts. When `on` and a clip plays, fade its gain in over 0.15 s with `setTargetAtTime`, store `this._loops.whir = { nodes: [src], gain }` so the existing stop code handles it, and return before the synth code.
- `main.js`: next to the stock-line warm-up (~line 701), add `sound.loadEffects(server.sfx || {});`. Don't `await` it. Next to the other `window.oracle*` debug hooks, add `window.oracleSound = () => sound; // for poking effects from DevTools`.

- [ ] **Step 4: Run the tests and check they pass**

Run: `node --test tests/js/*.test.mjs && .venv/bin/pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add static/js/sound.js static/js/main.js tests/js/sound.test.mjs
git commit -m "Play ElevenLabs effect clips with synth fallback"
```

---

### Task 4: Listening pass

No code unless tuning is needed. This needs a real `ELEVENLABS_API_KEY` in `.env`.

- [ ] **Step 1:** Run `.venv/bin/python -m server`. The ready log should show `sfx=11 clips`, and `ls data/sfx` should list 11 `.mp3` files.
- [ ] **Step 2:** In Chrome at http://localhost:8000, click Awaken, then:
  - Press **W**: you should hear a creak and a grind on waking.
  - Press **Space**: you should hear the coin clip.
  - The consult phase should play the whir loop, with no audible seam, and it should stop cleanly.
  - Press **G**, then do an adult reading: the grind should play mid-sentence.
  - The end of the reading should play the ratchet.
  - In DevTools, call `oracleSound().whir(true)` twice and then `oracleSound().whir(false)`. It should go silent with no leftover loop.
- [ ] **Step 3:** Run a few greetings with Claude enabled. Neither the subtitles nor the voice should contain creak/whirr words.
- [ ] **Step 4:** Adjust `CLIP_GAIN` until the clips sit under her voice, then commit if anything changed: `git commit -am "Balance effect clip levels"`.
- [ ] **Step 5:** Restart with `ELEVENLABS_API_KEY=` blank. The log should show `sfx=0 clips`, and the same actions should play today's synth sounds with no console errors.
