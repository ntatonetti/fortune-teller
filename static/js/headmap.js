// Head mode surfaces: the face and the crystal ball are each drawn on their own
// canvas and corner-pinned onto the real objects (a foam head, a frosted globe).
// Her room (the background of her photograph) can go on a third one, behind them,
// pinned onto the backdrop; it's off until switched on in alignment mode.
// Alignment mode lets you drag corners with the mouse or nudge with keys.

import { cornerPinMatrix, cssMatrix } from "./homography.js";

const STORE = "oracle-headmap";

// Logical size of each surface canvas (CSS px before warping).
// First is drawn first, so the background sits under the face and ball.
export const SURFACES = {
  bg: { w: 688, h: 384, label: "BACKGROUND" }, // half her 1376 x 768 photograph
  face: { w: 400, h: 520, label: "FACE" },
  ball: { w: 360, h: 360, label: "BALL" },
};

// Where the drawn face's features sit; tuned per foam head in alignment mode.
export const DEFAULT_GEOM = { eyeSpread: 1, eyeY: 0, eyeSize: 1, mouthY: 0 };

function defaultCorners(name) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const { w, h } = SURFACES[name];
  if (name === "bg") {
    // fill the screen, as her photograph does on the sheet
    const k = Math.max(vw / w, vh / h);
    const [x, y] = [(vw - w * k) / 2, (vh - h * k) / 2];
    return [
      [x, y],
      [x + w * k, y],
      [x + w * k, y + h * k],
      [x, y + h * k],
    ];
  }
  const s = name === "face" ? (vh * 0.5) / h : (vh * 0.28) / h;
  const cx = vw / 2;
  const cy = name === "face" ? vh * 0.36 : vh * 0.78;
  const hw = (w * s) / 2;
  const hh = (h * s) / 2;
  return [
    [cx - hw, cy - hh],
    [cx + hw, cy - hh],
    [cx + hw, cy + hh],
    [cx - hw, cy + hh],
  ];
}

export class HeadMap {
  constructor(container) {
    this.container = container;
    this.surfaces = {};
    for (const [name, spec] of Object.entries(SURFACES)) {
      const canvas = document.createElement("canvas");
      canvas.className = "surface";
      canvas.width = spec.w * 2; // 2x for crispness after the warp
      canvas.height = spec.h * 2;
      canvas.style.width = `${spec.w}px`;
      canvas.style.height = `${spec.h}px`;
      container.appendChild(canvas);
      const ctx = canvas.getContext("2d");
      this.surfaces[name] = { ...spec, canvas, ctx, corners: defaultCorners(name) };
    }
    this.geom = { ...DEFAULT_GEOM };
    this.bg = { on: false, level: 0.5 }; // her room behind the head, and how bright
    this.aligning = false;
    this.selected = "face";
    this.corner = 0; // 0 = whole surface, 1..4 = one corner
    this.testPattern = false;
    this._load();
    this._handles = this._makeHandles();
    this.apply();
  }

