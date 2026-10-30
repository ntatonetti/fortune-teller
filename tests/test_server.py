import asyncio
import base64
import json
import types

import httpx
import pytest
from fastapi.testclient import TestClient

from server import app as app_module
from server import oracle, printer
from server.memory import GuestLog
from server.models import Fortune

FAKE_JPEG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8" + b"x" * 400).decode()
_REAL_ASYNC_CLIENT = httpx.AsyncClient  # captured once, so mocking twice in a test doesn't nest
PIRATE = dict(
    audience="adult", group_size=1, costume="a pirate", spoken="Arr... 7.", card_title="The Omen of the Tide",
    card_text="Beware the tide.", lucky_number=7, task="Find a parrot.", gist="tide omen",
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch, tmp_path):
    """No real Claude (calls return None unless a test fakes them) and a fake ElevenLabs."""
    from server import config, voice

    monkeypatch.setattr(oracle, "_CLIENT", None)
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "tts")
    fake = lambda req: httpx.Response(200, content=b"ID3fake-mp3")  # noqa: E731
    monkeypatch.setattr(voice.httpx, "AsyncClient", lambda **kw: _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(fake), **kw))


def test_endpoints_when_claude_is_down():
    with TestClient(app_module.app) as client:
        cfg = client.get("/api/config").json()
        assert cfg["flickers"] == 3
        assert cfg["flicker_opacity"] == 0.8
        assert cfg["timings"]["wake_hold"] == 0.7 and cfg["timings"]["glitch_at_min"] == 0.3
        assert set(cfg["stock"]) >= {"invite_adult", "invite_child", "farewell_child"}
        assert all(v["url"] for variants in cfg["stock"].values() for v in variants)
        assert len(cfg["stock"]["invite_adult"]) >= 2  # several wordings per line
        audio = client.get(cfg["stock"]["invite_adult"][0]["url"])
        assert audio.status_code == 200 and audio.content[:3] == b"ID3"

        # No canned stand-ins: the page handles these (no greeting, "the spirits are silent").
        assert client.post("/api/greet", json={"image": FAKE_JPEG}).status_code == 503
        assert client.post("/api/fortune", json={"image": FAKE_JPEG, "audience": "adult"}).status_code == 503
        assert client.post("/api/asked", json={"question": "will I"}).status_code == 503

        assert client.post("/api/print", json=PIRATE).json()["status"] == "console"


def test_wont_start_without_keys(monkeypatch):
    monkeypatch.setattr(app_module.config, "ELEVENLABS_VOICE_ID", "")
    with pytest.raises(RuntimeError, match="ELEVENLABS_VOICE_ID"):
        with TestClient(app_module.app):
            pass


def test_asked_checks_with_a_quick_model(monkeypatch):
    seen = {}

    async def fake_ask(schema, effort, max_tokens, content, timeout, model=None, system=oracle.PERSONA):
        seen.update(model=model, system=system, text=content[0]["text"])
        return {"done": "puppy" in content[0]["text"]}

    monkeypatch.setattr(oracle, "_ask", fake_ask)
    with TestClient(app_module.app) as client:
        assert client.post("/api/asked", json={"question": "will I um", "kid": True}).json() == {"done": False}
        assert "A child is asking." in seen["text"] and "<heard>will I um</heard>" in seen["text"]
        assert client.post("/api/asked", json={"question": "will I get a puppy"}).json() == {"done": True}
    assert seen["model"] == "claude-haiku-5-5" and seen["system"] == oracle.ASKED_SYSTEM
    assert "An adult is asking." in seen["text"]


def test_bad_requests():
    with TestClient(app_module.app) as client:
        assert client.post("/api/greet", json={"image": "nope"}).status_code == 400
        assert client.get("/api/audio/..%2F..%2Fserver%2Fconfig.py").status_code == 404


