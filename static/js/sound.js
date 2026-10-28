// All sound is synthesized with WebAudio (no asset files), plus a "phonograph"
// chain the oracle's voice runs through. The voice analyser drives the jaw.

export class Sound {
  constructor() {
    this.ctx = new AudioContext();
    this.master = this.ctx.createGain();
    this.master.gain.value = 0.9;
    this.master.connect(this.ctx.destination);

    this.sfx = this.ctx.createGain();
    this.sfx.gain.value = 0.5;
    this.sfx.connect(this.master);

    this._buildVoiceChain();
    this._noise = this._makeNoise(2);
    this._buffers = new Map();
    this._loops = {};
  }

  async resume() {
    if (this.ctx.state !== "running") await this.ctx.resume();
  }

  // ---------- voice ----------

  _buildVoiceChain() {
    const c = this.ctx;
    this.voiceIn = c.createGain();
    const hp = c.createBiquadFilter();
    hp.type = "highpass";
    hp.frequency.value = 260;
    const lp = c.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 3600;
    const peak = c.createBiquadFilter();
    peak.type = "peaking";
    peak.frequency.value = 1400;
    peak.gain.value = 5;
    const shaper = c.createWaveShaper();
    shaper.curve = this._softClip(2.2);
    // Wow & flutter: a slowly wobbling delay bends the pitch like a worn record.
    const wobble = c.createDelay(0.05);
    wobble.delayTime.value = 0.012;
    const lfo = c.createOscillator();
    lfo.frequency.value = 0.7;
    const lfoDepth = c.createGain();
    lfoDepth.gain.value = 0.0012;
    lfo.connect(lfoDepth).connect(wobble.delayTime);
    lfo.start();
    this.voiceOut = c.createGain();
    this.voiceOut.gain.value = 1.4;
    this.analyser = c.createAnalyser();
    this.analyser.fftSize = 1024;
    this._level = new Float32Array(this.analyser.fftSize);

    this.voiceIn.connect(hp).connect(lp).connect(peak).connect(shaper).connect(wobble).connect(this.voiceOut);
    this.voiceOut.connect(this.master);
    // Analyse the dry signal so the jaw isn't fooled by crackle.
    this.voiceIn.connect(this.analyser);
  }