  _load() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORE) || "null");
      if (!saved) return;
      for (const name of Object.keys(this.surfaces)) {
        if (saved[name]?.length === 4) this.surfaces[name].corners = saved[name];
      }
      Object.assign(this.geom, saved.geom || {});
      Object.assign(this.bg, saved.bgShow || {});
    } catch {
      /* fall back to defaults */
    }
  }

  save() {
    const out = { geom: this.geom, bgShow: this.bg };
    for (const [name, s] of Object.entries(this.surfaces)) out[name] = s.corners;
    localStorage.setItem(STORE, JSON.stringify(out));
  }

  show(on) {
    this.container.hidden = !on;
  }

  apply() {
    this.surfaces.bg.canvas.hidden = !this.bg.on;
    for (const s of Object.values(this.surfaces)) {
      const m = cornerPinMatrix(s.w, s.h, s.corners);
      if (m) s.canvas.style.transform = cssMatrix(m);
    }
    this._placeHandles();
  }

  // ---------- alignment UI ----------

  setAligning(on) {
    this.aligning = on;
    document.body.classList.toggle("aligning", on);
    $("alignHelp").hidden = !on;
    this._placeHandles();
    this._status();
    if (!on) this.save();
  }

  _makeHandles() {
    const handles = [];
    for (const name of Object.keys(this.surfaces)) {
      for (let i = 0; i < 5; i++) {
        const el = document.createElement("div");
        el.className = i === 4 ? "handle center" : "handle";
        el.hidden = true;
        el.title = i === 4 ? `move ${name}` : `${name} corner ${i + 1}`;
        el.addEventListener("pointerdown", (e) => this._drag(e, name, i));
        document.body.appendChild(el); // outside #show, so mirroring doesn't flip them
        el.dataset.surface = name;
        el.dataset.index = i;
        handles.push(el);
      }
    }
    return handles;
  }

  _placeHandles() {
    for (const el of this._handles || []) {
      const s = this.surfaces[el.dataset.surface];
      const i = +el.dataset.index;
      el.hidden = !this.aligning || (el.dataset.surface === "bg" && !this.bg.on);
      const [x, y] = i === 4 ? centroid(s.corners) : s.corners[i];
      el.style.left = `${this._screenX(x)}px`;
      el.style.top = `${y}px`;
      const active = el.dataset.surface === this.selected && (this.corner === 0 ? i === 4 : i === this.corner - 1);
      el.classList.toggle("active", active);
    }
  }

  // The show may be mirrored for rear projection; handles live outside it.
  _screenX(x) {
    return document.body.classList.contains("mirror") ? window.innerWidth - x : x;
  }

  _drag(e, name, index) {
    e.preventDefault();
    this.selected = name;
    this.corner = index === 4 ? 0 : index + 1;
    let last = [this._screenX(e.clientX), e.clientY];
    const move = (ev) => {
      const p = [this._screenX(ev.clientX), ev.clientY];
      this._nudge(p[0] - last[0], p[1] - last[1]);
      last = p;
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      this.save();
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    this._status();
  }

  _nudge(dx, dy) {
    const s = this.surfaces[this.selected];
    const pts = this.corner === 0 ? s.corners : [s.corners[this.corner - 1]];
    for (const p of pts) {
      p[0] += dx;
      p[1] += dy;
    }
    this.apply();
  }

  _transform(scale, angle) {
    const s = this.surfaces[this.selected];
    const [cx, cy] = centroid(s.corners);
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    s.corners = s.corners.map(([x, y]) => {
      const dx = (x - cx) * scale;
      const dy = (y - cy) * scale;
      return [cx + dx * cos - dy * sin, cy + dx * sin + dy * cos];
    });
    this.apply();
  }

  _background(on, delta = 0) {
    this.bg.on = on;
    this.bg.level = Math.round(Math.min(1, Math.max(0.05, this.bg.level + delta)) * 100) / 100;
    if (!on && this.selected === "bg") this.selected = "face";
  }

  _geom(key, delta, lo, hi) {
    this.geom[key] = Math.round(Math.min(hi, Math.max(lo, this.geom[key] + delta)) * 100) / 100;
    this._status();
  }

  // Returns true if the key was handled.
  handleKey(e) {
    if (!this.aligning) return false;
    const big = e.shiftKey ? 10 : 1;
    const k = e.key;
    const actions = {
      Tab: () => {
        const order = this.bg.on ? ["face", "ball", "bg"] : ["face", "ball"];
        this.selected = order[(order.indexOf(this.selected) + 1) % order.length];
        this.corner = 0;
      },
      b: () => this._background(!this.bg.on),
      "[": () => this._background(true, -0.05),
      "]": () => this._background(true, 0.05),
      0: () => (this.corner = 0),
      1: () => (this.corner = 1),
      2: () => (this.corner = 2),
      3: () => (this.corner = 3),
      4: () => (this.corner = 4),
      ArrowLeft: () => this._nudge(-big, 0),
      ArrowRight: () => this._nudge(big, 0),
      ArrowUp: () => this._nudge(0, -big),
      ArrowDown: () => this._nudge(0, big),
      "=": () => this._transform(1 + 0.01 * big, 0),
      "+": () => this._transform(1 + 0.01 * big, 0),
      "-": () => this._transform(1 / (1 + 0.01 * big), 0),
      ",": () => this._transform(1, -0.005 * big),
      ".": () => this._transform(1, 0.005 * big),
      j: () => this._geom("eyeSpread", -0.02, 0.6, 1.6),
      k: () => this._geom("eyeSpread", 0.02, 0.6, 1.6),
      u: () => this._geom("eyeY", -2, -80, 80),
      n: () => this._geom("eyeY", 2, -80, 80),
      t: () => this._geom("eyeSize", -0.03, 0.5, 1.8),
      y: () => this._geom("eyeSize", 0.03, 0.5, 1.8),
      i: () => this._geom("mouthY", -2, -80, 80),
      m: () => this._geom("mouthY", 2, -80, 80),
      p: () => (this.testPattern = !this.testPattern),
      r: () => {
        this.surfaces[this.selected].corners = defaultCorners(this.selected);
        if (this.selected === "face") this.geom = { ...DEFAULT_GEOM };
        this.apply();
      },
      c: () => this.setAligning(false),
      Escape: () => this.setAligning(false),
    };
    const fn = actions[k] ?? actions[k.toLowerCase()];
    if (!fn) return true; // swallow other keys while aligning
    e.preventDefault();
    fn();
    this.apply();
    this._status();
    if (this.aligning) this.save();
    return true;
  }

  _status() {
    const el = $("alignStatus");
    if (!el) return;
    const what = this.corner === 0 ? "whole surface" : `corner ${this.corner}`;
    const g = this.geom;
    el.textContent =
      `editing: ${SURFACES[this.selected].label} · ${what}\n` +
      `eyes: spread ${g.eyeSpread} · height ${g.eyeY} · size ${g.eyeSize}   mouth: ${g.mouthY}\n` +
      `background: ${this.bg.on ? `on · brightness ${this.bg.level}` : "off"}`;
  }
}

function centroid(pts) {
  return [pts.reduce((a, p) => a + p[0], 0) / 4, pts.reduce((a, p) => a + p[1], 0) / 4];
}

function $(id) {
  return document.getElementById(id);
}