def test_child_seen_at_greeting_stays_child(monkeypatch):
    async def fake_ask(schema, effort, max_tokens, content, timeout):
        return {
            "audience": "adult", "group_size": 1, "costume": "a tiny dragon", "spoken": "Doom awaits.",
            "card_title": "Doom", "card_text": "Doom.", "lucky_number": 13, "task": "Scream.", "gist": "doom",
        }

    monkeypatch.setattr(oracle, "_ask", fake_ask)
    f = asyncio.run(oracle.fortune("x" * 200, "child", "a tiny dragon", []))
    assert f.audience == "child"


def test_prompt_includes_child_note_and_memory(monkeypatch):
    seen = {}

    async def fake_ask(schema, effort, max_tokens, content, timeout):
        seen["text"] = content[1]["text"]
        return None

    monkeypatch.setattr(oracle, "_ask", fake_ask)
    guests = [{"costume": "a vampire", "audience": "adult", "gist": "beware the garlic"}]
    asyncio.run(oracle.fortune("x" * 200, "mixed", "a bumblebee", guests))
    assert "CHILD mode no matter what" in seen["text"]
    assert "a vampire" in seen["text"]


class _FakeClient:
    def __init__(self, msgs):
        self.beta = types.SimpleNamespace(messages=msgs)
        self.timeouts = []

    def with_options(self, timeout):
        self.timeouts.append(timeout)
        return self


class _FakeMessages:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def _fake_client(response):
    msgs = _FakeMessages(response)
    return _FakeClient(msgs), msgs


def test_ask_request_shape_and_parse(monkeypatch):
    payload = {"audience": "adult", "group_size": 2, "costume": "two ghosts", "greeting": "Boo... come closer."}
    resp = types.SimpleNamespace(
        stop_reason="end_turn", stop_details=None, content=[types.SimpleNamespace(type="text", text=json.dumps(payload))]
    )
    client, msgs = _fake_client(resp)
    monkeypatch.setattr(oracle, "_CLIENT", client)
    monkeypatch.setattr(oracle.config, "CLAUDE_MODEL", "claude-opus-5-5")
    g = asyncio.run(oracle.greet("x" * 200))
    assert g.costume == "two ghosts"
    kw = msgs.kwargs
    assert kw["model"] == "claude-opus-5-5"
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert kw["output_config"]["format"]["type"] == "json_schema"
    assert kw["messages"][0]["content"][0]["type"] == "image"
    assert client.timeouts == [oracle.config.GREET_TIMEOUT_S]


def test_no_fallback_param_for_haiku(monkeypatch):
    resp = types.SimpleNamespace(stop_reason="end_turn", stop_details=None, content=[])
    client, msgs = _fake_client(resp)
    monkeypatch.setattr(oracle, "_CLIENT", client)
    monkeypatch.setattr(oracle.config, "CLAUDE_MODEL", "claude-haiku-5-5")
    asyncio.run(oracle.greet("x" * 200))
    assert "fallbacks" not in msgs.kwargs


def test_refusal_gives_no_greeting(monkeypatch):
    resp = types.SimpleNamespace(stop_reason="refusal", stop_details=types.SimpleNamespace(category=None), content=[])
    client, _ = _fake_client(resp)
    monkeypatch.setattr(oracle, "_CLIENT", client)
    assert asyncio.run(oracle.greet("x" * 200)) is None


def test_card_fits_paper():
    f = Fortune(
        audience="adult", group_size=1, costume="c", spoken="s", card_title="The Omen of the Extraordinarily Crooked Hat",
        card_text="word " * 40, lucky_number=7, task="Find the person in green and whisper a secret to them.", gist="g",
    )
    for width in (32, 48):
        assert all(len(line) <= width for line in printer.card_lines(f, width))


def test_guest_log_persists(tmp_path):
    path = tmp_path / "g.json"
    log = GuestLog(path, max_age_s=3600)
    log.add("a witch", "adult", "beware brooms", lucky=7)
    assert GuestLog(path, max_age_s=3600).recent(5)[0]["costume"] == "a witch"
    log.clear()
    assert GuestLog(path, max_age_s=3600).count() == 0


