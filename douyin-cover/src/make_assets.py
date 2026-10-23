"""Generate the raster assets of the frame templates.

Outputs (in src/assets/):
  bg-<style>.jpg          frame background (paper/grain, frame lines)
  guide-<style>.png       hidden alignment guide, sized to the photo window
  photo-<style>-<name>.jpg  sample watch photos cropped to each photo window
  crop-guide.png          how a 3:4 phone photo gets cropped by the window
  diagram-top.png         shooting angle, seen from above
  diagram-side.png        camera height, seen from the side

Run: python3 -I src/make_assets.py
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTOS = os.path.join(HERE, "photos")
OUT = os.path.join(HERE, "assets")
FONT = os.path.join(HERE, "..", "fonts", "NotoSerifSC-SemiBold.ttf")

W, H = 1080, 1440
# Photo window of each style: x, y, w, h in cover pixels. build.js has the
# same numbers; keep them in sync.
WINDOWS = {
    "noir": (96, 176, 888, 828),
    "ivory": (64, 64, 952, 952),
    "dossier": (72, 160, 936, 808),
}
DIAL_AT = (0.5, 0.5)    # dial centre, as a fraction of the window
DIAL_SIZE = 0.6         # dial diameter, as a fraction of the window width

CHAMPAGNE = (196, 168, 118)
BRASS = (176, 146, 96)
CYAN = (61, 245, 255)

# source photo: (dial centre x, y) and dial diameter, in source pixels
SOURCES = {
    "omega-gmt": ((182, 325), 300),
    "longines-hydroconquest": ((207, 352), 295),
    "tissot-lelocle": ((168, 333), 345),
    "rolex-dj-black": ((185, 215), 270),
    "gp-1945": ((150, 232), 205),
    "montblanc": ((160, 222), 225),
    "breguet-a": ((150, 212), 280),
    "breguet-b": ((152, 218), 280),
    "omega-seamaster": ((148, 222), 205),
}


def font(size):
    return ImageFont.truetype(FONT, size)


def smoothstep(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def grain(shape, strength, seed):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, 1, shape)
    n = np.asarray(Image.fromarray(((n * 40) + 128).clip(0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(0.6))).astype(float) - 128
    return n / 40 * strength


def base(color, glow_color, glow_at, glow_r, grain_strength, seed, edge_dark=0.0):
    y, x = np.mgrid[0:H, 0:W].astype(float)
    d = np.hypot((x - glow_at[0]) / glow_r, (y - glow_at[1]) / glow_r)
    g = (1 - smoothstep(d))[..., None]
    img = np.array(color, float) * (1 - g) + np.array(glow_color, float) * g
    if edge_dark:
        e = smoothstep((np.hypot((x - 540) / 760, (y - 720) / 1000) - 0.55) / 0.6)
        img *= (1 - edge_dark * e)[..., None]
    img += grain((H, W), grain_strength, seed)[..., None]
    return Image.fromarray(img.clip(0, 255).astype(np.uint8)).convert("RGBA")


def line_layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def rect(d, box, color, alpha, width):
    d.rectangle(box, outline=color + (alpha,), width=width)


def make_noir():
    img = base((13, 12, 11), (30, 28, 25), (540, 590), 760, 3.0, 1, edge_dark=0.35)
    lay = line_layer()
    d = ImageDraw.Draw(lay)
    rect(d, (40, 40, W - 41, H - 41), CHAMPAGNE, 150, 2)
    rect(d, (48, 48, W - 49, H - 49), CHAMPAGNE, 70, 1)
    x, y, w, h = WINDOWS["noir"]
    rect(d, (x - 16, y - 16, x + w + 15, y + h + 15), CHAMPAGNE, 120, 1)
    # small diamond centred under the photo, between frame and caption
    cx, cy = 540, y + h + 16
    d.polygon([(cx, cy - 7), (cx + 7, cy), (cx, cy + 7), (cx - 7, cy)], fill=CHAMPAGNE + (220,))
    Image.alpha_composite(img, lay).convert("RGB").save(os.path.join(OUT, "bg-noir.jpg"), quality=92)


def make_ivory():
    img = base((233, 227, 215), (240, 235, 225), (540, 500), 900, 3.5, 2, edge_dark=0.06)
    x, y, w, h = WINDOWS["ivory"]
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rectangle((x + 4, y + 14, x + w - 4, y + h + 12), fill=95)
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    img = Image.composite(Image.new("RGBA", (W, H), (60, 50, 40, 255)), img, shadow)
    lay = line_layer()
    d = ImageDraw.Draw(lay)
    d.line((x, 1290, x + w, 1290), fill=(30, 28, 24, 90), width=1)
    Image.alpha_composite(img, lay).convert("RGB").save(os.path.join(OUT, "bg-ivory.jpg"), quality=92)


def make_dossier():
    img = base((19, 19, 19), (31, 31, 30), (540, 560), 800, 3.0, 3, edge_dark=0.3)
    lay = line_layer()
    d = ImageDraw.Draw(lay)
    x, y, w, h = WINDOWS["dossier"]
    o, L, t = 14, 48, 3
    for cx, sx in ((x - o, 1), (x + w + o, -1)):
        for cy, sy in ((y - o, 1), (y + h + o, -1)):
            d.line((cx, cy, cx + sx * L, cy), fill=BRASS + (230,), width=t)
            d.line((cx, cy, cx, cy + sy * L), fill=BRASS + (230,), width=t)
    for ry in (1146, 1208, 1270):   # rows of the record table (see build.js)
        d.line((x, ry, x + w, ry), fill=(255, 255, 255, 46), width=1)
    Image.alpha_composite(img, lay).convert("RGB").save(os.path.join(OUT, "bg-dossier.jpg"), quality=92)


def dashed_circle(draw, c, r, color, width, dash=18):
    n = int(2 * math.pi * r / dash)
    for i in range(0, n, 2):
        a0, a1 = 360 * i / n, 360 * (i + 1) / n
        draw.arc((c[0] - r, c[1] - r, c[0] + r, c[1] + r), a0, a1, fill=color, width=width)


def label(draw, xy, text, size, color, anchor="la"):
    f = font(size)
    x, y = xy
    draw.text((x + 2, y + 2), text, font=f, fill=(0, 0, 0, 200), anchor=anchor)
    draw.text((x, y), text, font=f, fill=color + (255,), anchor=anchor)


def make_guide(style):
    _, _, w, h = WINDOWS[style]
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = (round(w * DIAL_AT[0]), round(h * DIAL_AT[1]))
    r = round(w * DIAL_SIZE / 2)
    dashed_circle(d, c, r, CYAN + (255,), 4)
    d.line((c[0] - 36, c[1], c[0] + 36, c[1]), fill=CYAN + (255,), width=3)
    d.line((c[0], c[1] - 36, c[0], c[1] + 36), fill=CYAN + (255,), width=3)
    label(d, (c[0], c[1] - r - 16), "表盘对准圆圈", 34, CYAN, "ms")
    img.save(os.path.join(OUT, f"guide-{style}.png"), optimize=True)


def place(name, out_w, out_h):
    """Scale and crop a source photo to fill an out_w x out_h window edge to
    edge, dial as close to the standard spot as the photo allows. The photo
    is never smaller than the window, so there are no faded or padded edges."""
    (dx, dy), dial_d = SOURCES[name]
    src = Image.open(os.path.join(PHOTOS, name + ".jpg")).convert("RGB")
    s = max(out_w * DIAL_SIZE / dial_d, out_w / src.width, out_h / src.height)
    sw, sh = math.ceil(src.width * s), math.ceil(src.height * s)
    big = src.resize((sw, sh), Image.LANCZOS).filter(
        ImageFilter.UnsharpMask(radius=2.0, percent=60, threshold=2))
    ox = min(0, max(out_w - sw, round(out_w * DIAL_AT[0] - dx * s)))
    oy = min(0, max(out_h - sh, round(out_h * DIAL_AT[1] - dy * s)))
    return big.crop((-ox, -oy, -ox + out_w, -oy + out_h))


def make_crop_guide():
    """A 3:4 phone photo with the part the frame keeps marked out. The kept
    band is the real window crop; the bands above and below stand in for
    the rest of the phone photo (mirrored, blurred and dimmed)."""
    _, _, w, h = WINDOWS["noir"]
    win_h = round(W * h / w)
    top = (H - win_h) // 2
    band = place("omega-gmt", W, win_h)
    img = Image.new("RGB", (W, H))
    img.paste(band, (0, top))
    above = band.crop((0, 0, W, top)).transpose(Image.FLIP_TOP_BOTTOM)
    below = band.crop((0, win_h - (H - top - win_h), W, win_h)).transpose(Image.FLIP_TOP_BOTTOM)
    for part, y in ((above, 0), (below, top + win_h)):
        part = part.filter(ImageFilter.GaussianBlur(14)).point(lambda v: v * 0.45)
        img.paste(part, (0, y))
    img = img.convert("RGBA")
    d = ImageDraw.Draw(img)
    for yy in (top, top + win_h):
        for xx in range(0, W, 44):
            d.line((xx, yy, xx + 22, yy), fill=CYAN + (255,), width=4)
    label(d, (W // 2, top // 2 + 16), "上下这部分会被画框裁掉", 46, (255, 255, 255), "ms")
    label(d, (W // 2, top + win_h + (H - top - win_h) // 2 + 16), "表放正中，四周留出空间", 46, (255, 255, 255), "ms")
    img.convert("RGB").resize((720, 960), Image.LANCZOS).save(os.path.join(OUT, "crop-guide.png"), optimize=True)


def arrow(d, p0, p1, color, width=6, head=22):
    d.line((p0, p1), fill=color, width=width)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for da in (2.6, -2.6):
        d.line((p1, (p1[0] + head * math.cos(ang + da), p1[1] + head * math.sin(ang + da))),
               fill=color, width=width)


def camera(d, c, ang_deg, color):
    """A phone seen edge-on: a short thick bar pointing along ang_deg."""
    a = math.radians(ang_deg)
    ux, uy = math.cos(a), math.sin(a)
    px, py = -uy, ux
    hw, hd = 70, 16
    pts = [(c[0] + px * hw + ux * hd, c[1] + py * hw + uy * hd),
           (c[0] - px * hw + ux * hd, c[1] - py * hw + uy * hd),
           (c[0] - px * hw - ux * hd, c[1] - py * hw - uy * hd),
           (c[0] + px * hw - ux * hd, c[1] + py * hw - uy * hd)]
    d.polygon(pts, fill=color)


def make_diagrams():
    ink = (235, 230, 220)
    dim = (120, 116, 110)
    gold = CHAMPAGNE
    # Seen from above: phone at the bottom, watch turned ~25 deg so the
    # crown end comes toward the lens and the dial faces front-left.
    img = Image.new("RGBA", (1000, 760), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    wc = (500, 250)
    rot = math.radians(25)

    def rp(x, y):
        return (wc[0] + x * math.cos(rot) - y * math.sin(rot),
                wc[1] + x * math.sin(rot) + y * math.cos(rot))
    d.polygon([rp(-70, -30), rp(70, -30), rp(60, -190), rp(-60, -190)], fill=dim)
    d.polygon([rp(-150, -40), rp(150, -40), rp(150, 30), rp(-150, 30)], fill=ink)
    d.polygon([rp(150, -22), rp(182, -22), rp(182, 8), rp(150, 8)], fill=gold)
    d.line((rp(-150, 30), rp(150, 30)), fill=gold, width=8)
    d.line((500, 290, 500, 560), fill=dim, width=3)
    arrow(d, rp(0, 40), rp(0, 200), gold, 5)
    d.arc((500 - 170, 250 - 170, 500 + 170, 250 + 170), 90, 115, fill=CYAN, width=6)
    camera(d, (500, 610), 90, ink)
    f = font(34)
    d.text((330, 430), "约 25°", font=f, fill=CYAN)
    d.text((300, 660), "手机正对表头，竖拍 3:4", font=f, fill=ink)
    d.text((700, 300), "表冠朝右\n露出侧面", font=f, fill=gold, spacing=8)
    d.text((40, 40), "俯视图", font=font(40), fill=ink)
    img.save(os.path.join(OUT, "diagram-top.png"), optimize=True)

    # Seen from the side: dial upright, phone level or slightly above, soft
    # light from the upper left.
    img = Image.new("RGBA", (1000, 760), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((60, 600, 940, 610), fill=dim)
    d.rounded_rectangle((210, 470, 330, 600), 16, fill=dim)
    d.rounded_rectangle((230, 300, 290, 520), 20, fill=ink)
    d.line((292, 310, 292, 510), fill=gold, width=8)
    centre = (292, 410)
    cam = (800, 330)
    camera(d, cam, 180 - math.degrees(math.atan2(410 - 330, 800 - 292)), ink)
    d.line((cam, centre), fill=CYAN, width=4)
    for xx in range(300, 860, 28):
        d.line((xx, 410, xx + 14, 410), fill=dim, width=3)
    d.arc((292 - 330, 410 - 330, 292 + 330, 410 + 330), 351, 360, fill=CYAN, width=6)
    d.rounded_rectangle((470, 110, 620, 160), 10, fill=(250, 246, 236))      # softbox
    for k in range(5):
        d.line((500 - k * 30, 170 + k * 18, 330 - k * 10, 290 + k * 6), fill=(250, 246, 236, 120), width=2)
    f = font(34)
    d.text((600, 425), "略高 5–10°", font=f, fill=CYAN)
    d.text((470, 490), "距离 20–30 cm · 用 2× 镜头", font=f, fill=ink)
    d.text((440, 60), "柔光灯", font=f, fill=(250, 246, 236))
    d.text((120, 640), "表立起来：表枕 / 支架", font=f, fill=ink)
    d.text((40, 40), "侧视图", font=font(40), fill=ink)
    img.save(os.path.join(OUT, "diagram-side.png"), optimize=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    make_noir()
    make_ivory()
    make_dossier()
    for style, (_, _, w, h) in WINDOWS.items():
        make_guide(style)
        for name in SOURCES:
            place(name, w, h).save(os.path.join(OUT, f"photo-{style}-{name}.jpg"), quality=90)
    make_crop_guide()
    make_diagrams()
    print("assets written to", OUT)
