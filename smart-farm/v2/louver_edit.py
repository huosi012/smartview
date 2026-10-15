"""Photo edit of the corridor-end louver corner (client's note: seal outside with glass,
LED strips inside, potted plants for observation).

    python louver_edit.py  ->  renders/louver_corner.jpg
"""
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "photos", "p_louver.jpg")
OUT = os.path.join(HERE, "renders", "louver_corner.jpg")
def _tone(im):
    rgb = ImageEnhance.Brightness(ImageEnhance.Color(im.convert("RGB")).enhance(0.72)).enhance(0.86)
    rgb = rgb.filter(ImageFilter.GaussianBlur(0.7))
    return Image.merge("RGBA", (*rgb.split(), im.split()[3]))


POTS = [_tone(Image.open(os.path.join(HERE, "tex", "pots", f"pot{i}.png")).convert("RGBA")) for i in range(6)]

VP = (1250, 620)                       # vanishing point of the left wall's horizontal lines
LEFT_X = (380, 738)
LEFT_FIN_BOTTOMS = [230, 455, 675]     # y at x=380 of each fin's underside (LED strip line)
BACK_X = (842, 1218)
BACK_FIN_BOTTOMS = [(505, 470), (598, 565), (688, 662), (780, 760)]   # (y at left, y at right)
LEFT_REGION = [(373, 8), (748, 330), (752, 862), (388, 1048)]
BACK_REGION = [(752, 362), (1228, 362), (1228, 838), (752, 862)]


def left_line_y(y380, x):
    return y380 + (VP[1] - y380) * (x - 380) / (VP[0] - 380)


def glass(img):
    """Tint and add reflections over the louver openings (non-white pixels inside the regions)."""
    W, H = img.size
    region = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(region)
    d.polygon(LEFT_REGION, fill=255)
    d.polygon(BACK_REGION, fill=255)
    hsv = img.convert("HSV")
    s = hsv.split()[1].point(lambda v: 255 if v > 55 else 0)
    v = hsv.split()[2].point(lambda q: 255 if q < 150 else 0)
    opening = ImageChops.multiply(region, ImageChops.lighter(s, v)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.5))
    tint = Image.new("RGB", (W, H), (186, 205, 214))
    glassy = Image.blend(img, tint, 0.22)
    streak = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(streak)
    for x0, wdt in ((430, 70), (560, 30), (900, 90), (1080, 40)):
        sd.polygon([(x0, 0), (x0 + wdt, 0), (x0 + wdt - 420, H), (x0 - 420, H)], fill=70)
    streak = streak.filter(ImageFilter.GaussianBlur(25))
    glassy = Image.composite(Image.new("RGB", (W, H), (245, 248, 250)), glassy, streak)
    return Image.composite(glassy, img, opening)


def led(img):
    W, H = img.size
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    core = Image.new("RGB", (W, H), (0, 0, 0))
    g, c = ImageDraw.Draw(glow), ImageDraw.Draw(core)
    lines = []
    for y380 in LEFT_FIN_BOTTOMS:
        lines.append(((LEFT_X[0], y380 + 3), (LEFT_X[1], left_line_y(y380, LEFT_X[1]) + 3)))
    for yl, yr in BACK_FIN_BOTTOMS:
        lines.append(((BACK_X[0], yl + 2), (BACK_X[1], yr + 2)))
    for a, b in lines:
        g.line((a, b), fill=(255, 196, 120), width=26)
        c.line((a, b), fill=(255, 244, 220), width=4)
    glow = glow.filter(ImageFilter.GaussianBlur(14))
    out = ImageChops.screen(img, ImageEnhance.Brightness(glow).enhance(0.75))
    out = ImageChops.screen(out, core.filter(ImageFilter.GaussianBlur(1)))
    # warm wash on the fin tops just below each strip
    wash = Image.new("RGB", (W, H), (0, 0, 0))
    wd = ImageDraw.Draw(wash)
    for a, b in lines:
        wd.polygon([a, b, (b[0], b[1] + 90), (a[0], a[1] + 90)], fill=(70, 48, 20))
    return ImageChops.screen(out, wash.filter(ImageFilter.GaussianBlur(30)))


def plants(img):
    rnd = random.Random(5)
    rows = []
    # (start, end, height_at_start_px, height_at_end_px, count)
    rows.append(((400, 612), (728, 614), 100, 64, 5))           # left wall eye-level fin
    rows.append(((440, 982), (728, 858), 125, 84, 4))           # left wall sill
    rows.append(((860, 642 + 22), (1205, 618 + 22), 58, 52, 6))    # back wall fin 3 top
    rows.append(((860, 742 + 20), (1205, 722 + 20), 60, 54, 6))    # back wall fin 4 top
    rows.append(((860, 834), (1205, 832), 64, 58, 6))              # back wall sill
    out = img.convert("RGBA")
    for (a, b, h0, h1, n) in rows:
        for k in range(n):
            t = (k + 0.5) / n
            x = a[0] + (b[0] - a[0]) * t
            y = a[1] + (b[1] - a[1]) * t
            h = int(h0 + (h1 - h0) * t)
            spr = POTS[rnd.randrange(6)]
            bbox = spr.getbbox()
            spr = spr.crop(bbox)
            w = int(spr.width * h / spr.height)
            spr = spr.resize((w, h), Image.LANCZOS)
            shadow = Image.new("RGBA", (int(w * 1.1), max(4, h // 8)), (0, 0, 0, 0))
            ImageDraw.Draw(shadow).ellipse((0, 0, shadow.width - 1, shadow.height - 1), fill=(0, 0, 0, 70))
            out.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(3)), (int(x - shadow.width / 2), int(y - shadow.height / 2)))
            out.alpha_composite(spr, (int(x - w / 2), int(y - h)))
    return out.convert("RGB")


def main():
    img = Image.open(SRC).convert("RGB")
    img = glass(img)
    img = plants(img)
    img = led(img)
    # a small label plate on the side wall
    d = ImageDraw.Draw(img)
    from PIL import ImageFont
    f = ImageFont.truetype("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 30)
    d.rounded_rectangle((1262, 640, 1300, 900), radius=6, fill=(31, 77, 58))
    for k, ch in enumerate("植物观察窗"):
        d.text((1281, 668 + k * 48), ch, font=f, fill=(247, 245, 238), anchor="mm")
    img.save(OUT, quality=93)
    print("saved", OUT)


if __name__ == "__main__":
    main()
