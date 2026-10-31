// Listening to the guest with Chrome's built-in speech recognition (no keys,
// but it needs internet). She only listens while she is silent, so she never
// transcribes her own voice. The operator can type what was said instead (the
// "/" key), which also covers a dead mic or a loud party.

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

export class Ears {
  constructor() {
    this.supported = !!SR;
    this.failed = null; // set when the mic or service is unusable; she stops trying
    this._current = null; // {finish(text)} for the listen in progress
  }

  get usable() {
    // A network hiccup gets another try after a while; a blocked mic does not.
    if (this.failed === "network" && performance.now() - this._failedAt > 30000) this.failed = null;
    return this.supported && !this.failed;
  }

  get listening() {
    return !!this._current;
  }

  // Resolves with what the guest said ("" if nothing). Stops on its own after
  // `silenceMs` of quiet once they've started talking, `waitMs` if they never
  // start, or `maxMs` total. Optional, for guests who need patience:
  // - `silenceMs` may be a function of what's been heard so far;
  // - `hold()` returning true stops the quiet clock (they're looking away);
  // - `confirm(text)` resolves true if the words so far are a finished
  //   thought; if not, she waits `moreMs` longer before giving up on more.
  //   It's asked a little before the pause is up, to hide its delay.
  listen({ maxMs = 12000, waitMs = 7000, silenceMs = 1600, moreMs = 6000, onHeard, hold, confirm } = {}) {
    this.cancel();
    return new Promise((resolve) => {
      let finalText = "";
      let interim = "";
      let rec = null;
      const started = performance.now();
      let activeAt = started; // last time they spoke, or were busy looking away
      let checking = false;
      let judged = null; // {text, done}: confirm()'s verdict on the words so far
      const text = () => `${finalText} ${interim}`.replace(/\s+/g, " ").trim();
      const finish = (override) => {
        if (this._current !== handle) return;
        this._current = null;
        clearInterval(poll);
        try {
          rec?.abort();
        } catch {
          /* already stopped */
        }
        resolve(override ?? text());
      };
      const handle = { finish };
      this._current = handle;
      const poll = setInterval(async () => {
        const now = performance.now();
        if (now - started > maxMs) return finish();
        if (hold?.()) {
          activeAt = now;
          return;
        }
        const t = text();
        const quiet = now - activeAt;
        if (!t) return quiet > waitMs && finish();
        const enough = typeof silenceMs === "function" ? silenceMs(t) : silenceMs;
        if (!confirm) return quiet >= enough && finish();
        if (judged?.text === t) return quiet >= enough + (judged.done ? 0 : moreMs) && finish();
        if (checking || quiet < Math.max(600, enough - 1500)) return;
        checking = true;
        const done = await confirm(t).catch(() => true);
        checking = false;
        judged = { text: t, done }; // stale (and ignored) if they carried on meanwhile
      }, 150);

      if (!SR) return; // typed input (inject) or the timers will finish it
      rec = new SR();
      rec.lang = "en-US";
      rec.continuous = true;
      rec.interimResults = true;
      rec.onresult = (e) => {
        interim = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const r = e.results[i];
          if (r.isFinal) finalText += ` ${r[0].transcript}`;
          else interim += ` ${r[0].transcript}`;
        }
        activeAt = performance.now();
        onHeard?.(text());
      };
      rec.onerror = (e) => {
        if (e.error !== "no-speech" && e.error !== "aborted") console.warn("speech recognition:", e.error);
        if (["not-allowed", "service-not-allowed", "audio-capture", "network"].includes(e.error)) {
          this.failed = e.error;
          this._failedAt = performance.now();
          finish();
        }
      };
      // Chrome ends sessions by itself now and then (more often during long
      // pauses); keep going until we finish, without losing half-heard words.
      rec.onend = () => {
        if (this._current !== handle) return;
        finalText += ` ${interim}`;
        interim = "";
        try {
          rec.start();
        } catch {
          finish();
        }
      };
      try {
        rec.start();
      } catch (e) {
        console.warn("speech recognition failed to start", e);
      }
    });
  }

  // Calls onLoud() once, when the room suddenly gets louder than it has been
  // (a howl, a "boo") for a quarter second: wordless sounds that speech
  // recognition may not transcribe. Returns a function that stops listening.
  watchLoud(onLoud, { factor = 3, holdMs = 250 } = {}) {
    let stopped = false;
    let stream, ctx, tick;
    const stop = () => {
      stopped = true;
      clearInterval(tick);
      stream?.getTracks().forEach((t) => t.stop());
      ctx?.close().catch(() => {});
    };
    navigator.mediaDevices
      .getUserMedia({ audio: { autoGainControl: false } })
      .then((s) => {
        stream = s;
        if (stopped) return stop();
        ctx = new AudioContext();
        const an = ctx.createAnalyser();
        an.fftSize = 1024;
        ctx.createMediaStreamSource(s).connect(an);
        const buf = new Float32Array(an.fftSize);
        const started = performance.now();
        let room = null; // the room's level, slowly following it
        let loudSince = 0;
        tick = setInterval(() => {
          an.getFloatTimeDomainData(buf);
          const rms = Math.sqrt(buf.reduce((sum, v) => sum + v * v, 0) / buf.length);
          const now = performance.now();
          room = room === null ? rms : room * 0.98 + rms * 0.02;
          if (now - started < 700 || rms < Math.max(room, 0.003) * factor) return void (loudSince = 0);
          loudSince ||= now;
          if (now - loudSince >= holdMs) {
            stop();
            onLoud();
          }
        }, 50);
      })
      .catch((e) => console.warn("mic level unavailable", e));
    return stop;
  }

  // Stop now and keep whatever has been heard so far.
  stop() {
    this._current?.finish();
  }

  // Operator typed what the guest said.
  inject(text) {
    this._current?.finish(text.trim());
  }

  cancel() {
    this._current?.finish("");
  }
}

export const wordCount = (s) => (s.trim() ? s.trim().split(/\s+/).length : 0);
