"""Turn the rendered sample covers (build/cover-NN.png) into the images the
guide pages use: style previews, the annotated composition sample and a
mock Douyin profile grid.

Run after build.js --preview has been rendered; see render.sh.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
ASSETS = os.path.join(HERE, "assets")
FONT = os.path.join(HERE, "..", "fonts", "NotoSansSC-Black.ttf")

STYLES = "ABC"           # covers 1-3 of the preview deck
GRID_FIRST = 4           # covers 4-12 are the grid, newest first
LIKES = ["1.3万", "548", "241", "80", "84", "301", "109", "50", "376"]
PINNED = 2


def cover(n):
    return Image.open(os.path.join(BUILD, f"cover-{n:02d}.png")).convert("RGB")


def heart(d, x, y, s, fill):
    r = s * 0.27
    d.ellipse((x, y, x + 2 * r, y + 2 * r), fill=fill)
    d.ellipse((x + s - 2 * r, y, x + s, y + 2 * r), fill=fill)
    d.polygon([(x + 0.02 * s, y + r * 1.3), (x + s - 0.02 * s, y + r * 1.3), (x + s / 2, y + s * 0.92)], fill=fill)


def grid_mockup():
    W, H = 1000, 1600
    img = Image.new("RGB", (W, H), (22, 24, 35))
    d = ImageDraw.Draw(img)
    f_tab = ImageFont.truetype(FONT, 38)
    f_like = ImageFont.truetype(FONT, 30)
    f_pin = ImageFont.truetype(FONT, 24)

    tabs = [("作品 23", True), ("喜欢", False), ("收藏", False)]
    for i, (t, on) in enumerate(tabs):
        cx = W * (i + 0.5) / 3
        d.text((cx, 70), t, font=f_tab, anchor="mm", fill=(255, 255, 255) if on else (140, 140, 150))
        if on:
            d.rounded_rectangle((cx - 40, 108, cx + 40, 114), 3, fill=(254, 44, 85))
    d.line((0, 140, W, 140), fill=(40, 42, 55), width=2)

    gap = 3
    cw = (W - 2 * gap) // 3
    ch = round(cw * 4 / 3)
    top = 146
    for i in range(9):
        r, c = divmod(i, 3)
        x, y = c * (cw + gap), top + r * (ch + gap)
        thumb = cover(GRID_FIRST + i).resize((cw, ch), Image.LANCZOS)
        img.paste(thumb, (x, y))
        shade = Image.new("L", (cw, 70), 0)
        sd = ImageDraw.Draw(shade)
        for k in range(70):
            sd.line((0, k, cw, k), fill=int(120 * k / 70))
        img.paste((0, 0, 0), (x, y + ch - 70, x + cw, y + ch), shade)
        heart(d, x + 14, y + ch - 46, 30, (255, 255, 255))
        d.text((x + 54, y + ch - 31), LIKES[i], font=f_like, anchor="lm", fill=(255, 255, 255))
        if i < PINNED:
            d.rounded_rectangle((x + 10, y + 10, x + 76, y + 46), 6, fill=(254, 196, 0))
            d.text((x + 43, y + 28), "置顶", font=f_pin, anchor="mm", fill=(30, 30, 30))

    H = top + 3 * ch + 2 * gap + 44
    img = img.crop((0, 0, W, H))
    # rounded phone-screen corners on a transparent background
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, H - 1), 56, fill=255)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    ImageDraw.Draw(out).rounded_rectangle((0, 0, W - 1, H - 1), 56, outline=(60, 62, 75), width=6)
    out.save(os.path.join(ASSETS, "grid-mockup.png"), optimize=True)


if __name__ == "__main__":
    for i, k in enumerate(STYLES, start=1):
        cover(i).resize((720, 960), Image.LANCZOS).save(os.path.join(ASSETS, f"preview-{k}.png"), optimize=True)
    sample = cover(1).convert("RGBA")
    sample = Image.alpha_composite(sample, Image.open(os.path.join(ASSETS, "guide.png")))
    sample.convert("RGB").resize((720, 960), Image.LANCZOS).save(os.path.join(ASSETS, "guide-sample.png"), optimize=True)
    grid_mockup()
    print("mockups written to", ASSETS)
