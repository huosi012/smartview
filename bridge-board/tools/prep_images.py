"""Prepare board images: crops, composites and the recolored assembly-step strip.

usage: python prep_images.py <pptx media dir> <extra images dir> <out dir>
  pptx media dir   ppt/media from the unzipped project PPT
  extra images dir holds 1.jpg (assembly diagram) and 2.jpg (team on the bridge)
"""
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage
from PIL import Image, ImageEnhance, ImageFilter

MEDIA = Path(sys.argv[1])
EXTRA = Path(sys.argv[2])
OUT = Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)


def save(im, name, q=92):
    im.convert("RGB").save(OUT / name, quality=q, subsampling=0)


def warm(im, lift=1.05, shift=0.025, sat=1.06, con=1.03):
    """Brighten and warm a photo so gray studio backdrops sit with the orange palette."""
    a = np.asarray(im.convert("RGB")).astype(np.float32) / 255
    lo, hi = np.percentile(a, 0.5), np.percentile(a, 99.5)
    a = np.clip((a - lo) / max(hi - lo, 1e-3) * lift, 0, 1)
    a[..., 0] = np.clip(a[..., 0] * (1 + shift), 0, 1)
    a[..., 2] = np.clip(a[..., 2] * (1 - shift), 0, 1)
    im = Image.fromarray((a * 255).round().astype(np.uint8))
    return ImageEnhance.Color(ImageEnhance.Contrast(im).enhance(con)).enhance(sat)


def crop_to_aspect(im, aspect, cx=0.5, cy=0.5):
    w, h = im.size
    if w / h > aspect:
        nw = round(h * aspect)
        x0 = round((w - nw) * cx)
        return im.crop((x0, 0, x0 + nw, h))
    nh = round(w / aspect)
    y0 = round((h - nh) * cy)
    return im.crop((0, y0, w, y0 + nh))


ASPECT = 16 / 9

# Station 1 shows the flat bridge bending under the bottle.
save(warm(crop_to_aspect(Image.open(MEDIA / "image4.png").convert("RGB"), ASPECT)), "st1.jpg")

for src, name, cy in [
    ("image6.png", "st2.jpg", 0.4),
    ("image8.png", "st3.jpg", 0.5),
    ("image10.png", "st4.jpg", 0.5),
]:
    save(warm(crop_to_aspect(Image.open(MEDIA / src).convert("RGB"), ASPECT, cy=cy)), name)

# Load comparison pairs (top: flat bridge, bottom: improved bridge).
for i, src in enumerate(["image11.jpeg", "image12.jpeg", "image13.jpeg"], 1):
    save(warm(Image.open(MEDIA / src)), f"cmp{i}.jpg")

# Shenyang bridges. Drop the burned-in title and the watermark from image14.
save(Image.open(MEDIA / "image14.jpeg").crop((0, 132, 860, 561)), "sy1.jpg")
save(Image.open(MEDIA / "image15.jpeg"), "sy2.jpg")
save(Image.open(MEDIA / "image16.jpeg"), "sy3.jpg")
save(Image.open(MEDIA / "image17.jpeg"), "sy4.jpg")

save(warm(Image.open(EXTRA / "2.jpg"), lift=1.03, shift=0.02, con=1.0), "kids.jpg", q=93)

# Assembly diagram: slice the 3x3 sequence into nine cells, recolor.
NAVY = (30, 55, 86)
ORANGE = (242, 107, 33)
WOOD = (255, 226, 196)
diag = Image.open(EXTRA / "1.jpg").convert("L")
PAD = 120
padded = Image.new("L", (diag.width + 2 * PAD, diag.height + 2 * PAD), 255)
padded.paste(diag, (PAD, PAD))
grounds = [118, 377, 684]
frames = [
    [(137, 347), (520, 732), (880, 1165)],
    [(102, 380), (460, 794), (873, 1191)],
    [(82, 440), (480, 825), (848, 1209)],
]
CW, CH = 400, 222
n = 0
for gy, row in zip(grounds, frames):
    for x0, x1 in row:
        n += 1
        cx = (x0 + x1) // 2
        box = (cx - CW // 2 + PAD, gy - (CH - 8) + PAD, cx + CW // 2 + PAD, gy + 8 + PAD)
        cell = padded.crop(box)
        L = np.array(cell).astype(np.int32)

        # Arrow fills are flat mid-gray; erode away anti-aliased line edges.
        mid = Image.fromarray((((L > 95) & (L < 185)) * 255).astype(np.uint8))
        arrow = mid.filter(ImageFilter.MinFilter(7)).filter(ImageFilter.MaxFilter(11))
        arrow = np.array(arrow) > 0

        # Small enclosed white regions are plank / peg interiors; large ones are
        # open space (outside, or under the bridge).
        labels, count = ndimage.label(L > 225)
        sizes = ndimage.sum(np.ones_like(L), labels, index=np.arange(1, count + 1))
        small = np.concatenate([[False], sizes < 2500])
        edge = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
        small[edge] = False
        interior = small[labels] | (small[ndimage.grey_dilation(labels, size=3)] & (L > 150))
        h, w = L.shape

        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        dark = np.clip((235 - L) * 255 // 155, 0, 255)
        rgba[..., :3] = NAVY
        rgba[..., 3] = dark
        rgba[interior] = (*WOOD, 255)
        rgba[arrow] = (*ORANGE, 255)
        Image.fromarray(rgba, "RGBA").resize((CW * 2, CH * 2), Image.LANCZOS).save(OUT / f"step{n}.png")

print("done", sorted(p.name for p in OUT.iterdir()))
