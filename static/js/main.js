// The show: a state machine that runs one reading at a time.
//   sleep -> wake (looks at you) -> greet -> invite (gold coin or a whispered secret)
//   -> ask (listens for their question) -> consult -> speak -> dispense -> farewell -> sleep

import { Ears, wordCount } from "./ears.js";
import { HeadMap } from "./headmap.js";
import { Puppet } from "./puppet.js";
import { Sound } from "./sound.js";
import { Watcher } from "./watcher.js";

const $ = (id) => document.getElementById(id);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const between = (lo, hi) => lo + Math.random() * (hi - lo);

const DEFAULTS = {
  cameraId: "",
  display: "screen", // screen (sheet/wall) | head (foam head + globe)
  mirror: false, // flip everything for rear projection if the projector can't
  subtitles: true,
  headSubtitles: false, // in head mode the projector should only light her
  music: true,
  invertEyes: false,
  near: 0.11, // face width (fraction of frame) that counts as "at the booth"
  button: true, // false = start the reading automatically after the invite
  listen: true, // hear secrets and questions through the mic
  audience: "auto", // auto | adult | child (manual override)
  glitchRate: 0.2, // chance an adult reading has a mechanical seizure
  walkAwayS: 8, // no face for this long mid-reading = they left; she shuts down
};
const settings = { ...DEFAULTS, ...JSON.parse(localStorage.getItem("oracle-settings") || "{}") };
const save = () => localStorage.setItem("oracle-settings", JSON.stringify(settings));

const puppet = new Puppet($("stage"));
const headmap = new HeadMap($("headLayers"));
puppet.headmap = headmap;
const watcher = new Watcher($("camera"));
const ears = new Ears();
let sound = null;
let server = { stock: {} };
// Every pause, wait and transition, in seconds, from .env via /api/config.
let T = {};
const ms = (name) => T[name] * 1000;

let state = "boot";
let reading = null; // {audience, kid, costume, fortune}
let tokenWaiter = null;
let farewellAt = 0;
// The guest whose reading just ended, followed by place and costume colours so
// they don't wake her again but anyone else does: {x, y, w, colours, at, alike}.
let lastGuest = null;
let lastFaceAt = 0;
// Walk-away detection: only once the camera has seen this guest, so a dark
// booth where faces aren't detected never cuts a real reading short.
class WalkedAway extends Error {}
let walkedAway = false;
let seenThisSession = false;
const stillHere = () => {
  if (walkedAway) throw new WalkedAway();
};
let nearSince = 0;
let farSince = 0;
let lastBeckon = 0;
let sleepTalk = null; // what she's mumbling in her sleep, if anything
let nextSleepTalk = 0;
let dazedUntil = 0; // woken with a start: looking about, not at them yet
let faceSince = 0; // asleep: when the face in view first appeared
let forceGlitch = false;
let speaking = null; // current voice controller
let subtitle = { words: [], ctrl: null };
let debug = false;
// Debug: ?brief in the URL caps her greeting and fortune at 20 words (?brief=30 for 30),
// so testing the guest's side isn't spent listening to her. Never saved.
const briefParam = new URLSearchParams(location.search).get("brief");
const maxWords = briefParam === null ? 0 : Number(briefParam) || 20;

// ---------------- helpers ----------------

async function api(path, body) {
  const res = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: body ? { "content-type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${path} ${res.status}`);
  return res.json();
}

function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 1600);
}

function setPrompt(text) {
  $("prompt").textContent = text || "";
}

function applyMirror() {
  document.body.classList.toggle("mirror", settings.mirror);
  headmap.apply();
}

const headMode = () => settings.display === "head";
const subtitlesOn = () => (headMode() ? settings.headSubtitles : settings.subtitles);

function applyDisplay() {
  const head = headMode();
  puppet.mode = settings.display;
  headmap.show(head);
  document.body.classList.toggle("head", head);
  if (!head && headmap.aligning) headmap.setAligning(false);
  $("displaySelect").value = settings.display;
}

// Speak a clip with subtitles. Resolves when she's done talking.
let sayCount = 0;
async function say(url, text, { glitch = false } = {}) {
  const myTurn = ++sayCount;
  if (subtitlesOn() && text) {
    subtitle.words = text.split(/\s+/);
    $("subtitle").textContent = "";
    $("subtitle").classList.add("show");
  }
  let ctrl = null;
  try {
    ctrl = url ? await sound.speak(url) : null;
  } catch (e) {
    console.warn("voice failed", e);
  }
  if (!ctrl) {
    // No audio: let the text sit there for a natural reading time.
    const d = ms("no_voice_word") * subtitle.words.length;
    subtitle.ctrl = { progress: ((t0) => () => clamp((performance.now() - t0) / d, 0, 1))(performance.now()) };
    await wait(d + 300);
  } else {
    speaking = ctrl;
    subtitle.ctrl = ctrl;
    if (glitch) {
      const at = ctrl.duration * between(T.glitch_at_min, T.glitch_at_max) * 1000;
      setTimeout(async () => {
        if (speaking !== ctrl) return;
        ctrl.pause();
        puppet.glitch(T.glitch);
        sound.grind(T.glitch - 0.2, 0.6);
        await wait(ms("glitch"));
        ctrl.resume();
      }, at);
    }
    await ctrl.done;
    speaking = null;
  }
  subtitle.ctrl = null;
  setTimeout(() => {
    if (sayCount === myTurn) $("subtitle").classList.remove("show");
  }, ms("subtitle_linger"));
}

