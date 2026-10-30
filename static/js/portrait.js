// Madame Mechanika as a photograph. One scene (static/img/mechanika/) whose face
// changes between AI-edited frames on her servo tick. The frames differ from
// base.png only in her face, so just a feathered patch of each is laid over it:
// the eyes of one frame (shut, looking off, rolled back) can then go over the
// mouth and brows of others.

const DIR = "/img/mechanika/";

// Where things are in the 1376 x 768 pictures. Her eyes and mouth are where the
// face mesh finds them on base.png (iris centres, middle of the lips), the same
// way the guest's are found, so the two line up.
export const MARKS = { eyes: [{ x: 658, y: 213 }, { x: 729, y: 212 }], mouth: { x: 694, y: 276 } };
export const BALL = { x: 691, y: 587, r: 78 };
const FACE = { x: 693, y: 255, rx: 105, ry: 125 }; // forehead to dropped chin
const EYES = { x: 693, y: 214, rx: 80, ry: 28 };
const BROWS = { x: 693, y: 185, rx: 100, ry: 42 }; // brows and the eyes under them
// Her eyes: each frame only differs from base.png there.
export const EYE_FRAMES = ["blink", "eyes-half", "look-left", "look-right", "look-up", "look-down", "trance"];

const loadImage = (name) =>
  new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = DIR + name + ".png";
  });

// The image cut to a soft-edged ellipse, so the patch melts into the base.
function patch(img, { x, y, rx, ry }) {
  const cv = document.createElement("canvas");
  cv.width = img.width;
  cv.height = img.height;
  const c = cv.getContext("2d");
  c.drawImage(img, 0, 0);
  c.globalCompositeOperation = "destination-in";
  c.translate(x, y);
  c.scale(1, ry / rx);
  const g = c.createRadialGradient(0, 0, 0, 0, 0, rx);
  g.addColorStop(0.7, "rgba(0,0,0,1)");
  g.addColorStop(1, "rgba(0,0,0,0)");
  c.fillStyle = g;
  c.fillRect(-rx, -rx, rx * 2, rx * 2);
  return cv;
}

export class Portrait {
  // Null if the pictures aren't there, and she stays drawn.
  static async load() {
    const names = ["base", "mouth-1", "mouth-2", "mouth-3", "brows-up", ...EYE_FRAMES];
    const imgs = await Promise.all(names.map(loadImage));
    if (imgs.some((i) => !i)) return null;
    // forehead.png (scripts/clean_forehead.py): skin over the pendant and the hair
    // above her temples, for the foam head; optional
    const forehead = await loadImage("forehead");
    return new Portrait({ ...Object.fromEntries(names.map((n, i) => [n, imgs[i]])), forehead });
  }

  constructor(imgs) {
    this.base = imgs.base;
    this.width = imgs.base.width;
    this.height = imgs.base.height;
    this.mouths = [null, ...["mouth-1", "mouth-2", "mouth-3"].map((n) => patch(imgs[n], FACE))];
    this.brows = patch(imgs["brows-up"], BROWS);
    this.eyes = Object.fromEntries(EYE_FRAMES.map((n) => [n, patch(imgs[n], EYES)]));
    this.forehead = imgs.forehead;
    this.canvas = document.createElement("canvas");
    this.canvas.width = this.width;
    this.canvas.height = this.height;
    this._key = "";
  }

  // Her face as it is this tick: mouth 0 (shut) to 3 (wide), her eyes (one of
  // EYE_FRAMES, or null for as in base.png), brows raised or not.
  compose(mouth, eyes = null, brows = false) {
    const key = `${mouth}${eyes}${brows}`;
    if (key === this._key) return this.canvas;
    this._key = key;
    const c = this.canvas.getContext("2d");
    c.drawImage(this.base, 0, 0);
    if (this.mouths[mouth]) c.drawImage(this.mouths[mouth], 0, 0);
    if (brows) c.drawImage(this.brows, 0, 0);
    if (eyes) c.drawImage(this.eyes[eyes], 0, 0);
    if (this.forehead) c.drawImage(this.forehead, 0, 0);
    return this.canvas;
  }
}
