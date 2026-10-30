// The automaton, drawn on a canvas. The magic (crystal ball mist, glow) moves
// smoothly; the machine (head, eyes, lids, jaw) only moves on a 12 fps "servo"
// tick, at a fixed rate toward its target, like a cam-driven carnival figure.
//
// Two display modes:
//   screen - the whole booth (curtains, gears, turban, ball) for a sheet or wall
//   head   - only the face and the ball mist, each on its own corner-pinned
//            surface (see headmap.js) for projecting onto a foam head and globe

import { DEFAULT_GEOM } from "./headmap.js";
import { Portrait, MARKS, BALL } from "./portrait.js";
import { IDX, OUTLINE, HER, TRIS } from "./mechanika-mesh.js";

const W = 1600;
const H = 900;
const SERVO_HZ = 12;

const TONE = "grayscale(1) sepia(0.85) contrast(1.45) brightness(1.08)"; // a camera face as a spirit photograph
const PORCELAIN = ["#f6ede0", "#e6d6c2", "#bfa88e"];
const BRASS = ["#f3d27a", "#b8862f", "#5e3d12"];

// Servo ticks in a span of seconds (at least one); between two spans, at random.
const ticks = (s) => Math.max(1, Math.round(s * SERVO_HZ));
const between = (lo, hi) => lo + Math.random() * (hi - lo);

// The 2D affine [a, b, c, d, e, f] that carries three points onto three others.
function affine3([s0, s1, s2], [d0, d1, d2]) {
  const [ux, uy, vx, vy] = [s1.x - s0.x, s1.y - s0.y, s2.x - s0.x, s2.y - s0.y];
  const det = ux * vy - vx * uy;
  if (Math.abs(det) < 1) return null;
  const [px, py, qx, qy] = [d1.x - d0.x, d1.y - d0.y, d2.x - d0.x, d2.y - d0.y];
  const a = (px * vy - qx * uy) / det;
  const b = (py * vy - qy * uy) / det;
  const c = (qx * ux - px * vx) / det;
  const d = (qy * ux - py * vx) / det;
  return [a, b, c, d, d0.x - a * s0.x - c * s0.y, d0.y - b * s0.x - d * s0.y];
}

// The guest's face (a camera crop and its face mesh) cut into the triangles of
// hers, each stretched onto her photograph: their eyes, nose and mouth all land on
// hers, at the cost of a little skew. Colour-graded to her photo's light so it
// sits in her picture, and covering her face out to its outline with only a
// thin soft edge. Returned with where it sits on her photo.
function warpOntoHer(crop, mesh, photo) {
  const xs = HER.map((p) => p[0]);
  const ys = HER.map((p) => p[1]);
  const x0 = Math.floor(Math.min(...xs)) - 2;
  const y0 = Math.floor(Math.min(...ys)) - 2;
  const cv = document.createElement("canvas");
  cv.width = Math.ceil(Math.max(...xs)) + 2 - x0;
  cv.height = Math.ceil(Math.max(...ys)) + 2 - y0;
  const c = cv.getContext("2d", { willReadFrequently: true });
  const her = HER.map(([x, y]) => ({ x: x - x0, y: y - y0 }));
  const theirs = IDX.map((i) => mesh[i]);
  for (const tri of TRIS) {
    const d = tri.map((i) => her[i]);
    const m = affine3(tri.map((i) => theirs[i]), d);
    if (!m) continue;
    // clipped a pixel past its edges, so no seams show between triangles
    const cx = (d[0].x + d[1].x + d[2].x) / 3;
    const cy = (d[0].y + d[1].y + d[2].y) / 3;
    c.save();
    c.beginPath();
    for (const p of d) {
      const l = Math.hypot(p.x - cx, p.y - cy) || 1;
      c.lineTo(p.x + (p.x - cx) / l, p.y + (p.y - cy) / l);
    }
    c.clip();
    c.transform(...m);
    c.drawImage(crop, 0, 0);
    c.restore();
  }
  matchColour(c, photo, x0, y0);
  // a thin soft edge at her face's outline
  const rim = her.slice(0, OUTLINE);
  const mx = rim.reduce((a, p) => a + p.x, 0) / rim.length;
  const my = rim.reduce((a, p) => a + p.y, 0) / rim.length;
  c.globalCompositeOperation = "destination-in";
  c.filter = "blur(4px)";
  c.beginPath();
  for (const p of rim) c.lineTo(mx + (p.x - mx) * 0.985, my + (p.y - my) * 0.985);
  c.fill();
  return { canvas: cv, x: x0, y: y0 };
}

// Grade the warped face to her photo under it: brightness and contrast matched,
// and its colour pulled to her skin's, so a webcam's light and cast take on hers.
function matchColour(c, photo, x0, y0) {
  const { width: w, height: h } = c.canvas;
  const under = document.createElement("canvas");
  under.width = w;
  under.height = h;
  const u = under.getContext("2d", { willReadFrequently: true });
  u.drawImage(photo, -x0, -y0);
  const theirs = c.getImageData(0, 0, w, h);
  const hers = u.getImageData(0, 0, w, h).data;
  const px = theirs.data;
  // brightness and two colour axes (YCbCr)
  const ycc = (d, i) => [
    0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2],
    -0.169 * d[i] - 0.331 * d[i + 1] + 0.5 * d[i + 2],
    0.5 * d[i] - 0.419 * d[i + 1] - 0.081 * d[i + 2],
  ];
  const sum = new Array(12).fill(0); // theirs, theirs², hers, hers² per axis
  let n = 0;
  for (let i = 0; i < px.length; i += 4) {
    if (px[i + 3] < 250) continue;
    n++;
    const [a, b] = [ycc(px, i), ycc(hers, i)];
    for (let ax = 0; ax < 3; ax++) {
      sum[ax] += a[ax];
      sum[3 + ax] += a[ax] * a[ax];
      sum[6 + ax] += b[ax];
      sum[9 + ax] += b[ax] * b[ax];
    }
  }
  if (n < 100) return;
  const grade = [0, 1, 2].map((ax) => {
    const [mt, mh] = [sum[ax] / n, sum[6 + ax] / n];
    const sdT = Math.sqrt(Math.max(1, sum[3 + ax] / n - mt * mt));
    const sdH = Math.sqrt(Math.max(1, sum[9 + ax] / n - mh * mh));
    return [mt, Math.min(2, sdH / sdT), mh];
  });
  for (let i = 0; i < px.length; i += 4) {
    const [y, cb, cr] = ycc(px, i).map((v, ax) => (v - grade[ax][0]) * grade[ax][1] + grade[ax][2]);
    px[i] = y + 1.402 * cr;
    px[i + 1] = y - 0.344 * cb - 0.714 * cr;
    px[i + 2] = y + 1.772 * cb;
  }
  c.putImageData(theirs, 0, 0);
}