// Pick one of a stock line's wordings, never the same one twice in a row.
const lastStock = {};
function sayStock(key, opts) {
  const options = server.stock?.[key] || [];
  if (!options.length) return say(null, "", opts);
  let i = Math.floor(Math.random() * options.length);
  if (options.length > 1 && i === lastStock[key]) i = (i + 1) % options.length;
  lastStock[key] = i;
  return say(options[i].url, options[i].text, opts);
}

const listening = () => settings.listen && ears.usable;

// Show what she hears, as it's heard (screen mode, or head mode with subtitles on).
function showHeard(text, { secret = false } = {}) {
  lastFaceAt = performance.now(); // someone talking is someone here
  if (!subtitlesOn()) return;
  const el = $("subtitle");
  el.classList.add("show", "heard");
  // A secret is shown as a row of dots, never as words.
  el.textContent = secret ? "· ".repeat(Math.min(12, wordCount(text) || 1)).trim() : `“${text}”`;
}

function clearHeard() {
  $("subtitle").classList.remove("show", "heard");
}

// Payment: the button (they dropped a gold coin) or a whispered secret.
// Resolves "coin", "secret", or null if they walked away or timed out.
function waitForPayment(timeoutMs) {
  let finish;
  const promise = new Promise((resolve) => {
    let done = false;
    const started = performance.now();
    const check = setInterval(() => {
      const now = performance.now();
      if (now - started > timeoutMs || walkedAway) finish(null);
    }, 250);
    finish = (v) => {
      if (done) return;
      done = true;
      clearInterval(check);
      tokenWaiter = null;
      ears.cancel();
      resolve(v);
    };
    tokenWaiter = () => finish("coin");
  });
  // Call once she has finished speaking, so she never hears herself.
  promise.listenForSecret = async () => {
    while (listening() && tokenWaiter) {
      const t0 = performance.now();
      const heard = await ears.listen({ maxMs: ms("secret_listen"), waitMs: ms("secret_listen"), onHeard: (t) => showHeard(t, { secret: true }) });
      if (ears.failed) toast(`Mic unavailable (${ears.failed}): coins only. Press / to type for guests.`);
      if (performance.now() - t0 < 1000) await wait(1000); // don't spin if recognition keeps bailing
      if (wordCount(heard) >= 2) {
        // The words are dropped right here: nothing about the secret leaves the browser.
        finish("secret");
        return;
      }
    }
  };
  return promise;
}

// Last words that mean they're mid-sentence ("will I...", "um...", "and..."), not done.
const TRAILING = new Set(
  "um uh er erm hmm like and or but so because if the a an my your his her their our to of for with about will would should could can do does did is are am was what when where who why how which i i'm me going gonna wanna maybe then".split(" "),
);

