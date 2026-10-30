"""Paint over the pendant on Madame Mechanika's forehead and the hair above her
temples with forehead skin, for the foam head. Writes static/img/mechanika/forehead.png,
a soft-edged layer laid over every frame of her face (portrait.js), so the photos
themselves stay as they are.

    .venv/bin/python scripts/clean_forehead.py
        fills it with her forehead's own colour, shaded off toward the edges
    .venv/bin/python scripts/clean_forehead.py path/to/base-edited.png
        takes it from a copy of base.png already cleaned up by an image model

The layer stops above her brows (raised ones too) so it never covers them.
Rerun it whenever base.png changes.

For a photo-real forehead instead of the plain fill, give base.png to the image
model with this, save what it returns, and pass that file to this script:

    Edit this photo. Remove the round gold pendant and its chain from her forehead,
    and replace the dark hair above her forehead and temples with smooth porcelain
    forehead skin, the same colour and sheen as the rest of her forehead, reaching
    up to the edge of her headscarf. Keep the image exactly the same size. Change
    nothing else: her brows, eyes, face, headscarf and everything around her stay
    pixel for pixel as they are.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "static" / "img" / "mechanika"
CX = 695  # middle of her forehead, in the 1376 x 768 photo

base = np.asarray(Image.open(DIR / "base.png").convert("RGB")).astype(float)
h, w, _ = base.shape
yy, xx = np.mgrid[0:h, 0:w]
dx = abs(xx - CX)
lum = base.mean(2)
sat = (base.max(2) - base.min(2)) / np.maximum(base.max(2), 1)
skin = (lum > 185) & (sat < 0.25)

# Above this line: down to the pendant's tip in the middle, just above her raised
# brows, then curving down round the temples to the edge of what reaches the foam.
line = np.where(dx < 20, 178, 172) + np.clip(dx - 56, 0, None) * 2.4
brows = (yy > 174) & (dx < 66)
oval = ((xx - 693) / 96) ** 2 + ((yy - 229) / 104) ** 2 < 1.05
region = (yy < line) & ~brows & oval

if len(sys.argv) > 1:
    fill = np.asarray(Image.open(sys.argv[1]).convert("RGB").resize((w, h))).astype(float)
    keep = region
else:
    forehead = skin & (yy > 150) & (yy < 182) & (dx < 55) & ~((dx < 26) & (yy < 180))
    colour = np.percentile(base[forehead], 75, axis=0)
    # a touch darker toward the sides and the top, the way the light falls off a forehead
    off = np.clip(((xx - CX) / 95) ** 2 + np.clip((168 - yy) / 110, 0, None) ** 2, 0, 1)
    fill = colour * (1 - 0.15 * off[..., None])
    keep = region & (~skin | (yy < 150))

alpha = Image.fromarray((keep * 255).astype("uint8"))
alpha = alpha.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(2.5))
alpha = np.asarray(alpha) * np.clip((235 - yy) / 30, 0, 1)  # the hair beside her eyes stays
out = np.dstack([fill.clip(0, 255), alpha]).astype("uint8")
Image.fromarray(out, "RGBA").save(DIR / "forehead.png", optimize=True)
print(f"wrote {DIR / 'forehead.png'}")