export class Puppet {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    // What the state machine asks for...
    this.target = {
      turn: 0, // -1..1 small head shift
      dim: 1, // 0 lit .. 1 asleep, her light turned down (her head never moves: she's projected on a mannequin)
      lidL: 0, // 0 closed .. 1 open
      lidR: 0,
      eyeX: 0, // -1..1, screen space
      eyeY: 0,
      brow: 0, // 0 neutral .. 1 raised
    };
    // ...and what the servos have actually reached.
    this.pose = { ...this.target };
    this.jaw = 0; // set directly from voice level, quantized
    this.ball = 0.15; // 0..1 crystal ball glow (smooth)
    this.ballTarget = 0.15;
    this.gearSpeed = 0.15; // rev/s-ish (smooth)
    this.gearTarget = 0.15;
    this.shake = 0; // servo ticks of glitch jitter remaining
    this._gearAngle = 0;
    this._lastServo = 0;
    this._last = performance.now();
    // Her timings in seconds, replaced by the server's (.env) once they arrive.
    this.timing = { dim: 0.9, blink_min: 2.5, blink_max: 7.5, blink: 0.17, glimpse_min: 0.33, glimpse_max: 0.58, glimpse_gap_min: 0.42, glimpse_gap_max: 0.83, look_side: 0.35, mouth_open: 2, glance_min: 5, glance_max: 14, glance: 0.9 };
    this._blinkAt = performance.now() + 3000;
    this._blinkTicks = 0;
    this._jitter = { x: 0, y: 0, r: 0 };
    this.mode = "screen";
    this.headmap = null; // set for head mode
    this.preview = false; // alignment: hold her awake with the mouth cycling
    this.guestFace = null; // the guest's face, toned like a spirit photograph
    this.flicker = false; // while consulting: her face and the guest's trade places
    this.trance = false; // while consulting: her eyes rolled back
    this._guestShown = 0; // 0 her; guestAlpha while the guest's face shows over hers
    this.guestAlpha = 1; // how solid their face is over hers (FLICKER_OPACITY in .env)
    this._flickerHold = 0;
    this.flickers = 3; // glimpses of the guest per consult (FACE_FLICKERS in .env)
    this.flickerWhere = "ball"; // where their face shows: "ball" or "face" (FLICKER_WHERE in .env)
    this._flickers = 0; // glimpses so far this consult
    this.portrait = null; // her photograph, once loaded; drawn porcelain until then
    Portrait.load().then((p) => (this.portrait = p));
    this.jawLevel = 0; // raw voice level, for the photograph's three mouths
    this._mouth = 0;
    this.resize();
    window.addEventListener("resize", () => this.resize());
  }

  resize() {
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.round(window.innerWidth * dpr);
    this.canvas.height = Math.round(window.innerHeight * dpr);
    const s = Math.min(this.canvas.width / W, this.canvas.height / H);
    this.scale = s;
    this.ox = (this.canvas.width - W * s) / 2;
    this.oy = (this.canvas.height - H * s) / 2;
  }

  set(partial) {
    Object.assign(this.target, partial);
  }

  setJaw(level) {
    this.jawLevel = level;
    // A wooden jaw has three positions: shut, ajar, open.
    this.jaw = level < 0.08 ? 0 : level < 0.25 ? 0.5 : 1;
  }

  glitch(seconds) {
    this.shake = ticks(seconds);
  }

  // Tone a camera crop once, so it reads as sepia porcelain rather than video.
  setGuestFace(crop) {
    if (!crop) return;
    const toned = document.createElement("canvas");
    toned.width = 240; // her face oval, 200 x 256
    toned.height = 307;
    const c = toned.getContext("2d");
    c.filter = TONE;
    const m = crop.marks && this._lineUp(crop.marks, toned.width, toned.height);
    if (m) {
      c.setTransform(...m);
      c.drawImage(crop, 0, 0);
    } else {
      c.drawImage(crop, 0, 0, toned.width, toned.height);
    }
    this.guestFace = toned;
    // Feathered all round, for her crystal ball (or her face, without a mesh).
    const soft = document.createElement("canvas");
    soft.width = toned.width;
    soft.height = toned.height;
    const s = soft.getContext("2d");
    s.drawImage(toned, 0, 0);
    s.globalCompositeOperation = "destination-in";
    s.translate(soft.width / 2, soft.height / 2);
    s.scale(1, soft.height / soft.width);
    const g = s.createRadialGradient(0, 0, 0, 0, 0, soft.width / 2);
    g.addColorStop(0.72, "rgba(0,0,0,1)");
    g.addColorStop(1, "rgba(0,0,0,0)");
    s.fillStyle = g;
    s.fillRect(-soft.width / 2, -soft.width / 2, soft.width, soft.width);
    this._guestSoft = soft;
    this._guestWarp = crop.mesh && this.portrait ? warpOntoHer(crop, crop.mesh, this.portrait.base) : null;
  }

  // The transform that puts the guest's eyes on her eyes and their mouth on her
  // jaw seam (three points fix it exactly), in the toned canvas's pixels.
  _lineUp({ eyes, mouth }, w, h) {
    const at = (p) => ({ x: ((p.x + 100) * w) / 200, y: ((p.y + 128) * h) / 256 });
    return affine3([eyes[0], eyes[1], mouth], this._ovalMarks().map(at));
  }

  // Her eyes and mouth in face-oval units (centre 0,0; 200 x 256).
  _ovalMarks() {
    const g = this.geom;
    return [
      { x: -40 * g.eyeSpread, y: -22 + g.eyeY },
      { x: 40 * g.eyeSpread, y: -22 + g.eyeY },
      { x: 0, y: 62 + g.mouthY },
    ];
  }

  // Called every animation frame.
  frame(now) {
    const dt = Math.min(0.1, (now - this._last) / 1000);
    this._last = now;
    // smooth things
    this.ball += (this.ballTarget - this.ball) * Math.min(1, dt * 3);
    this.gearSpeed += (this.gearTarget - this.gearSpeed) * Math.min(1, dt * 2);
    this._gearAngle += this.gearSpeed * dt * Math.PI * 2;
    // stepped things
    if (now - this._lastServo >= 1000 / SERVO_HZ) {
      this._lastServo = now;
      this._servoTick(now);
    }
    if (this.mode === "head" && this.headmap) this._drawHead(now / 1000);
    else this._draw(now / 1000);
  }

  get geom() {
    return this.mode === "head" && this.headmap ? this.headmap.geom : DEFAULT_GEOM;
  }

  _servoTick(now) {
    const p = this.pose;
    const t = this.target;
    const step = (key, maxStep) => {
      const d = t[key] - p[key];
      p[key] += Math.abs(d) <= maxStep ? d : Math.sign(d) * maxStep;
    };
    step("turn", 0.12);
    step("dim", 1 / ticks(this.timing.dim));
    step("lidL", 0.34);
    step("lidR", 0.34);
    step("brow", 0.25);
    // Eyes saccade: jump straight to the target if it moved enough.
    if (Math.hypot(t.eyeX - p.eyeX, t.eyeY - p.eyeY) > 0.12) {
      p.eyeX = t.eyeX;
      p.eyeY = t.eyeY;
    }
    // Blink now and then while awake (lids snap shut for two ticks).
    if (this._blinkTicks > 0) this._blinkTicks--;
    else if (now > this._blinkAt && t.lidL > 0.5 && t.lidR > 0.5) {
      this._blinkTicks = ticks(this.timing.blink);
      this._blinkAt = now + between(this.timing.blink_min, this.timing.blink_max) * 1000;
    }
    // Awake, she glances away now and then (her photograph's eyes only).
    if (this._glance && now > this._glanceEnd) this._glance = null;
    if (p.dim > 0 || this.trance || !(this.timing.glance > 0)) this._glanceAt = 0;
    else if (!this._glance && now > this._glanceAt) {
      if (this._glanceAt) {
        this._glance = ["look-left", "look-right", "look-up", "look-down"][Math.floor(Math.random() * 4)];
        this._glanceEnd = now + this.timing.glance * 1000;
      }
      this._glanceAt = now + between(this.timing.glance_min, this.timing.glance_max) * 1000;
    }
    // The photograph's mouth: shut, then three openings, set on the servo clock,
    // no wider than MOUTH_OPEN.
    const v = this.jawLevel;
    this._mouth = Math.min(v < 0.08 ? 0 : v < 0.2 ? 1 : v < 0.4 ? 2 : 3, this.timing.mouth_open ?? 2);
    if (this.shake > 0) {
      this.shake--;
      this._jitter = { x: (Math.random() - 0.5) * 14, y: (Math.random() - 0.5) * 8 };
      p.eyeX = Math.random() * 2 - 1;
      p.eyeY = Math.random() * 2 - 1;
    } else {
      this._jitter = { x: 0, y: 0 };
    }
    // The flicker runs on the servo clock too: a few uneven glimpses of the
    // guest, then she is herself again.
    if (!this.flicker || !this.guestFace) {
      this._guestShown = 0;
      this._flickers = 0;
    } else if (--this._flickerHold <= 0) {
      if (this._guestShown) {
        this._guestShown = 0;
        this._flickerHold = ticks(between(this.timing.glimpse_gap_min, this.timing.glimpse_gap_max));
      } else if (this._flickers < this.flickers) {
        this._flickers++;
        this._guestShown = this.guestAlpha;
        this._flickerHold = ticks(between(this.timing.glimpse_min, this.timing.glimpse_max));
      }
    }
    // A seizure shakes the guest's face loose again, stuttering on and off.
    if (this.shake > 0 && this.guestFace) this._guestShown = Math.random() < 0.5 ? this.guestAlpha : 0;
  }

  // ---------- drawing ----------

  _draw(time) {
    const c = this.ctx;
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.fillStyle = "#000";
    c.fillRect(0, 0, this.canvas.width, this.canvas.height);
    c.setTransform(this.scale, 0, 0, this.scale, this.ox, this.oy);

    if (this.portrait) {
      this._drawPortrait(time);
      this._vignette();
      return;
    }
    this._backdrop();
    this._gears();
    this._torso();
    this._head(time);
    this._dimmed(1 - this._power());
    this._ball(time);
    this._hands();
    this._vignette();
  }

  // Her photograph as it is this tick. Asleep she is the same, only dimmed.
  _portraitNow(time) {
    const p = this.pose;
    if (this.mode === "head" && this.preview) return this.portrait.compose(Math.floor(time) % 2 ? this.timing.mouth_open ?? 2 : 0);
    return this.portrait.compose(this._mouth, this._eyesNow(), p.brow > 0.5);
  }

  // Which of her photographed eyes fit the pose: shut, rolled back in the
  // trance, looking off (gaze past LOOK_SIDE, or a glance away), or heavy-lidded.
  _eyesNow() {
    const p = this.pose;
    const lids = (p.lidL + p.lidR) / 2;
    const side = this.timing.look_side ?? 0.35;
    if (this._blinkTicks > 0 || lids < 0.25) return "blink";
    if (this.trance) return "trance";
    if (this._glance) return this._glance;
    if (Math.abs(p.eyeX) >= side && Math.abs(p.eyeX) >= Math.abs(p.eyeY)) return p.eyeX < 0 ? "look-left" : "look-right";
    if (Math.abs(p.eyeY) >= side) return p.eyeY < 0 ? "look-up" : "look-down";
    if (lids < 0.75) return "eyes-half";
    return null;
  }

  // The whole booth as her photograph, filling the screen.
  _drawPortrait(time) {
    const c = this.ctx;
    const pt = this.portrait;
    const k = Math.max(W / pt.width, H / pt.height);
    const ox = (W - pt.width * k) / 2 + this._jitter.x;
    const oy = (H - pt.height * k) / 2 + this._jitter.y;
    const at = (p) => ({ x: ox + p.x * k, y: oy + p.y * k });
    c.drawImage(this._portraitNow(time), ox, oy, pt.width * k, pt.height * k);
    this._dimmed(1 - this._power());
    const b = at(BALL);
    this._ballGlow(b.x, b.y, BALL.r * k, time);
    c.save();
    c.translate(b.x, b.y);
    this._ballFace(c, BALL.r * k);
    c.restore();
    if (this.flickerWhere !== "face" || !this._guestShown) return;
    const g = this._guestWarp;
    if (g) {
      // the guest's face warped over hers
      c.globalAlpha = this._guestShown;
      c.drawImage(g.canvas, ox + g.x * k, oy + g.y * k, g.canvas.width * k, g.canvas.height * k);
      c.globalAlpha = 1;
    } else if (this._guestSoft) {
      // no face mesh: just their eyes and mouth on hers
      const m = affine3(this._ovalMarks(), [...MARKS.eyes.map(at), at(MARKS.mouth)]);
      if (m) {
        c.save();
        c.transform(...m);
        c.globalAlpha = this._guestShown;
        c.drawImage(this._guestSoft, -100, -128, 200, 256);
        c.restore();
      }
    }
  }

  // The guest's face flickering up in the crystal ball (centre 0,0, radius r).
  _ballFace(c, r) {
    if (this.flickerWhere === "face" || !this._guestShown || !this._guestSoft) return;
    const s = (1.3 * r) / 200; // their face oval about two thirds of the ball across
    const f = this._guestSoft;
    c.save();
    c.beginPath();
    c.arc(0, 0, r - 3, 0, Math.PI * 2);
    c.clip();
    c.globalAlpha = this._guestShown;
    c.drawImage(f, (-f.width * s) / 2, (-f.height * s) / 2, f.width * s, f.height * s);
    c.restore();
  }

  // Mist swirling in her real crystal ball, brighter as she consults.
  _ballGlow(cx, cy, r, time) {
    const c = this.ctx;
    const glow = this.ball;
    c.save();
    c.globalCompositeOperation = "screen";
    const halo = c.createRadialGradient(cx, cy, r * 0.8, cx, cy, r * (1.6 + glow));
    halo.addColorStop(0, `rgba(150,120,255,${glow * 0.35})`);
    halo.addColorStop(1, "rgba(150,120,255,0)");
    c.fillStyle = halo;
    c.fillRect(cx - r * 3, cy - r * 3, r * 6, r * 6);
    c.beginPath();
    c.arc(cx, cy, r - 3, 0, Math.PI * 2);
    c.clip();
    c.filter = "blur(10px)";
    for (let i = 0; i < 5; i++) {
      const a = time * (0.4 + glow * 1.6) * (i % 2 ? 1 : -1) + i * 1.3;
      const hue = 250 + i * 25 + Math.sin(time + i) * 20;
      c.fillStyle = `hsla(${hue}, 80%, ${45 + glow * 20}%, ${0.1 + glow * 0.4})`;
      c.beginPath();
      c.ellipse(cx + Math.cos(a) * r * 0.33, cy + Math.sin(a * 1.3) * r * 0.27, r * 0.55, r * 0.24, a, 0, Math.PI * 2);
      c.fill();
    }
    c.restore();
  }

  _backdrop() {
    const c = this.ctx;
    // Dark velvet curtain folds; kept dim so the projection reads as "only her".
    for (let i = 0; i < 16; i++) {
      const x = (i / 16) * W;
      const g = c.createLinearGradient(x, 0, x + W / 16, 0);
      g.addColorStop(0, "#120305");
      g.addColorStop(0.5, "#2a080d");
      g.addColorStop(1, "#120305");
      c.fillStyle = g;
      c.fillRect(x, 0, W / 16 + 1, H);
    }
    // Valance with gold fringe
    c.fillStyle = "#3a0a12";
    c.beginPath();
    c.moveTo(0, 0);
    c.lineTo(W, 0);
    c.lineTo(W, 50);
    for (let i = 8; i >= 0; i--) c.quadraticCurveTo((i + 0.5) * (W / 8), 105, i * (W / 8), 50);
    c.fill();
    c.strokeStyle = "#a07a2c";
    c.lineWidth = 3;
    c.stroke();
  }

  _gearPath(r, teeth, depth) {
    const c = this.ctx;
    c.beginPath();
    for (let i = 0; i < teeth * 2; i++) {
      const a0 = (i / (teeth * 2)) * Math.PI * 2;
      const a1 = ((i + 1) / (teeth * 2)) * Math.PI * 2;
      const rr = i % 2 === 0 ? r : r - depth;
      c.arc(0, 0, rr, a0, a1);
    }
    c.closePath();
  }

  _gear(x, y, r, teeth, angle, alpha = 0.55) {
    const c = this.ctx;
    c.save();
    c.translate(x, y);
    c.rotate(angle);
    c.globalAlpha = alpha;
    const g = c.createRadialGradient(-r * 0.3, -r * 0.3, r * 0.1, 0, 0, r);
    g.addColorStop(0, BRASS[0]);
    g.addColorStop(0.6, BRASS[1]);
    g.addColorStop(1, BRASS[2]);
    c.fillStyle = g;
    this._gearPath(r, teeth, r * 0.14);
    c.fill();
    // spokes cut-outs
    c.globalCompositeOperation = "destination-out";
    for (let i = 0; i < 5; i++) {
      c.rotate((Math.PI * 2) / 5);
      c.beginPath();
      c.ellipse(r * 0.45, 0, r * 0.2, r * 0.12, 0, 0, Math.PI * 2);
      c.fill();
    }
    c.beginPath();
    c.arc(0, 0, r * 0.12, 0, Math.PI * 2);
    c.fill();
    c.restore();
  }

  _gears() {
    const a = this._gearAngle;
    this._gear(250, 250, 120, 18, a, 0.4);
    this._gear(250 + 196, 330, 80, 12, -a * 1.5 + 0.2, 0.35);
    this._gear(140, 470, 60, 9, -a * 2 + 0.1, 0.3);
    this._gear(1350, 230, 100, 15, -a * 1.2, 0.4);
    this._gear(1350 - 160, 330, 65, 10, a * 1.85 + 0.15, 0.35);
    this._gear(1460, 420, 50, 8, a * 2.4, 0.3);
  }

  _torso() {
    const c = this.ctx;
    c.save();
    c.translate(0, 30);
    // shawl
    const g = c.createLinearGradient(0, 480, 0, H);
    g.addColorStop(0, "#5b1a4a");
    g.addColorStop(1, "#24081d");
    c.fillStyle = g;
    c.beginPath();
    c.moveTo(800 - 80, 470);
    c.bezierCurveTo(800 - 220, 480, 800 - 330, 520, 800 - 360, 640);
    c.lineTo(800 - 400, H + 10);
    c.lineTo(800 + 400, H + 10);
    c.lineTo(800 + 360, 640);
    c.bezierCurveTo(800 + 330, 520, 800 + 220, 480, 800 + 80, 470);
    c.closePath();
    c.fill();
    // gold trim + little stars
    c.strokeStyle = "#c79a3b";
    c.lineWidth = 5;
    c.beginPath();
    c.moveTo(800 - 80, 470);
    c.quadraticCurveTo(800, 640, 800 + 80, 470);
    c.stroke();
    c.fillStyle = "rgba(220,180,90,0.5)";
    for (let i = 0; i < 26; i++) {
      const x = 800 + ((i * 137) % 640) - 320;
      const y = 560 + ((i * 89) % 320);
      this._star(x, y, 5);
    }
    // brooch
    c.fillStyle = "#8a1020";
    c.strokeStyle = BRASS[0];
    c.lineWidth = 4;
    c.beginPath();
    c.ellipse(800, 575, 20, 26, 0, 0, Math.PI * 2);
    c.fill();
    c.stroke();
    c.restore();
  }

  _star(x, y, r) {
    const c = this.ctx;
    c.beginPath();
    for (let i = 0; i < 10; i++) {
      const a = (i / 10) * Math.PI * 2 - Math.PI / 2;
      const rr = i % 2 === 0 ? r : r * 0.4;
      c.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr);
    }
    c.fill();
  }

  _head(time) {
    const c = this.ctx;
    const p = this.pose;
    const j = this._jitter;
    // Mechanical tick-tock bob: one pixel, twice a second, never smooth.
    const bob = Math.floor(time * 2) % 2;
    const pivotX = 800 + p.turn * 18 + j.x;
    const pivotY = 455 + bob + j.y;

    // neck with a brass collar joint and rivets
    c.save();
    c.translate(800, 500);
    c.fillStyle = "#d9c6ad";
    c.fillRect(-34, -75, 68, 75);
    const cg = c.createLinearGradient(-50, 0, 50, 0);
    cg.addColorStop(0, BRASS[2]);
    cg.addColorStop(0.5, BRASS[0]);
    cg.addColorStop(1, BRASS[2]);
    c.fillStyle = cg;
    c.fillRect(-48, -18, 96, 22);
    c.fillStyle = "#3a2508";
    for (let i = -3; i <= 3; i++) {
      c.beginPath();
      c.arc(i * 13, -7, 2.5, 0, Math.PI * 2);
      c.fill();
    }
    c.restore();

    c.save();
    c.translate(pivotX, pivotY);
    c.scale(0.92, 0.92);

    const faceY = -112; // chin overlaps the top of the neck
    this._earrings(faceY);
    this._turbanBack(faceY);
    this._face(faceY);
    this._guest(faceY);
    this._turbanFront(faceY);
    c.restore();
  }

  _earrings(fy) {
    const c = this.ctx;
    c.strokeStyle = BRASS[0];
    c.lineWidth = 4;
    for (const s of [-1, 1]) {
      c.beginPath();
      c.arc(s * 98, fy + 40, 14, 0, Math.PI * 2);
      c.stroke();
    }
  }

  _turbanBack(fy) {
    const c = this.ctx;
    c.fillStyle = "#3b0f39";
    c.beginPath();
    c.ellipse(0, fy - 40, 128, 120, 0, Math.PI, 0);
    c.fill();
  }

  _turbanFront(fy) {
    const c = this.ctx;
    const g = c.createLinearGradient(0, fy - 175, 0, fy - 60);
    g.addColorStop(0, "#6e2266");
    g.addColorStop(1, "#3d0f3a");
    c.fillStyle = g;
    c.beginPath();
    c.moveTo(-122, fy - 52);
    c.bezierCurveTo(-140, fy - 150, -60, fy - 205, 0, fy - 200);
    c.bezierCurveTo(60, fy - 205, 140, fy - 150, 122, fy - 52);
    c.quadraticCurveTo(0, fy - 92, -122, fy - 52);
    c.fill();
    // wrap folds
    c.strokeStyle = "rgba(0,0,0,0.35)";
    c.lineWidth = 3;
    for (let i = 0; i < 4; i++) {
      c.beginPath();
      c.moveTo(-115 + i * 10, fy - 70 - i * 25);
      c.quadraticCurveTo(0, fy - 120 - i * 28, 115 - i * 10, fy - 70 - i * 25);
      c.stroke();
    }
    // gold band and jewel
    c.strokeStyle = "#c79a3b";
    c.lineWidth = 7;
    c.beginPath();
    c.moveTo(-120, fy - 60);
    c.quadraticCurveTo(0, fy - 98, 120, fy - 60);
    c.stroke();
    const jg = c.createRadialGradient(-5, fy - 92, 2, 0, fy - 86, 20);
    jg.addColorStop(0, "#ff8a8a");
    jg.addColorStop(0.4, "#c0102a");
    jg.addColorStop(1, "#4a0010");
    c.fillStyle = jg;
    c.strokeStyle = BRASS[0];
    c.lineWidth = 4;
    c.beginPath();
    c.ellipse(0, fy - 86, 17, 21, 0, 0, Math.PI * 2);
    c.fill();
    c.stroke();
    // feather plume
    c.strokeStyle = "rgba(230,220,200,0.8)";
    c.lineWidth = 2;
    for (let i = 0; i < 14; i++) {
      c.beginPath();
      c.moveTo(4, fy - 108);
      c.quadraticCurveTo(20 + i * 2, fy - 170 - i * 3, 46 + i * 3, fy - 210 - i * 2);
      c.stroke();
    }
  }

  _porcelain(cx, cy, rx, ry) {
    const g = this.ctx.createRadialGradient(cx - rx * 0.25, cy - ry * 0.3, rx * 0.1, cx, cy, ry * 1.05);
    g.addColorStop(0, PORCELAIN[0]);
    g.addColorStop(0.65, PORCELAIN[1]);
    g.addColorStop(1, PORCELAIN[2]);
    return g;
  }

  _face(fy, { nose = true } = {}) {
    const c = this.ctx;
    const rx = 100;
    const ry = 128;
    const mouthY = fy + 62 + this.geom.mouthY;
    const jawW = 36;
    const drop = this.jaw * 20;
    const facePath = () => {
      c.beginPath();
      c.ellipse(0, fy, rx, ry, 0, 0, Math.PI * 2);
    };

    // Mouth cavity behind the jaw
    c.fillStyle = "#1a0306";
    c.fillRect(-jawW, mouthY - 2, jawW * 2, drop + 40);

    // Upper face: the face ellipse minus the jaw slot
    c.save();
    c.beginPath();
    c.rect(-200, fy - 200, 400, 400);
    c.rect(jawW, mouthY, -jawW * 2, 200); // reversed winding = hole
    c.clip("evenodd");
    c.fillStyle = this._porcelain(0, fy, rx, ry);
    facePath();
    c.fill();
    c.restore();

    // Jaw piece: same porcelain, cut on the marionette lines, dropped
    c.save();
    c.translate(0, drop);
    c.beginPath();
    c.rect(-jawW, mouthY, jawW * 2, 200);
    c.clip();
    c.fillStyle = this._porcelain(0, fy - drop, rx, ry);
    facePath();
    c.fill();
    // lower lip
    c.fillStyle = "#9c1b2b";
    c.beginPath();
    c.ellipse(0, mouthY + 6, 22, 7, 0, 0, Math.PI);
    c.fill();
    // seam shadow
    c.strokeStyle = "rgba(60,30,20,0.55)";
    c.lineWidth = 2;
    c.beginPath();
    c.moveTo(-jawW, mouthY);
    c.lineTo(-jawW, fy + ry);
    c.moveTo(jawW, mouthY);
    c.lineTo(jawW, fy + ry);
    c.stroke();
    c.restore();

    // marionette seam lines on the upper face (stay put)
    c.strokeStyle = "rgba(60,30,20,0.6)";
    c.lineWidth = 2;
    c.beginPath();
    c.moveTo(-jawW - 1, mouthY);
    c.lineTo(-jawW - 1, mouthY + 52);
    c.moveTo(jawW + 1, mouthY);
    c.lineTo(jawW + 1, mouthY + 52);
    c.stroke();

    // upper lip, cupid's bow
    c.fillStyle = "#b42235";
    c.beginPath();
    c.moveTo(-24, mouthY);
    c.quadraticCurveTo(-12, mouthY - 12, 0, mouthY - 5);
    c.quadraticCurveTo(12, mouthY - 12, 24, mouthY);
    c.closePath();
    c.fill();

    // rouge
    for (const s of [-1, 1]) {
      const g = c.createRadialGradient(s * 56, fy + 25, 2, s * 56, fy + 25, 30);
      g.addColorStop(0, "rgba(220,90,100,0.45)");
      g.addColorStop(1, "rgba(220,90,100,0)");
      c.fillStyle = g;
      c.beginPath();
      c.arc(s * 56, fy + 25, 30, 0, Math.PI * 2);
      c.fill();
    }

    // nose (a real foam head brings its own)
    if (nose) {
      c.strokeStyle = "rgba(120,80,60,0.45)";
      c.lineWidth = 2.5;
      c.beginPath();
      c.moveTo(-4, fy - 12);
      c.quadraticCurveTo(-12, fy + 22, -2, fy + 30);
      c.quadraticCurveTo(6, fy + 33, 12, fy + 27);
      c.stroke();
    }

    this._eyes(fy - 22 + this.geom.eyeY);

    // A hairline crack in the porcelain, the detail that makes it wrong.
    c.strokeStyle = "rgba(50,25,15,0.6)";
    c.lineWidth = 1.5;
    c.beginPath();
    c.moveTo(62, fy - 85);
    c.lineTo(55, fy - 64);
    c.lineTo(66, fy - 50);
    c.lineTo(58, fy - 30);
    c.lineTo(63, fy - 18);
    c.moveTo(55, fy - 64);
    c.lineTo(44, fy - 58);
    c.stroke();
  }

  // The guest's face over all of hers, cut on the same marionette lines as _face:
  // their chin rides down with her jaw, so no porcelain shows.
  _guest(fy) {
    if (!this._guestShown || !this.guestFace) return;
    const c = this.ctx;
    const rx = 100;
    const ry = 128;
    const mouthY = fy + 62 + this.geom.mouthY;
    const jawW = 36;
    const drop = this.jaw * 20;
    const paint = () => {
      c.beginPath();
      c.ellipse(0, fy, rx, ry, 0, 0, Math.PI * 2);
      c.clip();
      c.drawImage(this.guestFace, -rx, fy - ry, rx * 2, ry * 2);
      // only the very edge softens into her porcelain rim
      c.translate(0, fy);
      c.scale(1, ry / rx);
      const rim = c.createRadialGradient(0, 0, rx * 0.9, 0, 0, rx);
      rim.addColorStop(0, "rgba(191,168,142,0)");
      rim.addColorStop(1, PORCELAIN[2]);
      c.fillStyle = rim;
      c.fillRect(-rx, -rx, rx * 2, rx * 2);
    };
    c.save();
    c.globalAlpha = this._guestShown;
    // upper face, around the jaw slot
    c.save();
    c.beginPath();
    c.rect(-200, fy - 200, 400, 400);
    c.rect(jawW, mouthY, -jawW * 2, 200);
    c.clip("evenodd");
    paint();
    c.restore();
    // jaw piece, dropped with hers
    c.save();
    c.translate(0, drop);
    c.beginPath();
    c.rect(-jawW, mouthY, jawW * 2, 200);
    c.clip();
    paint();
    c.restore();
    c.restore();
  }

  _eyes(ey) {
    const c = this.ctx;
    const p = this.pose;
    const blinking = this._blinkTicks > 0;
    const lids = [blinking ? 0 : p.lidL, blinking ? 0 : p.lidR];
    // Eyes sit at screen-left (-1) and screen-right (+1).
    const g = this.geom;
    const z = g.eyeSize;
    [-1, 1].forEach((s, i) => {
      const x = s * 40 * g.eyeSpread;
      const sw = 25 * z;
      const sh = 15 * z;
      // socket shadow (a foam head has real sockets)
      if (this.mode !== "head") {
        c.fillStyle = "rgba(110,70,60,0.35)";
        c.beginPath();
        c.ellipse(x, ey, sw + 7, sh + 7, 0, 0, Math.PI * 2);
        c.fill();
      }
      // glass eye
      c.save();
      c.beginPath();
      c.ellipse(x, ey, sw, sh, 0, 0, Math.PI * 2);
      c.clip();
      c.fillStyle = "#f4efe4";
      c.fill();
      const ix = x + p.eyeX * 11 * z;
      const iy = ey + p.eyeY * 6 * z;
      const ig = c.createRadialGradient(ix, iy, 1, ix, iy, 11 * z);
      ig.addColorStop(0, "#9fe0d0");
      ig.addColorStop(0.5, "#2d7a70");
      ig.addColorStop(1, "#0d2b29");
      c.fillStyle = ig;
      c.beginPath();
      c.arc(ix, iy, 11 * z, 0, Math.PI * 2);
      c.fill();
      c.fillStyle = "#050505";
      c.beginPath();
      c.arc(ix, iy, 4.8 * z, 0, Math.PI * 2);
      c.fill();
      c.fillStyle = "rgba(255,255,255,0.9)";
      c.beginPath();
      c.arc(ix - 3.5 * z, iy - 3.5 * z, 2.2 * z, 0, Math.PI * 2);
      c.fill();
      // eyelid (porcelain shutter coming down from the top)
      const lid = lids[i];
      const lidBottom = ey - sh + (1 - lid) * (sh * 2 + 2);
      c.fillStyle = this._porcelain(x, ey - 30 * z, 60 * z, 60 * z);
      c.fillRect(x - sw - 2, ey - sh - 2, sw * 2 + 4, lidBottom - (ey - sh - 2));
      c.restore();
      // lid line + painted lashes
      c.strokeStyle = "#2a160f";
      c.lineWidth = 2.5;
      c.beginPath();
      if (lid < 0.15) {
        c.moveTo(x - sw, ey);
        c.quadraticCurveTo(x, ey + 7, x + sw, ey);
      } else {
        c.ellipse(x, ey, sw, sh, 0, Math.PI * 1.05, Math.PI * 1.95);
      }
      c.stroke();
      const lashY = lid < 0.15 ? ey + 3 : ey - sh;
      for (let k = -2; k <= 2; k++) {
        c.beginPath();
        c.moveTo(x + k * 8 * z, lashY);
        c.lineTo(x + k * 10 * z, lashY - 7 * z);
        c.stroke();
      }
      // painted brow
      c.strokeStyle = "#3a2216";
      c.lineWidth = 3;
      c.beginPath();
      const by = ey - 30 * z - p.brow * 8;
      c.moveTo(x - 24 * z, by + 6);
      c.quadraticCurveTo(x, by - 6, x + 24 * z, by + 4);
      c.stroke();
    });
  }

  _ball(time) {
    const c = this.ctx;
    const cx = 800;
    const cy = 735;
    const r = 92;
    const glow = this.ball;
    // stand
    const sg = c.createLinearGradient(cx - 80, 0, cx + 80, 0);
    sg.addColorStop(0, BRASS[2]);
    sg.addColorStop(0.5, BRASS[0]);
    sg.addColorStop(1, BRASS[2]);
    c.fillStyle = sg;
    c.beginPath();
    c.moveTo(cx - 55, cy + 75);
    c.lineTo(cx + 55, cy + 75);
    c.lineTo(cx + 90, cy + 150);
    c.lineTo(cx - 90, cy + 150);
    c.closePath();
    c.fill();
    // outer glow
    c.save();
    c.shadowColor = `rgba(150,120,255,${0.25 + glow * 0.6})`;
    c.shadowBlur = 30 + glow * 90;
    const bg = c.createRadialGradient(cx - 30, cy - 35, 5, cx, cy, r);
    bg.addColorStop(0, `rgba(230,225,255,${0.35 + glow * 0.4})`);
    bg.addColorStop(0.5, `rgba(110,80,200,${0.25 + glow * 0.35})`);
    bg.addColorStop(1, `rgba(25,10,60,${0.7})`);
    c.fillStyle = bg;
    c.beginPath();
    c.arc(cx, cy, r, 0, Math.PI * 2);
    c.fill();
    c.restore();
    // swirling mist inside
    c.save();
    c.beginPath();
    c.arc(cx, cy, r - 3, 0, Math.PI * 2);
    c.clip();
    c.filter = "blur(10px)";
    for (let i = 0; i < 5; i++) {
      const a = time * (0.4 + glow * 1.6) * (i % 2 ? 1 : -1) + i * 1.3;
      const hue = 250 + i * 25 + Math.sin(time + i) * 20;
      c.fillStyle = `hsla(${hue}, 80%, ${55 + glow * 20}%, ${0.15 + glow * 0.35})`;
      c.beginPath();
      c.ellipse(cx + Math.cos(a) * 30, cy + Math.sin(a * 1.3) * 25, 50, 22, a, 0, Math.PI * 2);
      c.fill();
    }
    c.restore();
    // specular highlight
    c.fillStyle = "rgba(255,255,255,0.5)";
    c.beginPath();
    c.ellipse(cx - 35, cy - 45, 20, 11, -0.6, 0, Math.PI * 2);
    c.fill();
  }

  _hands() {
    const c = this.ctx;
    // Porcelain hands cupping the sides of the ball.
    for (const s of [-1, 1]) {
      c.save();
      c.translate(800 + s * 100, 760);
      c.scale(s, 1);
      c.fillStyle = this._porcelain(10, 0, 40, 40);
      c.beginPath();
      c.ellipse(16, 10, 30, 40, 0.2, 0, Math.PI * 2);
      c.fill();
      for (let k = 0; k < 4; k++) {
        c.beginPath();
        c.ellipse(-8, -22 + k * 16, 20, 7, -0.35 + k * 0.12, 0, Math.PI * 2);
        c.fill();
      }
      c.strokeStyle = "rgba(90,60,40,0.4)";
      c.lineWidth = 1.5;
      c.stroke();
      // lace cuff
      c.fillStyle = "#e9e1cf";
      c.beginPath();
      c.ellipse(44, 22, 14, 34, 0.25, 0, Math.PI * 2);
      c.fill();
      c.restore();
    }
  }

  // How bright her face is lit. Asleep she is a dim gaslight; waking, the lamp
  // sputters up to full.
  _power() {
    const p = this.pose;
    if (this.preview) return 1;
    let power = 1 - 0.72 * p.dim;
    if (p.dim > 0.04 && p.dim < 0.96 && Math.random() < 0.35) power *= 0.45;
    if (this.shake > 0 && Math.random() < 0.4) power *= 0.3 + Math.random() * 0.5;
    return power;
  }

  // Darken everything drawn so far by `shade` (0..1).
  _dimmed(shade) {
    if (shade <= 0) return;
    const c = this.ctx;
    c.save();
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.fillStyle = `rgba(0,0,0,${shade})`;
    c.fillRect(0, 0, this.canvas.width, this.canvas.height);
    c.restore();
  }

  // ---------- head mode ----------

  _drawHead(time) {
    const main = this.ctx;
    main.setTransform(1, 0, 0, 1, 0, 0);
    main.fillStyle = "#000";
    main.fillRect(0, 0, this.canvas.width, this.canvas.height);

    const hm = this.headmap;
    const p = this.pose;
    const power = this._power();

    const face = hm.surfaces.face;
    this._onSurface(face, (c) => {
      c.translate(face.w / 2 + this._jitter.x * 0.3, face.h * 0.54 + this._jitter.y * 0.3);
      c.scale(1.6, 1.6);
      if (this.portrait) {
        // her photograph, its eyes and mouth pinned on the foam's
        c.save();
        c.transform(...affine3([...MARKS.eyes, MARKS.mouth], this._ovalMarks()));
        c.drawImage(this._portraitNow(time), 0, 0);
        const g = this._guestWarp;
        const over = this.flickerWhere === "face" && this._guestShown;
        if (over && g) {
          c.globalAlpha = this._guestShown;
          c.drawImage(g.canvas, g.x, g.y);
        }
        c.restore();
        if (over && this._guestSoft && !g) {
          c.globalAlpha = this._guestShown;
          c.drawImage(this._guestSoft, -100, -128, 200, 256);
          c.globalAlpha = 1;
        }
      } else {
        const savedLids = [p.lidL, p.lidR];
        const savedJaw = this.jaw;
        if (this.preview) {
          p.lidL = p.lidR = 1;
          this.jaw = Math.floor(time) % 2; // open/shut each second to line up the lips
        }
        this._face(0, { nose: false });
        this._guest(0);
        [p.lidL, p.lidR] = savedLids;
        this.jaw = savedJaw;
      }
      // Feather the edge so no hard outline spills past the foam.
      c.globalCompositeOperation = "destination-in";
      c.save();
      c.scale(1, 128 / 100);
      const g = c.createRadialGradient(0, 0, 0, 0, 0, 104);
      g.addColorStop(0, "rgba(0,0,0,1)");
      g.addColorStop(0.8, "rgba(0,0,0,1)");
      g.addColorStop(1, "rgba(0,0,0,0)");
      c.fillStyle = g;
      c.fillRect(-200, -200, 400, 400);
      c.restore();
      c.globalCompositeOperation = "source-over";
    }, power);

    const ball = hm.surfaces.ball;
    this._onSurface(ball, (c) => {
      c.translate(ball.w / 2, ball.h / 2);
      const r = ball.w / 2 - 6;
      const glow = this.preview ? 0.8 : this.ball;
      c.filter = "blur(14px)";
      for (let i = 0; i < 6; i++) {
        const a = time * (0.4 + glow * 1.6) * (i % 2 ? 1 : -1) + i * 1.1;
        const hue = 250 + i * 22 + Math.sin(time + i) * 20;
        c.fillStyle = `hsla(${hue}, 85%, ${50 + glow * 25}%, ${0.12 + glow * 0.55})`;
        c.beginPath();
        c.ellipse(Math.cos(a) * r * 0.3, Math.sin(a * 1.3) * r * 0.25, r * 0.55, r * 0.25, a, 0, Math.PI * 2);
        c.fill();
      }
      c.filter = "none";
      this._ballFace(c, r);
      c.globalCompositeOperation = "destination-in";
      const g = c.createRadialGradient(0, 0, r * 0.6, 0, 0, r);
      g.addColorStop(0, "rgba(0,0,0,1)");
      g.addColorStop(1, "rgba(0,0,0,0)");
      c.fillStyle = g;
      c.fillRect(-r, -r, r * 2, r * 2);
      c.globalCompositeOperation = "source-over";
    }, 1);
  }

  // Draw onto one corner-pinned surface, plus alignment guides when aligning.
  _onSurface(surface, draw, power) {
    const c = surface.ctx;
    const prev = this.ctx;
    this.ctx = c;
    c.setTransform(2, 0, 0, 2, 0, 0); // surfaces are 2x for crispness
    c.globalCompositeOperation = "source-over";
    c.filter = "none";
    c.fillStyle = "#000";
    c.fillRect(0, 0, surface.w, surface.h);
    c.save();
    draw(c);
    c.restore();
    if (power < 1) {
      c.fillStyle = `rgba(0,0,0,${1 - power})`;
      c.fillRect(0, 0, surface.w, surface.h);
    }
    if (this.headmap.aligning) this._guides(surface);
    this.ctx = prev;
  }

  _guides(surface) {
    const c = surface.ctx;
    const hm = this.headmap;
    const selected = hm.surfaces[hm.selected] === surface;
    c.strokeStyle = selected ? "#ffd400" : "rgba(0,200,255,0.6)";
    c.lineWidth = selected ? 3 : 2;
    c.strokeRect(1.5, 1.5, surface.w - 3, surface.h - 3);
    c.fillStyle = c.strokeStyle;
    c.font = "bold 16px ui-monospace, Menlo, monospace";
    c.fillText(surface.label, 10, 24);
    if (surface === hm.surfaces.ball) {
      // Line this circle up with the outline of the globe.
      c.beginPath();
      c.arc(surface.w / 2, surface.h / 2, surface.w / 2 - 6, 0, Math.PI * 2);
      c.stroke();
    }
    if (!hm.testPattern) return;
    c.strokeStyle = "rgba(0,255,255,0.7)";
    c.lineWidth = 1;
    for (let x = 0; x <= surface.w; x += surface.w / 8) {
      c.beginPath();
      c.moveTo(x, 0);
      c.lineTo(x, surface.h);
      c.stroke();
    }
    for (let y = 0; y <= surface.h; y += surface.h / 10) {
      c.beginPath();
      c.moveTo(0, y);
      c.lineTo(surface.w, y);
      c.stroke();
    }
    if (surface === hm.surfaces.face) {
      // Crosshairs where the eyes and mouth are drawn, to sit on the foam features.
      const g = hm.geom;
      const cx = surface.w / 2;
      const cy = surface.h * 0.54;
      const k = 1.6;
      const marks = [
        [cx - 40 * g.eyeSpread * k, cy + (-22 + g.eyeY) * k],
        [cx + 40 * g.eyeSpread * k, cy + (-22 + g.eyeY) * k],
        [cx, cy + (62 + g.mouthY) * k],
      ];
      c.strokeStyle = "#ff3df0";
      c.lineWidth = 2;
      for (const [x, y] of marks) {
        c.beginPath();
        c.moveTo(x - 14, y);
        c.lineTo(x + 14, y);
        c.moveTo(x, y - 14);
        c.lineTo(x, y + 14);
        c.stroke();
      }
    }
  }

  _vignette() {
    const c = this.ctx;
    const g = c.createRadialGradient(W / 2, H * 0.48, H * 0.3, W / 2, H / 2, W * 0.62);
    g.addColorStop(0, "rgba(0,0,0,0)");
    g.addColorStop(1, "rgba(0,0,0,0.92)");
    c.fillStyle = g;
    c.fillRect(0, 0, W, H);
  }
}
