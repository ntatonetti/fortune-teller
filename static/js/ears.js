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
  // start, or `maxMs` total.
  listen({ maxMs = 12000, waitMs = 7000, silenceMs = 1600, onHeard } = {}) {
    this.cancel();
    return new Promise((resolve) => {
      let finalText = "";
      let interim = "";
      let rec = null;
      let silenceTimer = null;
      const timers = [];
      const text = () => `${finalText} ${interim}`.replace(/\s+/g, " ").trim();
      const finish = (override) => {
        if (this._current !== handle) return;
        this._current = null;
        timers.forEach(clearTimeout);
        clearTimeout(silenceTimer);
        try {
          rec?.abort();
        } catch {
          /* already stopped */
        }
        resolve(override ?? text());
      };
      const handle = { finish };
      this._current = handle;
      timers.push(setTimeout(() => finish(), maxMs));
      timers.push(setTimeout(() => !text() && finish(), waitMs));

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
        onHeard?.(text());
        clearTimeout(silenceTimer);
        silenceTimer = setTimeout(() => finish(), silenceMs);
      };
      rec.onerror = (e) => {
        if (e.error !== "no-speech" && e.error !== "aborted") console.warn("speech recognition:", e.error);
        if (["not-allowed", "service-not-allowed", "audio-capture", "network"].includes(e.error)) {
          this.failed = e.error;
          this._failedAt = performance.now();
          finish();
        }
      };
      // Chrome ends sessions by itself now and then; keep going until we finish.
      rec.onend = () => {
        if (this._current !== handle) return;
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