  _softClip(k) {
    const n = 1024;
    const curve = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const x = (i / (n - 1)) * 2 - 1;
      curve[i] = Math.tanh(k * x) / Math.tanh(k);
    }
    return curve;
  }

  // 0..1 loudness of the voice right now
  voiceLevel() {
    this.analyser.getFloatTimeDomainData(this._level);
    let sum = 0;
    for (const v of this._level) sum += v * v;
    return Math.min(1, Math.sqrt(sum / this._level.length) * 4);
  }

  async load(url) {
    if (!url) return null;
    if (this._buffers.has(url)) return this._buffers.get(url);
    const res = await fetch(url);
    if (!res.ok) throw new Error(`audio ${res.status}`);
    const buf = await this.ctx.decodeAudioData(await res.arrayBuffer());
    this._buffers.set(url, buf);
    return buf;
  }

  // Plays a voice clip. Returns a controller with pause()/resume()/progress()
  // and a `done` promise that resolves when the clip finishes (or is stopped).
  async speak(url) {
    const buf = await this.load(url);
    if (!buf) return null;
    const ctx = this.ctx;
    let src = null;
    let startedAt = 0;
    let offset = 0;
    let finished = false;
    let paused = false;
    let resolveDone;
    const done = new Promise((r) => (resolveDone = r));
    const crackle = this._crackle(buf.duration + 0.5);

    const start = () => {
      src = ctx.createBufferSource();
      src.buffer = buf;
      src.connect(this.voiceIn);
      src.onended = () => {
        if (src._paused) return;
        finished = true;
        crackle.stop();
        resolveDone();
      };
      startedAt = ctx.currentTime - offset;
      paused = false;
      src.start(0, offset);
    };
    start();

    return {
      duration: buf.duration,
      done,
      progress: () => (finished ? 1 : Math.min(1, (paused ? offset : ctx.currentTime - startedAt) / buf.duration)),
      pause: () => {
        if (finished || paused || !src) return;
        offset = ctx.currentTime - startedAt;
        paused = true;
        src._paused = true;
        src.stop();
      },
      resume: () => {
        if (!finished && paused) start();
      },
      stop: () => {
        if (finished) return;
        finished = true;
        if (src && !paused) {
          src._paused = true;
          src.stop();
        }
        crackle.stop();
        resolveDone();
      },
    };
  }

  // Sparse record-surface crackle under the voice.
  _crackle(seconds) {
    const ctx = this.ctx;
    const len = Math.ceil(seconds * ctx.sampleRate);
    const buf = ctx.createBuffer(1, len, ctx.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) {
      d[i] = (Math.random() * 2 - 1) * 0.015; // hiss
      if (Math.random() < 0.0004) d[i] += (Math.random() * 2 - 1) * 0.6; // pops
    }
    const src = ctx.createBufferSource();
    src.buffer = buf;
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = 2500;
    bp.Q.value = 0.5;
    const g = ctx.createGain();
    g.gain.value = 0.5;
    src.connect(bp).connect(g).connect(this.master);
    src.start();
    return { stop: () => src.stop() };
  }

  // ---------- sound effects ----------

  _makeNoise(seconds) {
    const len = seconds * this.ctx.sampleRate;
    const buf = this.ctx.createBuffer(1, len, this.ctx.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
    return buf;
  }

  _noiseSrc(loop = false) {
    const s = this.ctx.createBufferSource();
    s.buffer = this._noise;
    s.loop = loop;
    return s;
  }

  _env(gain, t, attack, hold, release, peak = 1) {
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(peak, t + attack);
    gain.gain.setValueAtTime(peak, t + attack + hold);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + attack + hold + release);
  }

  tick(pitch = 3200, vol = 0.5, when = 0) {
    const t = this.ctx.currentTime + when;
    const s = this._noiseSrc();
    const bp = this.ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = pitch;
    bp.Q.value = 8;
    const g = this.ctx.createGain();
    this._env(g, t, 0.001, 0.004, 0.03, vol);
    s.connect(bp).connect(g).connect(this.sfx);
    s.start(t, Math.random());
    s.stop(t + 0.06);
  }

  // Tick-tock of the clockwork while she's awake.
  clock(on) {
    clearInterval(this._loops.clock);
    if (!on) return;
    let tock = false;
    this._loops.clock = setInterval(() => {
      this.tick(tock ? 2100 : 2900, 0.18);
      tock = !tock;
    }, 500);
  }

  // Grinding gears: a lumpy low sawtooth plus gritty noise.
  grind(duration = 1.2, vol = 0.5) {
    const ctx = this.ctx;
    const t = ctx.currentTime;
    const osc = ctx.createOscillator();
    osc.type = "sawtooth";
    osc.frequency.setValueAtTime(38, t);
    for (let i = 1; i < 10; i++) osc.frequency.setValueAtTime(30 + Math.random() * 35, t + (duration * i) / 10);
    const am = ctx.createGain();
    const amOsc = ctx.createOscillator();
    amOsc.type = "square";
    amOsc.frequency.value = 14;
    const amDepth = ctx.createGain();
    amDepth.gain.value = 0.5;
    amOsc.connect(amDepth).connect(am.gain);
    am.gain.value = 0.5;
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 900;
    const n = this._noiseSrc(true);
    const nbp = ctx.createBiquadFilter();
    nbp.type = "bandpass";
    nbp.frequency.value = 1800;
    nbp.Q.value = 1.5;
    const ng = ctx.createGain();
    ng.gain.value = 0.25;
    const g = ctx.createGain();
    this._env(g, t, 0.05, duration - 0.2, 0.15, vol);
    osc.connect(lp).connect(am);
    n.connect(nbp).connect(ng).connect(am);
    am.connect(g).connect(this.sfx);
    for (const s of [osc, amOsc, n]) {
      s.start(t);
      s.stop(t + duration + 0.1);
    }
    // Ratcheting clicks on top
    for (let i = 0; i < duration * 9; i++) this.tick(1200 + Math.random() * 800, 0.35, i / 9 + Math.random() * 0.03);
  }

  // A servo creak: a resonant glide.
  creak(vol = 0.25) {
    const ctx = this.ctx;
    const t = ctx.currentTime;
    const osc = ctx.createOscillator();
    osc.type = "sawtooth";
    const f0 = 180 + Math.random() * 120;
    osc.frequency.setValueAtTime(f0, t);
    osc.frequency.linearRampToValueAtTime(f0 * (0.6 + Math.random() * 0.8), t + 0.35);
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = 1100;
    bp.Q.value = 12;
    const g = ctx.createGain();
    this._env(g, t, 0.02, 0.25, 0.1, vol);
    osc.connect(bp).connect(g).connect(this.sfx);
    osc.start(t);
    osc.stop(t + 0.45);
  }

  // Token drops into the slot: two metallic bounces and a clunk.
  coin() {
    const ctx = this.ctx;
    const ping = (when, vol) => {
      const t = ctx.currentTime + when;
      for (const [ratio, amp] of [[1, 1], [2.76, 0.5], [5.4, 0.25], [8.9, 0.12]]) {
        const o = ctx.createOscillator();
        o.frequency.value = 1850 * ratio;
        const g = ctx.createGain();
        this._env(g, t, 0.001, 0.0, 0.5 / ratio + 0.1, vol * amp);
        o.connect(g).connect(this.sfx);
        o.start(t);
        o.stop(t + 0.8);
      }
    };
    ping(0, 0.35);
    ping(0.14, 0.2);
    ping(0.22, 0.1);
    // clunk
    const t = ctx.currentTime + 0.45;
    const o = ctx.createOscillator();
    o.frequency.setValueAtTime(140, t);
    o.frequency.exponentialRampToValueAtTime(50, t + 0.15);
    const g = ctx.createGain();
    this._env(g, t, 0.002, 0.02, 0.15, 0.6);
    o.connect(g).connect(this.sfx);
    o.start(t);
    o.stop(t + 0.3);
    this.tick(900, 0.6, 0.45);
  }

  // Card dispenser: a fast ratchet.
  ratchet(seconds = 1.6) {
    for (let i = 0; i < seconds * 22; i++) this.tick(1500 + (i % 2) * 400, 0.3, i / 22);
  }

  // Busy machinery while she consults the spirits.
  whir(on) {
    const l = this._loops;
    if (l.whir) {
      const { nodes, gain } = l.whir;
      gain.gain.setTargetAtTime(0.0001, this.ctx.currentTime, 0.15);
      setTimeout(() => nodes.forEach((n) => n.stop()), 600);
      l.whir = null;
    }
    clearInterval(l.whirTicks);
    if (!on) return;
    const ctx = this.ctx;
    const n = this._noiseSrc(true);
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = 700;
    bp.Q.value = 3;
    const sweep = ctx.createOscillator();
    sweep.frequency.value = 0.4;
    const sweepDepth = ctx.createGain();
    sweepDepth.gain.value = 400;
    sweep.connect(sweepDepth).connect(bp.frequency);
    const hum = ctx.createOscillator();
    hum.type = "triangle";
    hum.frequency.value = 55;
    const humG = ctx.createGain();
    humG.gain.value = 0.4;
    const gain = ctx.createGain();
    gain.gain.value = 0.0001;
    gain.gain.setTargetAtTime(0.35, ctx.currentTime, 0.2);
    n.connect(bp).connect(gain);
    hum.connect(humG).connect(gain);
    gain.connect(this.sfx);
    [n, sweep, hum].forEach((s) => s.start());
    l.whir = { nodes: [n, sweep, hum], gain };
    l.whirTicks = setInterval(() => this.tick(2600 + Math.random() * 600, 0.15), 125);
  }

  // A faint, out-of-tune music box waltz for the idle attract loop.
  musicBox(on) {
    clearTimeout(this._loops.music);
    if (!on) return;
    // A minor, 3/4. Semitones from A4; null is a rest.
    const melody = [0, 3, 7, 12, 7, 3, 5, 8, 12, 8, 5, null, 2, 5, 8, 11, 8, 5, 3, 7, 10, 7, 3, null];
    let i = 0;
    const step = () => {
      const note = melody[i % melody.length];
      if (note !== null) this._bell(440 * Math.pow(2, note / 12) * (1 + (Math.random() - 0.5) * 0.006));
      i++;
      this._loops.music = setTimeout(step, 420);
    };
    step();
  }

  _bell(freq, vol = 0.07) {
    const ctx = this.ctx;
    const t = ctx.currentTime;
    for (const [ratio, amp] of [[1, 1], [2, 0.3], [3.01, 0.12]]) {
      const o = ctx.createOscillator();
      o.type = "sine";
      o.frequency.value = freq * ratio;
      const g = ctx.createGain();
      this._env(g, t, 0.003, 0, 1.4 / ratio, vol * amp);
      o.connect(g).connect(this.sfx);
      o.start(t);
      o.stop(t + 1.6);
    }
  }

  // "Your turn to speak": a single clear bell.
  cue() {
    this._bell(1318.5, 0.12);
    setTimeout(() => this._bell(1975.5, 0.08), 140);
  }

  // Sparkly shimmer when the crystal ball lights.
  shimmer() {
    for (let i = 0; i < 9; i++) {
      setTimeout(() => this._bell(1760 * Math.pow(2, [0, 4, 7, 11, 12, 16, 19, 23, 24][i] / 12), 0.04), i * 60);
    }
  }
}
