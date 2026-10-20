"""Trace the logo marks out of the summer-version screenshot into SVG paths.

PREVIEW ONLY: the screenshot is low-res, so these traces are approximations used
to place the logo in the mockups. Final artwork must use the vector logo from
the original .ai file.
"""
import sys
from pathlib import Path

import numpy as np
import potrace
from PIL import Image, ImageFilter

SCALE = 10
CROPS = {
    "callig": (1072, 210, 1136, 250),  # 佛慈 calligraphy (the rest of the lockup is rebuilt in layout)
    "seal": (740, 375, 832, 462),      # big 慈 seal
    "icons": (774, 122, 868, 153),     # three knot icons
}


def ink_alpha(crop: Image.Image) -> np.ndarray:
    """Alpha of the dark ink, measured against the locally brightest background."""
    lum = np.asarray(crop.convert("L"), dtype=np.float32)
    bg = np.asarray(crop.convert("L").filter(ImageFilter.MaxFilter(9)), dtype=np.float32)
    bg = np.asarray(Image.fromarray(bg.astype(np.uint8)).filter(ImageFilter.GaussianBlur(4)), dtype=np.float32)
    ink = 20.0
    a = (bg - lum) / np.maximum(bg - ink, 1)
    return np.clip(a, 0, 1)


def trace(alpha: np.ndarray) -> str:
    h, w = alpha.shape
    big = Image.fromarray((alpha * 255).astype(np.uint8)).resize((w * SCALE, h * SCALE), Image.BICUBIC)
    big = big.filter(ImageFilter.GaussianBlur(SCALE * 0.55))
    # potracer traces the False pixels as ink, so invert
    bmp = ~(np.asarray(big) > 112)
    plist = potrace.Bitmap(bmp).trace(turdsize=SCALE * 2, alphamax=1.1, opticurve=True, opttolerance=0.4)
    parts = []
    for curve in plist:
        s = curve.start_point
        d = [f"M{s.x:.1f},{s.y:.1f}"]
        for seg in curve.segments:
            if seg.is_corner:
                d.append(f"L{seg.c.x:.1f},{seg.c.y:.1f}L{seg.end_point.x:.1f},{seg.end_point.y:.1f}")
            else:
                d.append(f"C{seg.c1.x:.1f},{seg.c1.y:.1f} {seg.c2.x:.1f},{seg.c2.y:.1f} {seg.end_point.x:.1f},{seg.end_point.y:.1f}")
        parts.append("".join(d) + "Z")
    return "".join(parts), w * SCALE, h * SCALE


def main(screenshot: str, out_dir: str) -> None:
    im = Image.open(screenshot).convert("RGB")
    out = Path(out_dir)
    for name, box in CROPS.items():
        d, w, h = trace(ink_alpha(im.crop(box)))
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
               f'<path fill-rule="evenodd" fill="currentColor" d="{d}"/></svg>\n')
        (out / f"{name}.svg").write_text(svg)
        print(name, w, h, len(d))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
