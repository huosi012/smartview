"""Corridor-end louver corner (client's note: seal outside with glass, LED strips inside, potted plants for
observation). Puts the passes from louver_scene.py onto the photo.

    python louver_scene.py && python louver_edit.py  ->  renders/louver_corner.jpg
"""
import json
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "photos", "p_louver.jpg")
R_ = os.path.join(HERE, "renders")
OUT = os.path.join(R_, "louver_corner.jpg")
CAL = json.load(open(os.path.join(HERE, "calib_louver.json")))
FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
RELIGHT = 0.8                    # how much of the LED light / plant shadows to put on the photo


def lin(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def srgb(a):
    a = np.clip(a, 0, 1)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * a ** (1 / 2.4) - 0.055)


def load(name, size, mode=None):
    im = Image.open(os.path.join(R_, name))
    if mode:
        im = im.convert(mode)
    return im if im.size == size else im.resize(size, Image.LANCZOS)


def project(X):
    c = CAL["cam"]
    R, _ = cv2.Rodrigues(np.array(c["rv"]))
    Xc = R @ np.array(X, float) + np.array(c["tv"])
    w, h = c["size"]
    return (c["f"] * Xc[0] / Xc[2] + w / 2, c["f"] * Xc[1] / Xc[2] + h / 2)


def relight(img):
    """LED light on the fins, sill and reveals; contact shadows under the pots."""
    f = np.load(os.path.join(R_, "louver_light.npy")).astype(np.float32)
    h, w = img.shape[:2]
    if f.shape[:2] != (h, w):
        f = cv2.resize(f, (w, h), interpolation=cv2.INTER_LINEAR)
    d = f[..., :3] - 1
    d = np.where(d > 0, np.maximum(d - 0.08, 0), d)      # drop the faint overall warm cast, keep the glow
    fac = 1 + RELIGHT * d
    return srgb(lin(img) * fac)


def glass(img):
    """Tint and soft reflections where the new glass is seen through the louvers."""
    h, w = img.shape[:2]
    m = np.asarray(load("louver_glass.png", (w, h), "RGBA"))[..., 3].astype(np.float32) / 255
    m = cv2.GaussianBlur(m, (0, 0), 0.8)[..., None]
    tint = np.array([0.73, 0.80, 0.84])
    out = img * (1 - 0.2 * m) + tint * 0.2 * m
    streak = Image.new("L", (w, h), 0)
    sd = ImageDraw.Draw(streak)
    for x0, wd, a in ((430, 80, 60), (580, 30, 45), (900, 100, 55), (1090, 45, 40)):
        sd.polygon([(x0, 0), (x0 + wd, 0), (x0 + wd - 420, h), (x0 - 420, h)], fill=a)
    s = np.asarray(streak.filter(ImageFilter.GaussianBlur(28))).astype(np.float32)[..., None] / 255
    return out + (0.97 - out) * s * m


def over(img, beauty):
    b = np.asarray(beauty).astype(np.float32) / 255
    a = b[..., 3:]
    return b[..., :3] * a + img * (1 - a)


def bloom(img, beauty):
    """Glow around the LED strips (the brightest, warmest pixels of the render)."""
    b = np.asarray(beauty).astype(np.float32) / 255
    lum = b[..., :3].mean(-1) * b[..., 3]
    warm = (b[..., 0] - b[..., 2]) > 0.08
    core = np.where((lum > 0.9) & warm, 1.0, 0.0).astype(np.float32)
    glow = cv2.GaussianBlur(core, (0, 0), 6) * 0.7 + cv2.GaussianBlur(core, (0, 0), 20) * 0.45
    col = np.array([1.0, 0.78, 0.5])
    return 1 - (1 - img) * (1 - np.clip(glow[..., None] * col, 0, 1))


def plaque(im):
    """Small sign on the wall under the side louvers, put on in perspective."""
    pw, ph = 1100, 250
    p = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(p)
    d.rounded_rectangle((0, 0, pw - 1, ph - 1), radius=22, fill=(31, 77, 58, 255))
    d.rectangle((60, 56, 72, ph - 56), fill=(180, 138, 70, 255))
    d.text((pw / 2 + 36, ph / 2), "植物观察窗", font=ImageFont.truetype(FONT, 150), fill=(247, 245, 238, 255), anchor="mm")
    x0, x1, z0, z1, y = -3.05, -2.15, 0.54, 0.745, -0.012
    quad = np.float32([project((x0, y, z1)), project((x1, y, z1)), project((x1, y, z0)), project((x0, y, z0))])
    H = cv2.getPerspectiveTransform(np.float32([[0, 0], [pw, 0], [pw, ph], [0, ph]]), quad)
    W_, H_ = im.size
    warped = cv2.warpPerspective(np.asarray(p), H, (W_, H_), flags=cv2.INTER_AREA)
    sh = np.zeros((H_, W_), np.uint8)
    off = np.float32(project((x0 + 0.015, y, z0 - 0.02))) - quad[3]
    cv2.fillConvexPoly(sh, np.int32(quad + off), 255)
    sh = cv2.GaussianBlur(sh, (0, 0), 4)
    shadow = Image.new("RGBA", im.size, (40, 40, 38, 0))
    shadow.putalpha(Image.fromarray((sh * 0.35).astype(np.uint8)))
    out = im.convert("RGBA")
    out.alpha_composite(shadow)
    out.alpha_composite(Image.fromarray(warped))
    return out.convert("RGB")


def main():
    photo = Image.open(SRC).convert("RGB")
    size = photo.size
    img = np.asarray(photo).astype(np.float32) / 255
    beauty = load("louver_beauty.png", size, "RGBA")
    img = relight(img)
    img = glass(img)
    img = over(img, beauty)
    img = bloom(img, beauty)
    out = Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8))
    out = plaque(out)
    out.save(OUT, quality=93)
    print("saved", OUT)


if __name__ == "__main__":
    main()