def test_old_guests_are_forgotten(tmp_path):
    path = tmp_path / "g.json"
    path.write_text(json.dumps([
        {"t": 0, "costume": "last week's vampire", "audience": "adult", "gist": "old"},
        {"t": __import__("time").time(), "costume": "tonight's witch", "audience": "adult", "gist": "new"},
    ]))
    log = GuestLog(path, max_age_s=12 * 3600)
    assert [g["costume"] for g in log.recent(10)] == ["tonight's witch"]
    assert log.count() == 1


def test_forget_everyone_endpoint():
    with TestClient(app_module.app) as client:
        app_module.guests.add("a ghost", "adult", "boo")
        assert client.get("/api/config").json()["guests"] >= 1
        assert client.delete("/api/guests").json() == {"cleared": True}
        assert client.get("/api/config").json()["guests"] == 0


def test_variety_steers_away_from_repeats(monkeypatch):
    from server import variety

    seen = {}

    async def fake_ask(schema, effort, max_tokens, content, timeout):
        seen["text"] = content[1]["text"]
        return None

    monkeypatch.setattr(oracle, "_ask", fake_ask)
    recent = [
        {"costume": "a pirate", "audience": "adult", "gist": "g", "title": "The Omen of the Tide", "lucky": n,
         "task": "Find a stranger.", "opener": "Ahh... the gears turn and I see"}
        for n in range(1, 99)  # every number but 99 (13 is in here too) already used
    ]
    asyncio.run(oracle.fortune("x" * 200, "adult", "a witch", recent))
    assert "Their lucky number is 99." in seen["text"]
    assert "Ahh... the gears turn and I see" in seen["text"] and "Do not reuse" in seen["text"]
    assert "Read it from " in seen["text"]
    assert all(variety.pick_sign(kid=True).replace("the tarot card ", "") in variety.TAROT_FOR_KIDS + variety.SIGNS_FOR_KIDS for _ in range(50))


def test_elevenlabs_rate_limit_is_retried_and_queued(monkeypatch):
    import httpx

    from server import voice

    calls = {"n": 0, "active": 0, "peak": 0}

    async def handler(request):
        calls["n"] += 1
        calls["active"] += 1
        calls["peak"] = max(calls["peak"], calls["active"])
        await asyncio.sleep(0.01)
        calls["active"] -= 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"detail": "too_many_concurrent_requests"})
        return httpx.Response(200, content=b"ID3fake-mp3")

    monkeypatch.setattr(voice.httpx, "AsyncClient", lambda **kw: _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(voice, "RETRY_DELAYS_S", (0.01, 0.01))
    monkeypatch.setattr(voice, "_eleven_slots", asyncio.Semaphore(2))

    async def many():
        return await asyncio.gather(*(voice._eleven(f"line {i}") for i in range(6)))

    results = asyncio.run(many())
    assert all(r == b"ID3fake-mp3" for r in results)  # the 429 was retried, not dropped
    assert calls["peak"] <= 2  # never more than 2 requests in flight


def test_question_and_payment_reach_the_prompt(monkeypatch):
    seen = {}

    async def fake_ask(schema, effort, max_tokens, content, timeout):
        seen["text"] = content[1]["text"]
        return {
            "audience": "adult", "group_size": 1, "costume": "a pirate", "spoken": "Yes... the treasure is yours.",
            "card_title": "The Buried Answer", "card_text": "Dig where the parrot sleeps.", "lucky_number": 8,
            "task": "Ask the witch for a map.", "gist": "treasure ahead",
        }

    monkeypatch.setattr(oracle, "_ask", fake_ask)
    f = asyncio.run(oracle.fortune("x" * 200, "adult", "a pirate", [], question="Will I find treasure?", paid_with="secret"))
    assert "<question>Will I find treasure?</question>" in seen["text"]
    assert "whispering you a secret" in seen["text"]
    assert f.question == "Will I find treasure?"

    asyncio.run(oracle.fortune("x" * 200, "adult", "a pirate", [], paid_with="coin"))
    assert "gold coin" in seen["text"] and "<question>" not in seen["text"]


def test_secret_text_is_never_accepted_or_logged(monkeypatch):
    seen = {}

    async def fake_fortune(image, audience, costume, recent, question="", paid_with="", max_words=0):
        seen.update(question=question, paid_with=paid_with)
        return Fortune(**PIRATE)

    monkeypatch.setattr(app_module.oracle, "fortune", fake_fortune)
    with TestClient(app_module.app) as client:
        body = {"image": FAKE_JPEG, "audience": "adult", "paid_with": "secret", "secret": "I ate the last cupcake"}
        f = client.post("/api/fortune", json=body).json()
    assert seen["paid_with"] == "secret"
    assert "cupcake" not in json.dumps(seen) and "cupcake" not in json.dumps(f)


def test_card_prints_the_question():
    f = Fortune(
        audience="adult", group_size=1, costume="c", spoken="s", card_title="The Answer", card_text="Yes.",
        lucky_number=3, task="Dance.", gist="g", question="Will my sourdough starter survive the winter " * 3,
    )
    lines = printer.card_lines(f, 32)
    assert "You asked:" in lines
    assert all(len(line) <= 32 for line in lines)
    assert any("…" in line for line in lines)  # long questions are shortened


def test_persona_forbids_sound_effects():
    assert "Never write sound effects" in oracle.PERSONA


def _sfx_env(monkeypatch, tmp_path, key="k"):
    from server import sfx
    monkeypatch.setattr(sfx.config, "SFX_DIR", tmp_path)
    monkeypatch.setattr(sfx.config, "ELEVENLABS_API_KEY", key)
    return sfx


_REAL_CLIENT = httpx.Client  # captured once, so mocking twice in a test doesn't nest


def _mock_eleven(monkeypatch, sfx, handler):
    monkeypatch.setattr(sfx.httpx, "Client", lambda **kw: _REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))


