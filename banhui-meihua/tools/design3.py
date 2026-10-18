"""v3: v1's bright palette with original structure — dot-grid page with wave bands, badge section labels, pastel case folders."""
import sys, os, math, random
from PIL import Image, ImageDraw, ImageFilter, ImageChops
sys.path.insert(0, os.path.dirname(__file__))
from gfx import *

F_QK = os.path.expanduser('~/.fonts/QingKe.ttf')     # stamp glyphs

OUT = sys.argv[1]
PAGE = (255, 252, 242)
BAND = (255, 214, 102)
BAND_L = (255, 233, 165)


def stamp(c, cx, cy, r, glyph, color=(200, 66, 59), rot=-12, seed=1):
    """red ink stamp: double ring + centre glyph, roughened"""
    k = c.k
    sc = Canvas(int(r * 2.4), int(r * 2.4), k=k)
    o = r * 1.2
    sc.circle(o, o, r, outline=rgba(color), width=r * 0.09)
    sc.circle(o, o, r * 0.8, outline=rgba(color), width=r * 0.035)
    if glyph == '★':
        sc.star(o, o, r * 0.5, rgba(color))
    else:
        sc.text((o, o + r * 0.04), glyph, F_QK, r * 0.95, rgba(color), anchor='mm')
    img = sc.im
    rnd = random.Random(seed)
    m = Image.new('L', img.size, 255)
    md = ImageDraw.Draw(m)
    for _ in range(int(r * 6)):
        x, y = rnd.randint(0, img.width), rnd.randint(0, img.height)
        s = rnd.randint(1, max(2, int(r * k * 0.03)))
        md.ellipse([x, y, x + s, y + s], fill=rnd.randint(0, 90))
    a = ImageChops.multiply(img.split()[3], m)
    img.putalpha(a.point(lambda v: int(v * 0.88)))
    img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    c.im.alpha_composite(img, (c.s(cx) - img.width // 2, c.s(cy) - img.height // 2))


def paperclip(c, x, y, h, color=(150, 160, 172), rot=8):
    pc = Canvas(int(h * 0.6), int(h * 1.2), k=c.k)
    w = h * 0.28
    lw = h * 0.06
    pc.rrect([h * 0.1, h * 0.05, h * 0.1 + w, h * 0.05 + h], w / 2, outline=rgba(color), width=lw)
    pc.rrect([h * 0.1 + w * 0.22, h * 0.2, h * 0.1 + w * 0.78, h * 0.05 + h * 0.8], w * 0.28, outline=rgba(color), width=lw)
    img = pc.im.rotate(rot, resample=Image.BICUBIC, expand=True)
    c.im.alpha_composite(img, (c.s(x), c.s(y)))


# ---------------------------------------------------------------- page


def wave(c, y0, amp, period, phase, fill, top=True):
    W = c.w
    pts = []
    for x in range(0, W + 10, 8):
        pts.append((x, y0 + amp * math.sin(x / period + phase)))
    if top:
        pts = [(0, 0)] + pts + [(W, 0)]
    else:
        pts = [(0, c.h)] + pts + [(W, c.h)]
    c.poly(pts, fill=fill)


# ---------------------------------------------------------------- page
def page_frame():
    W, H = 1654, 2339                     # A4 @ 200 dpi
    c = Canvas(W, H, bg=rgba(PAGE), k=1)
    for gx in range(20, W, 40):
        for gy in range(20, H, 40):
            c.circle(gx, gy, 1.8, fill=(236, 205, 140, 150))
    # top waves
    wave(c, 150, 16, 95, 0.8, rgba(BAND_L))
    wave(c, 118, 14, 80, 0.0, rgba(BAND))
    # bottom waves
    wave(c, H - 112, 14, 90, 1.6, rgba(BAND_L), top=False)
    wave(c, H - 80, 12, 75, 0.4, rgba(BAND), top=False)
    # queue of little people walking along the top band
    c.line([(1010, 92), (1560, 92)], rgba(WHITE), 5)
    for i in range(7):
        person(c, 1050 + i * 80, 90, 58, (255, 255, 255) if i % 2 == 0 else (120, 180, 240))
    # magnifier on the top band
    magnifier(c, 110, 58, 26, ring=rgba(NAVY), lens=rgba((232, 243, 255)), handle=rgba(ORANGE), angle=45, ring_w=8)
    c.sparkle(178, 34, 12, rgba(WHITE))
    c.sparkle(960, 46, 10, rgba(WHITE))
    # bead line on the bottom band
    bead_line(c, 560, 1094, H - 38, n=9, line_c=rgba(WHITE), r=8, lw=4)
    c.save(f'{OUT}/v3_page_bg.jpg', rgb_bg=WHITE, quality=90)


# ---------------------------------------------------------------- section label
def tag(name, text, color=ST_BLUE):
    W, H = 1937, 124
    c = Canvas(W, H, k=2)
    # badge
    c.circle(62, 62, 52, fill=rgba(tint(color, 0.15)))
    c.circle(62, 62, 52, outline=rgba(WHITE), width=6)
    magnifier(c, 56, 56, 19, ring=rgba(WHITE), lens=rgba(tint(color, 0.15)), handle=rgba(YELLOW), angle=45, ring_w=7)
    size = 64
    tw = c.text_w(text, F_KUAILE, size)
    x = 132
    c.rrect([x + 14, 72, x + tw - 6, 104], 16, fill=rgba(YELLOW, 190))
    c.text((x, 64), text, F_KUAILE, size, rgba(NAVY_D), anchor='lm')
    # dotted line of beads to the right edge
    cols = [ST_CORAL, YELLOW, ST_BLUE, ST_GREEN, ORANGE]
    xx, k = x + tw + 40, 0
    while xx < W - 20:
        c.circle(xx, 66, 6.5, fill=rgba(cols[k % len(cols)], 210))
        xx += 34
        k += 1
    c.export().save(f'{OUT}/v3_tag_{name}.png')


# ---------------------------------------------------------------- stage folder (bright)
def folder(name, label, title, color, glyph, seed, pose=None):
    """case folder banner; with a pose the character stands at the right end, popping out of the folder"""
    W = 1937
    dy = 90 if pose else 0
    H = 290 + dy
    c = Canvas(W, H, k=2)
    tsz = 50
    tw = c.text_w(label, F_KUAILE, tsz)
    tab = [40, 10 + dy, 40 + tw + 90, 104 + dy]
    c.rrect(tab, 26, fill=rgba(color))
    c.text(((tab[0] + tab[2]) / 2, 52 + dy), label, F_KUAILE, tsz, rgba(WHITE), anchor='mm')
    paper_end = 1100 if pose else 1470
    c.rrect([tab[2] + 36, 34 + dy, paper_end, 140 + dy], 10, fill=rgba(WHITE), outline=rgba(tint(color, 0.6)), width=2)
    for yy in (62, 88, 114):
        c.line([(tab[2] + 76, yy + dy), (paper_end - 40, yy + dy)], rgba(tint(color, 0.7)), 3)
    body = [16, 90 + dy, W - 16, H - 14]
    c.shadow(body, 34, color=color + (60,), blur=8, off=(0, 6))
    c.rrect(body, 34, fill=rgba(tint(color, 0.8)))
    c.rrect([body[0] + 12, body[1] + 12, body[2] - 12, body[3] - 12], 26, outline=rgba(tint(color, 0.35)), width=3)
    size = 84
    maxw = 1120 if pose else 1460
    while c.text_w(title, F_KUAILE, size) > maxw:
        size -= 2
    cy = (body[1] + body[3]) / 2 + 4
    c.text((86, cy), title, F_KUAILE, size, rgba(shade(color, 0.45)), anchor='lm')
    if pose:
        paperclip(c, 1150, 36 + dy, 128, color=(160, 170, 182))
        stamp(c, 1330, cy - 4, 74, glyph, color=shade(color, 0.05), rot=-12, seed=seed)
        img = Image.open(f'{OUT}/{pose}')
        box_w, box_h = 500, body[3] - 10
        sc = min(box_w / img.width, box_h / img.height)
        pw, ph = img.width * sc, img.height * sc
        # soft floor shadow on the folder
        c.ellipse([1672 - pw * 0.42, body[3] - 30, 1672 + pw * 0.42, body[3] - 6], fill=shade(color, 0.3) + (70,))
        c.paste(img, 1672 - pw / 2, body[3] - 14 - ph, w=pw, h=ph)
    else:
        paperclip(c, 1560, 36, 128, color=(160, 170, 182))
        stamp(c, 1772, 190, 78, glyph, color=shade(color, 0.05), rot=-12, seed=seed)
        c.sparkle(1880, 120, 16, rgba(YELLOW))
    c.export().save(f'{OUT}/v3_banner_{name}.png')
    return W, H


def icons():
    # newspaper icon in bright colours (no text)
    c = Canvas(140, 120, k=3)
    c.rrect([14, 14, 126, 106], 12, fill=rgba(WHITE), outline=rgba(ST_BLUE), width=7)
    c.rrect([30, 30, 70, 64], 4, fill=rgba(ORANGE))
    for yy in (34, 48, 62):
        c.line([(80, yy), (110, yy)], rgba(ST_BLUE), 5)
    for yy in (78, 92):
        c.line([(30, yy), (110, yy)], rgba(ST_BLUE), 5)
    c.export().save(f'{OUT}/v3_ic_paper.png')


if __name__ == '__main__':
    page_frame()
    for nm, tx in [('bjfx', '【背景分析】'), ('bhmb', '【班会目标】'), ('bhzb', '【班会准备】'),
                   ('bhgc', '【班会过程】'), ('yshd', '【班会后延伸教育活动】'),
                   ('bssj', '【板书设计】'), ('bhfs', '【班会反思】')]:
        tag(nm, tx)
    def pose(f):
        return f if os.path.exists(f'{OUT}/{f}') else None
    sizes = {
        'dr': folder('dr', '导入：', '侦探集结令——初识队伍一条线', (88, 140, 220), '★', 1, pose('char_intro.png')),
        'h1': folder('h1', '环节一', '循线索·辨队列之乱', ST_BLUE, '知', 2, pose('char_C.png')),
        'h2': folder('h2', '环节二', '探现场·察隐患之危', ST_ORANGE, '情', 3, pose('char_D.png')),
        'h3': folder('h3', '环节三', '解密码·立守护之法', ST_GREEN, '意', 4, pose('char_E.png')),
        'h4': folder('h4', '环节四', '守勋章·践文明之美', ST_CORAL, '行', 5, pose('char_F.png')),
    }
    print('banner sizes', sizes)
    icons()
