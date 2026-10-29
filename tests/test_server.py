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


def test_endpoints_fall_back_without_claude():
    with TestClient(app_module.app) as client:
        cfg = client.get("/api/config").json()
        assert cfg["claude"] is False
        assert cfg["voice"] == "macos-say"
        assert set(cfg["stock"]) >= {"invite_adult", "invite_child", "farewell_child"}
        assert all(v["url"] for variants in cfg["stock"].values() for v in variants)
        assert len(cfg["stock"]["invite_adult"]) >= 2  # several wordings per line

        g = client.post("/api/greet", json={"image": FAKE_JPEG}).json()
        assert g["source"] == "fallback" and g["audience"] == "child"
        assert client.get(g["audio"]).status_code == 200

        f = client.post("/api/fortune", json={"image": FAKE_JPEG, "audience": "adult", "costume": "a pirate"}).json()
        assert f["source"] == "fallback" and f["audience"] == "adult"
        assert str(f["lucky_number"]) in f["spoken"]
        audio = client.get(f["audio"])
        assert audio.status_code == 200 and audio.content[:4] == b"RIFF"

        assert client.post("/api/print", json={k: v for k, v in f.items() if k != "audio"}).json()["status"] == "console"


def test_bad_requests():
    with TestClient(app_module.app) as client:
        assert client.post("/api/greet", json={"image": "nope"}).status_code == 400
        assert client.get("/api/audio/..%2F..%2Fserver%2Fconfig.py").status_code == 404


def test_unknown_audience_falls_back_to_child():
    f = asyncio.run(oracle.fortune("x" * 200, "", "", []))
    assert f.audience == "child"


def test_child_seen_at_greeting_stays_child(monkeypatch):
    async def fake_ask(schema, effort, max_tokens, content, timeout):
        return {
            "audience": "adult", "group_size": 1, "costume": "a tiny dragon", "spoken": "Doom awaits.",
            "card_title": "Doom", "card_text": "Doom.", "lucky_number": 13, "task": "Scream.", "gist": "doom",
        }

    monkeypatch.setattr(oracle, "_ask", fake_ask)
    f = asyncio.run(oracle.fortune("x" * 200, "child", "a tiny dragon", []))
    assert f.audience == "child"
    assert f.source == "claude"


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
    assert g.costume == "two ghosts" and g.source == "claude"
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


def test_refusal_uses_canned_line(monkeypatch):
    resp = types.SimpleNamespace(stop_reason="refusal", stop_details=types.SimpleNamespace(category=None), content=[])
    client, _ = _fake_client(resp)
    monkeypatch.setattr(oracle, "_CLIENT", client)
    assert asyncio.run(oracle.greet("x" * 200)).source == "fallback"


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

    real_client = httpx.AsyncClient
    monkeypatch.setattr(voice.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
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

    async def fake_fortune(image, audience, costume, recent, question="", paid_with=""):
        seen.update(question=question, paid_with=paid_with)
        return __import__("server.fallback_fortunes", fromlist=["x"]).fortune("adult", costume)

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


@pytest.mark.parametrize(
    "raw, clean",
    [
        ("*creak* Ah... a visitor.", "Ah... a visitor."),
        ("Creak... whirrr... Ah, a pirate! Come closer...", "Ah, a pirate! Come closer..."),
        ("Creak, creak! The gears wake.", "The gears wake."),
        ("Whirrr... the gears remember you.", "The gears remember you."),
        ("Hmm [gears grinding] your future glows.", "Hmm your future glows."),
        ("Your fate is sealed... clank! Beware the raven.", "Your fate is sealed... Beware the raven."),
        ("(a long hiss) Lucky seven.", "Lucky seven."),
        ("The gears whir in the dark... your ticket awaits.", "The gears whir in the dark... your ticket awaits."),
        ("*whirrr*", "*whirrr*"),
    ],
)
def test_scrub_spoken(raw, clean):
    assert oracle.scrub_spoken(raw) == clean


def test_claude_lines_are_scrubbed(monkeypatch):
    async def fake_ask(schema, *a, **k):
        if schema is oracle.GREET_SCHEMA:
            return {"audience": "adult", "group_size": 1, "costume": "a pirate", "greeting": "*creak* Ahoy... come closer."}
        return {
            "audience": "adult", "group_size": 1, "costume": "a pirate", "spoken": "Clank! Seven ravens.",
            "card_title": "The Raven", "card_text": "*whirr* Seven ravens.", "lucky_number": 7,
            "task": "Toast a ghost.", "gist": "ravens",
        }

    monkeypatch.setattr(oracle, "_ask", fake_ask)
    g = asyncio.run(oracle.greet("x" * 200))
    assert g.greeting == "Ahoy... come closer."
    f = asyncio.run(oracle.fortune("x" * 200, "adult", "a pirate", []))
    assert f.spoken == "Seven ravens." and f.card_text == "Seven ravens."


def test_persona_forbids_sound_effects():
    assert "Never write sound effects" in oracle.PERSONA


def _sfx_env(monkeypatch, tmp_path, key="k"):
    from server import sfx, voice
    monkeypatch.setattr(sfx.config, "SFX_DIR", tmp_path)
    monkeypatch.setattr(sfx.config, "ELEVENLABS_API_KEY", key)
    monkeypatch.setattr(voice, "RETRY_DELAYS_S", (0.01,))
    return sfx


_REAL_ASYNC_CLIENT = httpx.AsyncClient  # captured once, so mocking twice in a test doesn't nest


def _mock_eleven(monkeypatch, sfx, handler):
    mock = lambda **kw: _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), **kw)  # noqa: E731
    monkeypatch.setattr(sfx.httpx, "AsyncClient", mock)


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