def test_sfx_generate_makes_every_variant_with_loop_only_for_whir_and_ball(monkeypatch, tmp_path):
    sfx = _sfx_env(monkeypatch, tmp_path)
    seen = []

    def handler(req):
        assert req.url.path == "/v1/sound-generation" and req.headers["xi-api-key"] == "k"
        seen.append(json.loads(req.content))
        return httpx.Response(200, content=b"ID3sfx")

    _mock_eleven(monkeypatch, sfx, handler)
    sfx.generate()
    looped = {p for name in ("whir", "ball") for p, _ in sfx.EFFECTS[name]}
    assert len(seen) == sum(len(v) for v in sfx.EFFECTS.values())
    assert all(b["loop"] == (b["text"] in looped) for b in seen)
    assert all(0.5 <= b["duration_seconds"] <= 30 and b["model_id"] == "eleven_text_to_sound_v2" for b in seen)
    assert set(sfx.available()) == set(sfx.EFFECTS)


def test_sfx_rerun_requests_only_missing_clips(monkeypatch, tmp_path):
    sfx = _sfx_env(monkeypatch, tmp_path)
    creak = {p for p, _ in sfx.EFFECTS["creak"]}
    _mock_eleven(monkeypatch, sfx, lambda req: httpx.Response(500 if json.loads(req.content)["text"] in creak else 200, content=b"ID3"))
    sfx.generate()  # a failed clip is skipped, not fatal
    assert "creak" not in sfx.available() and "coin" in sfx.available()
    second = []
    _mock_eleven(monkeypatch, sfx, lambda req: second.append(json.loads(req.content)["text"]) or httpx.Response(200, content=b"ID3"))
    sfx.generate()
    assert sorted(second) == sorted(creak)


def test_sfx_missing_permission_stops_after_one_request(monkeypatch, tmp_path):
    sfx = _sfx_env(monkeypatch, tmp_path)
    calls = []
    _mock_eleven(monkeypatch, sfx, lambda req: calls.append(1) or httpx.Response(401, json={"detail": {"status": "missing_permissions"}}))
    with pytest.raises(SystemExit, match="Sound Effects permission"):
        sfx.generate()
    assert calls == [1]


