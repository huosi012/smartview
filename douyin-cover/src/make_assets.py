"""Generate the raster assets the cover template uses.

Outputs (in src/assets/):
  mask.png           darkening gradient laid over every cover photo
  mask-<side>.png    the same gradient in four pieces, as placed in the deck
  guide.png          composition guide (dial target, text zone, blocked zones)
  photo-<name>.jpg   sample watch photos placed on the 1080x1440 cover grid
  diagram-top.png    shooting angle, seen from above
  diagram-side.png   camera height, seen from the side

Run: python3 -I src/make_assets.py
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTOS = os.path.join(HERE, "photos")
OUT = os.path.join(HERE, "assets")
FONT = os.path.join(HERE, "..", "fonts", "NotoSansSC-Black.ttf")

W, H = 1080, 1440
# Where every watch photo should put the dial: the standard composition.
DIAL_CENTER = (540, 500)
DIAL_DIAMETER = 560
TEXT_TOP = 860          # text block starts here
LIKES_TOP = 1290        # Douyin draws the like counter below this line
LIKES_RIGHT = 560
PIN_RIGHT, PIN_BOTTOM = 250, 150   # Douyin's 置顶 badge on pinned videos

GOLD = (214, 179, 110)
CYAN = (61, 245, 255)
RED = (255, 77, 79)


def font(size):
    return ImageFont.truetype(FONT, size)


def smoothstep(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


# The mask is cut into four pieces around a clear window over the dial, so
# clicking the dial in PowerPoint/WPS selects the photo instead of the mask.
MASK_WINDOW = (300, 340, 780, 760)   # x0, y0, x1, y1 - alpha is ~0 inside


def make_mask():
    y, x = np.mgrid[0:H, 0:W].astype(float)
    top = 0.62 * (1 - smoothstep(y / 330)) ** 1.4
    bottom = 0.97 * smoothstep((y - 760) / 520) ** 0.75
    d = np.hypot((x - 540) / 760, (y - 620) / 900)
    vignette = 0.5 * smoothstep((d - 0.45) / 0.55)
    alpha = 1 - (1 - top) * (1 - bottom) * (1 - vignette)
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., :3] = (8, 7, 6)
    rgba[..., 3] = (alpha * 255).round().astype(np.uint8)
    full = Image.fromarray(rgba, "RGBA")
    full.save(os.path.join(OUT, "mask.png"), optimize=True)
    x0, y0, x1, y1 = MASK_WINDOW
    pieces = {"top": (0, 0, W, y0), "bottom": (0, y1, W, H),
              "left": (0, y0, x0, y1), "right": (x1, y0, W, y1)}
    for k, box in pieces.items():
        full.crop(box).save(os.path.join(OUT, f"mask-{k}.png"), optimize=True)


def dashed_circle(draw, c, r, color, width, dash=18):
    n = int(2 * math.pi * r / dash)
    for i in range(0, n, 2):
        a0, a1 = 360 * i / n, 360 * (i + 1) / n
        draw.arc((c[0] - r, c[1] - r, c[0] + r, c[1] + r), a0, a1, fill=color, width=width)


def dashed_hline(draw, y, x0, x1, color, width, dash=22):
    for x in range(x0, x1, dash * 2):
        draw.line((x, y, min(x + dash, x1), y), fill=color, width=width)


def hatch(img, box, color, alpha=90, step=22):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=color + (alpha // 2,))
    for k in range(x0 - (y1 - y0), x1, step):
        d.line((k, y1, k + (y1 - y0), y0), fill=color + (alpha + 60,), width=3)
    clip = Image.new("L", img.size, 0)
    ImageDraw.Draw(clip).rectangle(box, fill=255)
    img.paste(Image.alpha_composite(img, layer), (0, 0), clip)


def label(draw, xy, text, size, color, anchor="la"):
    f = font(size)
    x, y = xy
    draw.text((x + 2, y + 2), text, font=f, fill=(0, 0, 0, 200), anchor=anchor)
    draw.text((x, y), text, font=f, fill=color + (255,), anchor=anchor)


def make_guide():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hatch(img, (0, LIKES_TOP, LIKES_RIGHT, H), RED)
    hatch(img, (0, 0, PIN_RIGHT, PIN_BOTTOM), RED)
    d = ImageDraw.Draw(img)
    cx, cy = DIAL_CENTER
    r = DIAL_DIAMETER // 2
    dashed_circle(d, DIAL_CENTER, r, CYAN + (255,), 5)
    d.line((cx - 40, cy, cx + 40, cy), fill=CYAN + (255,), width=4)
    d.line((cx, cy - 40, cx, cy + 40), fill=CYAN + (255,), width=4)
    label(d, (cx, cy - r - 18), "表盘放在圈内", 40, CYAN, "ms")
    dashed_hline(d, TEXT_TOP, 40, W - 40, CYAN + (255,), 4)
    label(d, (48, TEXT_TOP - 14), "↓ 以下是文字区，不要放表盘", 32, CYAN, "ls")
    label(d, (24, H - 34), "点赞数遮挡区", 36, RED, "ls")
    label(d, (18, PIN_BOTTOM - 18), "置顶标签", 30, RED, "ls")
    img.save(os.path.join(OUT, "guide.png"), optimize=True)


def place(name, dial_xy, dial_d, out_name=None, brightness=1.0):
    """Scale a watch photo so its dial sits on the standard spot, feathering
    the photo edges into a dark backdrop where it doesn't fill the frame."""
    src = Image.open(os.path.join(PHOTOS, name + ".jpg")).convert("RGB")
    s = DIAL_DIAMETER / dial_d
    sw, sh = round(src.width * s), round(src.height * s)
    big = src.resize((sw, sh), Image.LANCZOS).filter(
        ImageFilter.UnsharpMask(radius=2.2, percent=70, threshold=2))
    ox = round(DIAL_CENTER[0] - dial_xy[0] * s)
    oy = round(DIAL_CENTER[1] - dial_xy[1] * s)

    arr = np.asarray(src).astype(float)
    edge = np.concatenate([arr[:6].reshape(-1, 3), arr[:, :6].reshape(-1, 3),
                           arr[:, -6:].reshape(-1, 3)])
    base = edge.mean(0) * 0.35
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    glow = 1 - smoothstep(np.hypot((xx - 540) / 900, (yy - 520) / 900))
    backdrop = base[None, None, :] * (0.55 + 0.6 * glow[..., None])

    feather = 110
    a = np.ones((sh, sw))
    ramp = smoothstep(np.arange(feather) / feather)
    if ox > 0:
        a[:, :feather] *= ramp[None, :]
    if ox + sw < W:
        a[:, -feather:] *= ramp[::-1][None, :]
    if oy > 0:
        a[:feather, :] *= ramp[:, None]
    if oy + sh < H:
        a[-feather:, :] *= ramp[::-1][:, None]

    canvas = backdrop.copy()
    x0, y0 = max(ox, 0), max(oy, 0)
    x1, y1 = min(ox + sw, W), min(oy + sh, H)
    patch = np.asarray(big).astype(float)[y0 - oy:y1 - oy, x0 - ox:x1 - ox] * brightness
    pa = a[y0 - oy:y1 - oy, x0 - ox:x1 - ox][..., None]
    canvas[y0:y1, x0:x1] = patch * pa + canvas[y0:y1, x0:x1] * (1 - pa)
    out = Image.fromarray(canvas.clip(0, 255).astype(np.uint8))
    out.save(os.path.join(OUT, f"photo-{out_name or name}.jpg"), quality=90)


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
    # Seen from above: phone at the bottom, watch turned ~25 deg so the
    # crown end comes toward the lens and the dial faces front-left.
    img = Image.new("RGBA", (1000, 760), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    wc = (500, 250)
    rot = math.radians(25)

    def rp(x, y):
        return (wc[0] + x * math.cos(rot) - y * math.sin(rot),
                wc[1] + x * math.sin(rot) + y * math.cos(rot))
    # bracelet going back, case, crown
    d.polygon([rp(-70, -30), rp(70, -30), rp(60, -190), rp(-60, -190)], fill=dim)
    d.polygon([rp(-150, -40), rp(150, -40), rp(150, 30), rp(-150, 30)], fill=ink)
    d.polygon([rp(150, -22), rp(182, -22), rp(182, 8), rp(150, 8)], fill=GOLD)
    d.line((rp(-150, 30), rp(150, 30)), fill=GOLD, width=8)       # dial face
    d.line((500, 290, 500, 560), fill=dim, width=3)                 # lens axis
    arrow(d, rp(0, 40), rp(0, 200), GOLD, 5)                         # dial normal
    d.arc((500 - 170, 250 - 170, 500 + 170, 250 + 170), 90, 115, fill=CYAN, width=6)
    camera(d, (500, 610), 90, ink)
    f = font(34)
    d.text((330, 430), "约 25°", font=f, fill=CYAN)
    d.text((300, 660), "手机正对表头，竖拍 3:4", font=f, fill=ink)
    d.text((700, 300), "表冠朝右\n露出侧面", font=f, fill=GOLD, spacing=8)
    d.text((40, 40), "俯视图", font=font(40), fill=ink)
    img.save(os.path.join(OUT, "diagram-top.png"), optimize=True)

    # Seen from the side: dial upright, phone level or slightly above.
    img = Image.new("RGBA", (1000, 760), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((60, 600, 940, 610), fill=dim)                      # table
    d.rounded_rectangle((210, 470, 330, 600), 16, fill=dim)        # stand
    d.rounded_rectangle((230, 300, 290, 520), 20, fill=ink)        # watch, dial facing right
    d.line((292, 310, 292, 510), fill=GOLD, width=8)
    centre = (292, 410)
    cam = (800, 330)
    camera(d, cam, 180 - math.degrees(math.atan2(410 - 330, 800 - 292)), ink)
    d.line((cam, centre), fill=CYAN, width=4)
    dashed_hline(d, 410, 300, 860, dim + (255,), 3, 14)
    d.arc((292 - 330, 410 - 330, 292 + 330, 410 + 330), 351, 360, fill=CYAN, width=6)
    f = font(34)
    d.text((640, 420), "略高 5–10°", font=f, fill=CYAN)
    d.text((560, 210), "距离 20–30 cm\n用 2× 镜头", font=f, fill=ink, spacing=8)
    d.text((120, 640), "表立起来：表枕 / 支架", font=f, fill=ink)
    d.text((40, 40), "侧视图", font=font(40), fill=ink)
    img.save(os.path.join(OUT, "diagram-side.png"), optimize=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    make_mask()
    make_guide()
    # dial centre (x, y) and outer diameter, in source-photo pixels
    place("omega-seamaster", (148, 222), 205, brightness=1.05)
    place("rolex-dj-black", (185, 215), 270)
    place("gp-1945", (150, 232), 205)
    place("breguet-a", (150, 212), 280)
    place("montblanc", (160, 222), 225)
    place("iwc-portugieser", (166, 152), 300)
    place("chopard-luc", (160, 142), 270)
    place("breguet-b", (152, 218), 280)
    place("rolex-dj-white", (180, 118), 290)
    make_diagrams()
    print("assets written to", OUT)