// How long a pause ends their question: longer for kids, and longer still if
// they've barely started or trailed off mid-sentence.
function questionPause(text, kid) {
  const words = text.toLowerCase().replace(/[^a-z' ]/g, " ").split(/\s+/).filter(Boolean);
  const trailing = words.length < 3 || TRAILING.has(words.at(-1));
  return ms(kid ? "question_pause_kid" : "question_pause") + (trailing ? ms("question_trailing") : 0);
}

// She asks for their question and listens, patiently: the clock stops while
// they look away (asking a friend, say), and at each pause Claude judges
// whether the question is finished. Resolves with the question ("" if none).
async function askQuestion(kid) {
  if (!listening()) return "";
  state = "ask";
  await sayStock(kid ? "ask_child" : "ask_adult");
  stillHere();
  sound.cue();
  setPrompt("✦ speak your question ✦");
  puppet.set({ brow: 1, lidL: 1, lidR: 1 });
  const question = await ears.listen({
    maxMs: ms("question_max"),
    waitMs: ms(kid ? "question_start_kid" : "question_start"),
    moreMs: ms("question_more"),
    silenceMs: (t) => questionPause(t, kid),
    hold: () => seenThisSession && (!watcher.nearest || watcher.lookingAway),
    confirm: (t) => api("/api/asked", { question: t, kid }).then((r) => r.done),
    onHeard: (t) => showHeard(t),
  });
  stillHere();
  setPrompt("");
  if (question) showHeard(question);
  await wait(ms("heard_show"));
  clearHeard();
  await sayStock(question ? (kid ? "heard_child" : "heard_adult") : kid ? "no_question_child" : "no_question_adult");
  stillHere();
  return question;
}

function onToken() {
  lastFaceAt = performance.now(); // a hand on the button is someone here
  if (state === "sleep") {
    session({ paid: true });
  } else if (tokenWaiter) {
    tokenWaiter();
  } else if (state === "ask" && ears.listening) {
    ears.stop(); // the button means "that's my question"
  }
}

// ---------------- the reading ----------------

async function session(opts = {}) {
  if (state !== "sleep") return;
  walkedAway = false;
  seenThisSession = false;
  lastFaceAt = performance.now();
  lastGuest = null;
  try {
    await runReading(opts);
  } catch (e) {
    if (!(e instanceof WalkedAway)) console.error("reading failed", e);
    await shutDown(e instanceof WalkedAway);
  }
}

// Snorted awake: she looks about, blinks, mutters, then finds them.
async function wakeStartled() {
  dazedUntil = performance.now() + ms("wake_dazed") + 4000; // the mutter ends it sooner
  sound.snort();
  puppet.set({ brow: 1, eyeX: 0, turn: 0 });
  const looks = [-0.8, 0.7, -0.3];
  const each = ms("wake_dazed") / (looks.length + 1);
  for (const x of looks) {
    await wait(each);
    puppet.set({ eyeX: x, eyeY: -0.2, turn: x * 0.5, lidL: 0.6, lidR: 0.8 });
  }
  await wait(each / 2);
  puppet.set({ lidL: 0.1, lidR: 0.1 }); // a slow blink
  await wait(each / 2);
  puppet.set({ lidL: 1, lidR: 1 });
  await sayStock("wake_startled");
  dazedUntil = 0;
}

// They left mid-reading (or something broke): stop everything and go to sleep.
async function shutDown(walked) {
  state = "farewell"; // out of the reading, so the grumble isn't itself cut off
  tokenWaiter = null;
  ears.cancel();
  speaking?.stop();
  sound.whir(false);
  puppet.flicker = false;
  clearHeard();
  setPrompt("");
  puppet.glitch(T.shutdown_glitch);
  sound.grind(T.shutdown_glitch + 0.3, 0.4);
  walkedAway = false; // let the grumble play
  if (walked) await sayStock(reading?.kid ? "walkaway_child" : "walkaway_adult");
  await sleepAgain();
}

async function runReading({ paid = false } = {}) {
  state = "wake";
  stopSleepTalk();
  setPrompt("");
  sound.musicBox(false);
  sound.grind(1.5);
  sound.clock(true);
  puppet.set({ dim: 0, lidL: 1, lidR: 1, brow: 1 });
  puppet.gearTarget = 0.6;
  puppet.ballTarget = 0.45;
  sound.ball(0.45);

  const shot = watcher.snapshot();
  puppet.setGuestFace(watcher.faceCrop());
  const [greet] = await Promise.all([
    shot ? api("/api/greet", { image: shot, max_words: maxWords }).catch((e) => (console.warn(e), null)) : null,
    wait(ms("wake_pause")),
    Math.random() < T.wake_startle ? wakeStartled() : null,
  ]);
  stillHere();

  if (greet && greet.audience === "nobody" && !paid) {
    // She woke for a shadow. Grumble and go back to sleep.
    await sayStock("rewind");
    return sleepAgain();
  }
  let audience = greet?.audience && greet.audience !== "nobody" ? greet.audience : "child";
  if (settings.audience !== "auto") audience = settings.audience;
  const kid = audience === "child" || audience === "mixed";
  const showFace = !kid || !!server.kid_flicker; // kids see their face in hers only with KID_FLICKER
  if (!showFace) puppet.guestFace = null;
  reading = { audience, kid, costume: greet?.costume || "", fortune: null, paidWith: paid ? "coin" : "", question: "" };
  puppet.set({ brow: kid ? 1 : 0.4 });

  state = "greet";
  if (greet?.greeting) await say(greet.audio, greet.greeting);
  stillHere();

  if (!paid) {
    state = "invite";
    setPrompt(listening() ? "✦ a gold coin… or a secret ✦" : "✦ insert your gold coin ✦");
    const payment = waitForPayment(ms("pay_timeout"));
    payment.then((v) => v && speaking?.stop()); // paying mid-sentence cuts her off
    await sayStock(kid ? "invite_child" : "invite_adult");
    if (!settings.button && !listening()) tokenWaiter?.();
    payment.listenForSecret();
    const paidWith = await payment;
    setPrompt("");
    clearHeard();
    stillHere();
    if (!paidWith) return sleepAgain();
    reading.paidWith = paidWith;
  }

  if (reading.paidWith === "secret") {
    sound.shimmer();
    await sayStock(kid ? "secret_child" : "secret_adult");
  } else {
    sound.coin();
    await wait(ms("coin_pause"));
  }
  stillHere();
  reading.question = await askQuestion(kid);
  await consultAndSpeak();
}

async function consultAndSpeak() {
  const { kid } = reading;
  state = "consult";
  setPrompt("✦ the spirits are consulted ✦");
  sound.whir(true);
  sound.shimmer();
  puppet.gearTarget = 2.6;
  puppet.ballTarget = 1;
  sound.ball(1);
  // Adults get the eyes rolled up into the head; kids see her gaze into the ball.
  puppet.set(kid ? { eyeX: 0, eyeY: 1, lidL: 0.6, lidR: 0.6 } : { eyeX: 0, eyeY: -1, lidL: 0.35, lidR: 0.35 });
  puppet.trance = !kid;
  // Her face and the guest's flicker back and forth while the spirits answer
  // (for kids only with KID_FLICKER).
  const showFace = !kid || !!server.kid_flicker;
  if (showFace) puppet.setGuestFace(watcher.faceCrop());
  puppet.flicker = showFace;

  const shot = watcher.snapshot();
  const started = performance.now();
  const fortuneP = shot
    ? api("/api/fortune", {
        image: shot,
        audience: reading.audience,
        costume: reading.costume,
        question: reading.question,
        paid_with: reading.paidWith,
        max_words: maxWords,
      }).catch((e) => (console.warn(e), null))
    : Promise.resolve(null);
  await sayStock(kid ? "consult_child" : "consult_adult");
  stillHere();
  const f = await fortuneP;
  const left = ms("consult_min") - (performance.now() - started);
  if (left > 0) await wait(left);
  stillHere();

  sound.whir(false);
  puppet.flicker = false;
  puppet.trance = false;
  puppet.gearTarget = 0.6;
  puppet.ballTarget = 0.55;
  sound.ball(0.55);
  puppet.set({ lidL: 1, lidR: 1 });
  setPrompt("");

  if (!f) {
    await sayStock("silent");
    return sleepAgain();
  }
  reading.fortune = f;
  const kidNow = kid || f.audience === "child" || f.audience === "mixed";
  state = "speak";
  const glitch = !kidNow && (forceGlitch || Math.random() < settings.glitchRate);
  forceGlitch = false;
  await say(f.audio, f.spoken, { glitch });
  stillHere(); // left mid-fortune: no ticket

  state = "dispense";
  sound.ratchet(1.6);
  api("/api/print", f).catch((e) => console.warn("print failed", e));
  await wait(ms("ticket_pause"));
  stillHere();
  await sayStock(kidNow ? "farewell_child" : "farewell_adult");
  await sleepAgain();
}

async function sleepAgain() {
  state = "farewell";
  sound.clock(false);
  sound.creak();
  puppet.flicker = false;
  puppet.trance = false;
  puppet.guestFace = null; // forget their face
  puppet.set({ dim: 1, lidL: 1, lidR: 1, brow: 0, turn: 0, eyeX: 0, eyeY: 0 }); // asleep: just dimmed
  puppet.gearTarget = 0.15;
  puppet.ballTarget = 0.15;
  sound.ball(0); // asleep: the music box plays alone
  await wait(ms("fall_asleep"));
  state = "sleep";
  farewellAt = performance.now();
  nextSleepTalk = farewellAt + (T.sleep_talk > 0 ? sleepTalkGap(4) : 0);
  nearSince = 0;
  farSince = 0;
  setPrompt("✦ approach the glass ✦");
  if (settings.music) sound.musicBox(true);
}

// ---------------- per-frame logic ----------------

function lookAt(face, now) {
  if (!face) return;
  const dir = settings.invertEyes ? -1 : 1;
  // The camera faces the guest, so their left is the image's right.
  const ex = clamp((0.5 - face.x) * 2.4 * dir, -1, 1);
  const ey = clamp((face.y - 0.45) * 2, -1, 1) * 0.7;
  puppet.set({ eyeX: ex, eyeY: ey, turn: ex * 0.6 });
}

// During a reading the nearest face is the guest: learn their place and colours.
function noteGuest(f, now) {
  const colours = watcher.colours(f);
  if (!colours) return;
  const was = lastGuest?.colours;
  if (was) for (let i = 0; i < 64; i++) was[i] += (colours[i] - was[i]) * 0.02; // averaged over about a second
  lastGuest = { x: f.x, y: f.y, w: f.w, colours: was || colours, at: now, alike: 1 };
}

// After the reading: the face that is still the last guest (about where they
// were, about their size, their costume's colours), or null. Once they've been
// out of sight for REWAKE_GONE they're forgotten.
function followLastGuest(now) {
  const g = lastGuest;
  if (!g) return null;
  if (now - g.at > ms("rewake_gone")) return (lastGuest = null);
  let best = null;
  for (const f of watcher.faces) {
    const size = f.w / g.w;
    if (size < 0.6 || size > 1.7 || Math.hypot(f.x - g.x, f.y - g.y) > Math.max(f.w, g.w) * 1.5) continue;
    const alike = Watcher.alike(watcher.colours(f), g.colours);
    if (!best || alike > best.alike) best = { f, alike };
  }
  if (best) g.alike = best.alike;
  if (!best || best.alike < T.same_guest) return null;
  Object.assign(g, { x: best.f.x, y: best.f.y, w: best.f.w, at: now });
  return best.f;
}

function sleepLogic(now) {
  const face = watcher.nearest;
  if (face) lastFaceAt = now;
  if (lastGuest && now - farewellAt > ms("rewake_anyway")) lastGuest = null; // lingered: greet them again

  // Anyone at the booth but the guest who just left wakes her, even while they're still there.
  const theirs = followLastGuest(now);
  const newcomer = watcher.faces.some((f) => f !== theirs && f.w >= settings.near);
  const near = face && face.w >= settings.near;
  if (newcomer) {
    nearSince ||= now;
    if (now - nearSince > ms("wake_hold")) {
      nearSince = 0;
      session();
      return;
    }
  } else nearSince = 0;

  // Someone lingering at a distance: her eyes follow them.
  if (face && !near) {
    farSince ||= now;
    if (now - farSince > ms("peek_after")) lookAt(face, now);
    if (now - farSince > ms("beckon_after") && now - lastBeckon > ms("beckon_every") && !lastGuest) {
      lastBeckon = now;
      sound.musicBox(false);
      sayStock("beckon").then(() => state === "sleep" && settings.music && sound.musicBox(true));
    }
  } else if (farSince) {
    farSince = 0;
    puppet.set({ eyeX: 0, eyeY: 0, turn: 0 });
  }

  // Talk in her sleep while no one is about; hush once someone is (a face for a
  // moment, not a stray flicker of detection).
  if (face) {
    faceSince ||= now;
    if (now - faceSince > 300) stopSleepTalk();
  } else {
    faceSince = 0;
    if (!sleepTalk && T.sleep_talk > 0 && now > nextSleepTalk) talkInSleep();
  }
}

// The quiet gap after sleep talk that lasted `seconds`, so she talks for about
// SLEEP_TALK of the time she's alone.
const sleepTalkGap = (seconds) => seconds * 1000 * (1 / T.sleep_talk - 1) * between(0.5, 1.5);

async function talkInSleep() {
  const lines = server.stock?.sleeptalk || [];
  const line = lines[Math.floor(Math.random() * lines.length)];
  const claim = (sleepTalk = {});
  const talk = line?.url ? await sound.sleepTalk(line.url, Math.random() < T.sleep_mumble).catch(() => null) : null;
  if (!talk) {
    if (sleepTalk === claim) sleepTalk = null;
    nextSleepTalk = performance.now() + sleepTalkGap(4);
    return;
  }
  if (sleepTalk !== claim || state !== "sleep") return talk.stop(); // hushed while it loaded
  sleepTalk = talk;
  await talk.done;
  if (sleepTalk === talk) sleepTalk = null;
  nextSleepTalk = performance.now() + sleepTalkGap(talk.duration);
}

function stopSleepTalk() {
  sleepTalk?.stop?.();
  sleepTalk = null;
}

let padWasDown = false;
function pollGamepads() {
  let down = false;
  for (const pad of navigator.getGamepads?.() || []) {
    if (pad && pad.buttons.some((b) => b.pressed)) down = true;
  }
  if (down && !padWasDown) onToken();
  padWasDown = down;
}

function drawDebug() {
  const box = $("debug");
  box.hidden = !debug;
  if (!debug) return;
  const cv = $("debugCanvas");
  const c = cv.getContext("2d");
  const v = watcher.video;
  c.fillStyle = "#000";
  c.fillRect(0, 0, cv.width, cv.height);
  if (v.videoWidth) c.drawImage(v, 0, 0, cv.width, cv.height);
  for (const f of watcher.faces) {
    c.strokeStyle = f === watcher.nearest ? (f.w >= settings.near ? "#0f0" : "#ff0") : "#888";
    c.lineWidth = 2;
    c.strokeRect((f.x - f.w / 2) * cv.width, (f.y - f.h / 2) * cv.height, f.w * cv.width, f.h * cv.height);
  }
  const n = watcher.nearest;
  $("debugText").textContent = [
    `state: ${state}`,
    `face: ${n ? `w=${n.w.toFixed(3)} (near ≥ ${settings.near}) · turn=${(n.turn ?? 0).toFixed(2)}${watcher.lookingAway ? " AWAY" : ""}` : "none"}`,
    `audience: ${reading?.audience || "-"} ${settings.audience !== "auto" ? `(forced ${settings.audience})` : ""}`,
    `ears: ${!ears.supported ? "unsupported in this browser" : ears.failed ? `failed (${ears.failed})` : settings.listen ? (ears.listening ? "LISTENING" : "on") : "off"} · paid: ${reading?.paidWith || "-"}`,
    `question: ${reading?.question || "-"}`,
    `walk-away: ${inReading() ? `${((performance.now() - lastFaceAt) / 1000).toFixed(1)}s` : "-"} / ${settings.walkAwayS}s${inReading() && !seenThisSession ? " (face not seen yet: off)" : ""}`,
    `costume: ${reading?.costume || "-"}`,
    `last guest: ${lastGuest ? `alike ${lastGuest.alike.toFixed(2)} (same ≥ ${T.same_guest}) · seen ${((performance.now() - lastGuest.at) / 1000).toFixed(1)}s ago` : "-"}`,
    `printer: ${server.printer}${maxWords ? ` · brief: ${maxWords} words` : ""}`,
    `button: ${settings.button ? "required" : "auto"} · glitch: ${Math.round(settings.glitchRate * 100)}% · guests: ${server.guests ?? "?"}`,
  ].join("\n");
}

const inReading = () => ["wake", "greet", "invite", "ask", "consult", "speak", "dispense"].includes(state);

function frame(now) {
  watcher.update(now);
  pollGamepads();
  if (state === "sleep") sleepLogic(now);
  else if (state === "farewell") followLastGuest(now);
  else if (inReading()) {
    if (watcher.nearest) {
      lastFaceAt = now;
      seenThisSession = true;
      noteGuest(watcher.nearest, now);
      if (state !== "consult" && now > dazedUntil) lookAt(watcher.nearest, now);
    }
    const away = now - lastFaceAt;
    if (seenThisSession && !walkedAway && settings.walkAwayS > 0 && away > settings.walkAwayS * 1000) {
      walkedAway = true;
      // Cut off whatever she is waiting on so the reading notices right away.
      speaking?.stop();
      ears.cancel();
    }
  }
  puppet.preview = headmap.aligning;
  puppet.setJaw(speaking ? sound.voiceLevel() : 0);
  puppet.frame(now);
  if (subtitle.ctrl) {
    const n = Math.ceil(subtitle.ctrl.progress() * subtitle.words.length * 1.1);
    $("subtitle").textContent = subtitle.words.slice(0, n).join(" ");
  }
  drawDebug();
  requestAnimationFrame(frame);
}

// ---------------- setup & keys ----------------

const KEYS = {
  " ": () => onToken(),
  Enter: () => onToken(),
  w: () => state === "sleep" && session(),
  d: () => (debug = !debug),
  m: () => toggle("mirror", "Mirror", applyMirror),
  s: () => toggle(headMode() ? "headSubtitles" : "subtitles", "Subtitles"),
  v: () => {
    settings.display = headMode() ? "screen" : "head";
    save();
    applyDisplay();
    toast(`Display: ${headMode() ? "foam head" : "screen"}`);
  },
  c: () => {
    if (!headMode()) return toast("Alignment is for head mode: press V first");
    headmap.setAligning(true);
  },
  n: () => toggle("music", "Music box", () => state === "sleep" && sound.musicBox(settings.music)),
  i: () => toggle("invertEyes", "Invert eye tracking"),
  b: () => toggle("button", "Button required"),
  l: () => toggle("listen", "Listening (mic)"),
  "/": () => typeForGuest(),
  g: () => {
    forceGlitch = true;
    toast("Next adult reading will glitch");
  },
  a: () => {
    const order = ["auto", "adult", "child"];
    settings.audience = order[(order.indexOf(settings.audience) + 1) % order.length];
    save();
    toast(`Audience: ${settings.audience}`);
  },
  j: () => adjustWalkAway(-1),
  k: () => adjustWalkAway(1),
  "[": () => adjustNear(-0.01),
  "]": () => adjustNear(0.01),
  f: () => (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen()),
  h: () => ($("help").hidden = !$("help").hidden),
  Escape: () => openSetup(),
};

// Operator fallback: type what the guest said (noisy party, dead mic).
function typeForGuest() {
  if (!ears.listening) return toast("She isn't listening right now");
  // window.prompt blocks; the listen's own timers resume when it closes.
  const what = state === "invite" ? "the guest's secret (it is not saved)" : "the guest's question";
  const text = window.prompt(`Type ${what}:`);
  if (text) ears.inject(text);
}

function toggle(key, label, after) {
  settings[key] = !settings[key];
  save();
  toast(`${label}: ${settings[key] ? "on" : "off"}`);
  after?.();
}

function adjustWalkAway(d) {
  settings.walkAwayS = clamp(settings.walkAwayS + d, 3, 30);
  save();
  toast(`Walk away: she gives up after ${settings.walkAwayS}s without a face`);
}

function adjustNear(d) {
  settings.near = Math.round(clamp(settings.near + d, 0.03, 0.5) * 100) / 100;
  save();
  toast(`Wake distance: face width ≥ ${settings.near}`);
}

window.addEventListener("keydown", (e) => {
  if ($("setup").hidden === false && e.key !== "Escape") return;
  if (headmap.handleKey(e)) return;
  const fn = KEYS[e.key] || KEYS[e.key.toLowerCase()];
  if (fn) {
    e.preventDefault();
    if (!e.repeat) fn();
  }
});

// The server's settings, into her.
function applyServer() {
  puppet.flickers = server.flickers ?? 3;
  puppet.flickerWhere = server.flicker_where ?? "ball";
  puppet.guestAlpha = server.flicker_opacity ?? 1;
  if (server.timings) puppet.timing = T = { ...puppet.timing, ...server.timings }; // her defaults fill any gaps
}

async function refreshServer() {
  try {
    server = await api("/api/config");
  } catch {
    server = { stock: {}, printer: "?" };
  }
  applyServer();
  document.title = server.name || "The Oracle";
  $("title").textContent = server.name || "The Oracle";
  const st = $("status");
  st.innerHTML = "";
  for (const [label, ok, detail] of [
    ["Server", !!server.name, server.name ? "running" : "not reachable"],
    ["Printer", server.printer === "usb", server.printer],
  ]) {
    const li = document.createElement("li");
    li.className = ok ? "ok" : "warn";
    li.textContent = `${label}: ${detail}`;
    st.appendChild(li);
  }
  // Her memory of tonight's guests, and the way to wipe it before the party.
  const mem = document.createElement("li");
  mem.className = "ok";
  const n = server.guests ?? 0;
  mem.textContent = `Memory: ${n ? `${n} guest${n === 1 ? "" : "s"} remembered` : "empty"} `;
  if (n) {
    const btn = document.createElement("button");
    btn.className = "forget";
    btn.textContent = "Forget everyone";
    btn.onclick = async () => {
      if (!window.confirm(`Make her forget all ${n} remembered guest${n === 1 ? "" : "s"}?`)) return;
      await fetch("/api/guests", { method: "DELETE" });
      refreshServer();
    };
    mem.appendChild(btn);
  }
  st.appendChild(mem);
  showSettings(server.settings || []);
}

// Every .env setting that changes how she behaves: its value, editable, and
// what it does. Edits are saved into .env when she's awakened.
function showSettings(list) {
  const box = $("settingsList");
  box.innerHTML = "";
  let section = null;
  for (const setting of list) {
    const { section: sec, name, value, about } = setting;
    if (sec !== section) {
      section = sec;
      const h = document.createElement("h3");
      h.textContent = sec;
      box.appendChild(h);
    }
    const row = document.createElement(setting.kind === "voices" ? "div" : "label");
    row.className = "row";
    const code = document.createElement("code");
    code.textContent = name;
    const cell = document.createElement("span");
    cell.className = "value";
    cell.append(...control(setting));
    const unit = name.endsWith("_S") ? "s" : name.endsWith("_H") ? "h" : "";
    if (unit) cell.append(` ${unit}`);
    const what = document.createElement("span");
    what.className = "about";
    what.textContent = about;
    row.append(code, cell, what);
    box.appendChild(row);
    // The longer story, folded away under the row (not inside it: a click in a
    // label would also flip its checkbox).
    if (setting.detail) {
      const more = el("details", { className: "more" });
      more.append(
        el("summary", { textContent: "What this does" }),
        el("p", { textContent: setting.detail }),
        el("p", { className: "eg", textContent: `Example: ${setting.example}` }),
      );
      box.appendChild(more);
    }
  }
  fillVoiceChoice();
  $("settings").hidden = !list.length;
}

const el = (tag, props = {}) => Object.assign(document.createElement(tag), props);

// The input(s) a setting is edited with. The one carrying its name holds the
// value; dataset.was is the value it started with.
function control({ name, value, choices, range, kind }) {
  if (typeof value === "boolean") {
    const box = el("input", { type: "checkbox", name, checked: value });
    box.dataset.was = String(value);
    return [box];
  }
  if (kind === "voice") return voiceChoice(name, value);
  if (kind === "voices") return voiceList(name, value);
  if (choices) {
    const sel = el("select", { name });
    for (const c of choices.includes(value) ? choices : [value, ...choices]) sel.append(el("option", { value: c, textContent: c }));
    sel.value = value;
    sel.dataset.was = value;
    return [sel];
  }
  if (range) {
    // A slider over the usual span, and the number itself, which can go past it.
    const [min, max, step] = range;
    const slider = el("input", { type: "range", min, max, step, value, tabIndex: -1 });
    const num = el("input", { type: "text", name, inputMode: "decimal", spellcheck: false, value: String(value) });
    num.dataset.was = num.value;
    slider.setAttribute("aria-label", `${name} slider`);
    slider.addEventListener("input", () => (num.value = slider.value));
    num.addEventListener("input", () => {
      const n = parseFloat(num.value);
      if (Number.isFinite(n)) slider.value = clamp(n, min, max);
    });
    return [slider, num];
  }
  const input = el("input", { type: "text", name, spellcheck: false, className: "words", value: String(value) });
  input.dataset.was = input.value;
  return [input];
}

// Her voice: picked with "Use this voice" on the list below; this shows its name.
function voiceChoice(name, value) {
  const input = el("input", { type: "hidden", name, value, className: "voice" });
  input.dataset.was = value;
  input.dataset.want = value;
  return [input, el("span", { className: "voiceNow" })];
}

// Her voice comes from the list (which always has the one she has); remove it
// and she takes the first voice left. The row she uses is marked.
function fillVoiceChoice(want) {
  const input = $("settingsList").querySelector("input.voice");
  if (!input) return;
  if (want) input.dataset.want = want;
  const voices = readVoices();
  if (!voices.some((v) => v.id === input.dataset.want)) input.dataset.want = voices[0]?.id || input.dataset.was;
  input.value = input.dataset.want;
  input.parentElement.querySelector(".voiceNow").textContent = voices.find((v) => v.id === input.value)?.name || input.value;
  for (const r of $("settingsList").querySelectorAll(".voices .voiceRow")) {
    const using = r.querySelector(".vid").textContent === input.value;
    r.classList.toggle("using", using);
    const use = r.querySelector(".use");
    use.disabled = using;
    use.textContent = using ? "In use" : "Use this voice";
  }
}

// VOICES: a row per voice (name, id, Hear, Remove) and a row to add one. A
// hidden input carries the list as the .env text, Name=voice id, comma between.
function voiceList(name, value) {
  const text = (vs) => vs.map((v) => `${v.name}=${v.id}`).join(", ");
  const hidden = el("input", { type: "hidden", name, value: text(value) });
  hidden.dataset.was = hidden.value;
  // The voice she has is always listed, to keep or remove like the others, and
  // saved into VOICES with the rest, so it stays listed after she switches.
  const has = server.settings?.find((s) => s.kind === "voice")?.value;
  if (has && !value.some((v) => v.id === has)) value = [{ name: "Original", id: has }, ...value];
  hidden.value = text(value);
  const list = el("span", { className: "voices" });
  const sync = () => {
    hidden.value = text(readVoices(list));
    fillVoiceChoice();
  };
  const addRow = ({ name: vName, id }) => {
    const r = el("span", { className: "voiceRow" });
    const n = el("input", { type: "text", value: vName, spellcheck: false, className: "vname" });
    n.setAttribute("aria-label", "voice name");
    n.addEventListener("input", sync);
    const i = el("code", { textContent: id, className: "vid" });
    const hear = el("button", { type: "button", className: "small", textContent: "Hear" });
    hear.addEventListener("click", () => hearVoice(id, hear));
    const use = el("button", { type: "button", className: "small use", textContent: "Use this voice" });
    use.addEventListener("click", () => fillVoiceChoice(id));
    const drop = el("button", { type: "button", className: "small", textContent: "Remove" });
    drop.addEventListener("click", () => {
      if (list.children.length > 1) r.remove(), sync(); // she needs one voice
    });
    r.append(n, i, hear, use, drop);
    list.append(r);
  };
  value.forEach(addRow);
  const adder = el("span", { className: "voiceRow adder" });
  const n = el("input", { type: "text", placeholder: "Name", spellcheck: false, className: "vname" });
  const i = el("input", { type: "text", placeholder: "ElevenLabs voice ID", spellcheck: false, className: "vidIn" });
  n.setAttribute("aria-label", "new voice name");
  i.setAttribute("aria-label", "new voice ID");
  const add = el("button", { type: "button", className: "small", textContent: "Add voice" });
  add.addEventListener("click", () => {
    const vName = n.value.replace(/[=,]/g, " ").trim();
    const id = i.value.trim();
    if (!vName || !/^[A-Za-z0-9]{10,40}$/.test(id)) {
      $("settingsError").textContent = "A voice needs a name and its ElevenLabs voice ID (letters and digits).";
      $("settingsError").hidden = false;
      return;
    }
    $("settingsError").hidden = true;
    addRow({ name: vName, id });
    n.value = i.value = "";
    sync();
  });
  adder.append(n, i, add);
  return [hidden, list, adder];
}

// The voices as listed on the start screen right now.
function readVoices(list = $("settingsList").querySelector(".voices")) {
  if (!list) return [];
  return [...list.querySelectorAll(".voiceRow")].map((r) => ({
    name: r.querySelector(".vname").value.replace(/[=,]/g, " ").trim() || "Unnamed",
    id: r.querySelector(".vid").textContent,
  }));
}

async function hearVoice(id, button) {
  button.disabled = true;
  button.textContent = "…";
  try {
    const res = await fetch("/api/voice/sample", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ voice_id: id }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || res.status);
    $("settingsError").hidden = true;
    await new Audio(body.url).play();
  } catch (e) {
    $("settingsError").textContent = `Couldn't play that voice: ${e.message}`;
    $("settingsError").hidden = false;
  } finally {
    button.disabled = false;
    button.textContent = "Hear";
  }
}

// The settings changed on the start screen, as {NAME: "text"}.
function editedSettings() {
  const out = {};
  for (const input of $("settingsList").querySelectorAll("[name]")) {
    const now = input.type === "checkbox" ? String(input.checked) : input.value.trim();
    if (now !== input.dataset.was) out[input.name] = now;
  }
  return out;
}

// Save the start screen's edits into .env and reload every setting (hand edits
// to .env too), so this session runs on them. False if one was refused.
async function saveSettings() {
  const edits = editedSettings();
  const btn = $("beginBtn");
  const label = btn?.textContent;
  if (btn && ("ELEVENLABS_VOICE_ID" in edits || "ELEVENLABS_MODEL" in edits)) {
    btn.disabled = true;
    btn.textContent = "Teaching her the new voice…";
  }
  const res = await fetch("/api/settings", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ values: edits }),
  }).catch(() => null);
  if (btn) {
    btn.disabled = false;
    btn.textContent = label;
  }
  if (!res) return true; // server unreachable: carry on with what she has
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({}));
    $("settingsError").textContent = `Not saved: ${detail || res.status}`;
    $("settingsError").hidden = false;
    return false;
  }
  $("settingsError").hidden = true;
  server = await res.json();
  applyServer();
  showSettings(server.settings || []);
  return true;
}