def test_sfx_stale_clips_are_ignored_and_pruned(monkeypatch, tmp_path):
    sfx = _sfx_env(monkeypatch, tmp_path)
    prompt, dur = sfx.EFFECTS["coin"][0]
    current = tmp_path / sfx.filename("coin", 0, prompt, dur)
    current.write_bytes(b"ID3")
    (tmp_path / "coin-0-deadbeef00.mp3").write_bytes(b"old")
    assert sfx.available() == {"coin": [f"/sfx/{current.name}"]}
    assert sfx.prune() == ["coin-0-deadbeef00.mp3"]
    assert [p.name for p in tmp_path.iterdir()] == [current.name]


def test_committed_clips_are_advertised_and_served():
    client = TestClient(app_module.app)
    clips = client.get("/api/config").json()["sfx"]
    assert set(clips) == {"creak", "grind", "whir", "coin", "ratchet", "ball"}  # run scripts/make_sfx.py if this fails
    r = client.get(clips["whir"][0])
    assert r.status_code == 200 and r.content[:3] == b"ID3"


def test_usb_ticket_is_plain_ascii_and_cut(monkeypatch):
    from escpos import printer as escpos_printer

    made = {}

    def fake_usb(vendor, product, **kw):
        made.update(kw, vendor=vendor, product=product)
        made["dummy"] = escpos_printer.Dummy()
        return made["dummy"]

    monkeypatch.setattr(escpos_printer, "Usb", fake_usb)
    monkeypatch.setattr(printer.config, "PRINTER_WIDTH_CHARS", 48)
    f = Fortune(
        audience="adult", group_size=1, costume="c", spoken="s", card_title="The “Crooked” Hat",
        card_text="The cat’s whiskers twitch—and then… silence.", lucky_number=7,
        task="Say ‘boo’ to a ghost.", gist="g", question="Will it rain? " * 10,
    )
    printer._print_usb(f)

    out = made["dummy"].output
    assert (made["in_ep"], made["out_ep"]) == (0x81, 0x01)
    text = bytes(b for b in out if 0x20 <= b < 0x7F).decode()
    assert "cat's whiskers twitch--and then... silence." in text
    assert '"CROOKED" HAT' in text and "'boo'" in text
    assert not any(b >= 0x80 for b in out)  # no codepage-dependent bytes for the punctuation
    assert b"\x1dV" in out  # paper is cut (GS V)


def test_signature_lines_are_offered_and_kids_only_get_kid_lines(monkeypatch):
    from server import phrases

    seen = []

    async def fake_ask(schema, effort, max_tokens, content, timeout):
        seen.append(content[1]["text"])
        return None

    monkeypatch.setattr(oracle, "_ask", fake_ask)
    adult_lines = [l for lines in phrases.ADULT.values() for _, l in lines]
    kid_lines = [l for lines in phrases.KIDS.values() for _, l in lines]

    asyncio.run(oracle.greet("x" * 200))
    assert sum(l in seen[-1] for _, l in phrases.GREETING) == 3

    asyncio.run(oracle.fortune("x" * 200, "adult", "a pirate", []))
    assert sum(l in seen[-1] for l in adult_lines) == 4
    assert not any(l in seen[-1] for l in kid_lines)

    asyncio.run(oracle.fortune("x" * 200, "child", "a tiny dragon", []))
    assert sum(l in seen[-1] for l in kid_lines) == 4
    assert not any(l in seen[-1] for l in adult_lines)


def test_signature_line_odds():
    import random
    from collections import Counter

    from server import phrases

    rng = random.Random(1)
    lines = [(0, "never"), (1, "rare"), (9, "common"), (5, "fill")]
    counts = Counter(l for _ in range(2000) for l in phrases._pick(lines, 2, rng))
    assert counts["never"] == 0
    assert counts["common"] > 2 * counts["rare"]
    assert phrases._pick([(0, "off"), (2, "on")], 2, rng) == ["on"]
