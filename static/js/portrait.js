// Madame Mechanika as a photograph. One scene (static/img/mechanika/) whose face
// changes between AI-edited frames on her servo tick. The frames differ from
// base.png only in her face, so just a feathered patch of each is laid over it:
// the eyes of one frame (shut, looking off, rolled back) can then go over the
// mouth and brows of others. Asleep, the whole frame is shown.

const DIR = "/img/mechanika/";

// Where things are in the 1376 x 768 pictures. Her eyes and mouth are where the
// face mesh finds them on base.png (iris centres, middle of the lips), the same
// way the guest's are found, so the two line up.
export const MARKS = { eyes: [{ x: 675, y: 190 }, { x: 745, y: 189 }], mouth: { x: 709, y: 265 } };
export const BALL = { x: 700, y: 526, r: 89 };
const FACE = { x: 708, y: 232, rx: 112, ry: 128 }; // forehead to dropped chin
const EYES = { x: 708, y: 188, rx: 88, ry: 30 };
const BROWS = { x: 704, y: 160, rx: 110, ry: 46 }; // brows and the eyes under them
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
    const names = ["base", "mouth-1", "mouth-2", "mouth-3", "brows-up", "asleep", "asleep-peek", ...EYE_FRAMES];
    const imgs = await Promise.all(names.map(loadImage));
    if (imgs.some((i) => !i)) return null;
    return new Portrait(Object.fromEntries(names.map((n, i) => [n, imgs[i]])));
  }

  constructor(imgs) {
    this.base = imgs.base;
    this.sleeping = { asleep: imgs.asleep, "asleep-peek": imgs["asleep-peek"] };
    this.width = imgs.base.width;
    this.height = imgs.base.height;
    this.mouths = [null, ...["mouth-1", "mouth-2", "mouth-3"].map((n) => patch(imgs[n], FACE))];
    this.brows = patch(imgs["brows-up"], BROWS);
    this.eyes = Object.fromEntries(EYE_FRAMES.map((n) => [n, patch(imgs[n], EYES)]));
    this.canvas = document.createElement("canvas");
    this.canvas.width = this.width;
    this.canvas.height = this.height;
    this._key = "";
  }

  // Her face as it is this tick: mouth 0 (shut) to 3 (wide), her eyes (one of
  // EYE_FRAMES, or null for as in base.png), brows raised or not; or slumped
  // "asleep" or "asleep-peek".
  compose(mouth, eyes = null, brows = false, asleep = null) {
    if (asleep) return this.sleeping[asleep];
    const key = `${mouth}${eyes}${brows}`;
    if (key === this._key) return this.canvas;
    this._key = key;
    const c = this.canvas.getContext("2d");
    c.drawImage(this.base, 0, 0);
    if (this.mouths[mouth]) c.drawImage(this.mouths[mouth], 0, 0);
    if (brows) c.drawImage(this.brows, 0, 0);
    if (eyes) c.drawImage(this.eyes[eyes], 0, 0);
    return this.canvas;
  }
}