async function fillCameras() {
  const sel = $("cameraSelect");
  try {
    // Labels only show up after permission is granted once.
    const tmp = await navigator.mediaDevices.getUserMedia({ video: true });
    tmp.getTracks().forEach((t) => t.stop());
  } catch (e) {
    console.warn("camera permission", e);
  }
  const cams = await Watcher.cameras();
  sel.innerHTML = "";
  for (const cam of cams) {
    const o = document.createElement("option");
    o.value = cam.deviceId;
    o.textContent = cam.label || `Camera ${sel.length + 1}`;
    if (cam.deviceId === settings.cameraId) o.selected = true;
    sel.appendChild(o);
  }
  if (!cams.length) sel.innerHTML = "<option value=''>No camera found</option>";
}

function openSetup() {
  $("setup").hidden = false;
  refreshServer();
  fillCameras();
}

async function begin() {
  if (!(await saveSettings())) return;
  if (state === "boot") document.documentElement.requestFullscreen?.().catch(() => {});
  settings.cameraId = $("cameraSelect").value;
  settings.display = $("displaySelect").value;
  save();
  applyDisplay();
  $("setup").hidden = true;
  sound ||= new Sound();
  await sound.resume();
  if (settings.listen && ears.supported) {
    // Ask for the mic now, at setup, rather than in the middle of a reading.
    try {
      (await navigator.mediaDevices.getUserMedia({ audio: true })).getTracks().forEach((t) => t.stop());
    } catch (e) {
      toast("Microphone blocked: she won't hear guests (press L to stop trying)");
    }
  }
  try {
    await watcher.start(settings.cameraId);
  } catch (e) {
    console.error(e);
    toast("Camera unavailable. Press the button to start readings.");
  }
  // Warm the stock lines so the first reading has no stalls.
  Object.values(server.stock || {})
    .flat()
    .forEach((s) => s.url && sound.load(s.url).catch(() => {}));
  await sound.loadEffects(server.sfx || {}); // before she settles, so even the first creak is a clip
  if (state === "boot") await sleepAgain();
}

$("beginBtn").addEventListener("click", begin);
window.oracleState = () => state; // for scripts/smoke.py
window.oracleHear = (text) => ears.inject(text); // ditto: stands in for the mic
window.oracleListening = () => ears.listening;
window.oracleFakeFace = (f) => (watcher.fake = f); // a face for tests; undefined = real camera
window.oracleSound = () => sound; // for poking effects from DevTools
applyMirror();
applyDisplay();
refreshServer();
fillCameras();
requestAnimationFrame(frame);
