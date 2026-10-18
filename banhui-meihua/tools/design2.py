"""v2 "侦探档案" design: graph-paper notebook page, file-tab section labels, case-folder stage banners."""
import sys, os, math, random
from PIL import Image, ImageDraw, ImageFilter, ImageChops
sys.path.insert(0, os.path.dirname(__file__))
from gfx import *

F_QK = os.path.expanduser('~/.fonts/QingKe.ttf')
INK = (30, 52, 96)            # deep navy, structure
ROYAL = (11, 75, 155)         # vest blue
MUSTARD = (242, 183, 5)       # cap yellow
MUSTARD_L = (255, 243, 205)
BRICK = (200, 66, 59)         # red thread / pins / stamps
KRAFT = (234, 215, 178)
KRAFT_D = (196, 164, 116)
PAPER = (252, 251, 246)
GRID = (226, 233, 242)
ST2 = [(47, 111, 208), (217, 83, 79), (42, 157, 143), (232, 155, 12)]   # 知 情 意 行

OUT = sys.argv[1] if len(sys.argv) > 1 else '.'


def char_img():
    return Image.open(f'{OUT}/char_full.png')


def pushpin(c, x, y, r=18, color=BRICK):
    c.circle(x + r * 0.25, y + r * 0.35, r, fill=(0, 0, 0, 50))
    c.circle(x, y, r, fill=rgba(color))
    c.circle(x, y, r * 0.62, fill=rgba(tint(color, 0.18)))
    c.circle(x - r * 0.35, y - r * 0.35, r * 0.28, fill=(255, 255, 255, 170))


def fingerprint(c, cx, cy, r, color, seed=3):
    """nested ellipse ridges, each broken by a couple of gaps"""
    rnd = random.Random(seed)
    lw = c.s(r * 0.032)
    for i in range(11):
        rr = r * (0.1 + i * 0.085)
        box = c.box([cx - rr * 0.78, cy - rr, cx + rr * 0.78, cy + rr * 0.95])
        a = rnd.uniform(0, 360)
        segs = rnd.choice([2, 3])
        for k in range(segs):
            span = 360 / segs - rnd.uniform(18, 40)
            c.d.arc(box, a, a + span, fill=color, width=lw)
            a += 360 / segs
    # whorl core
    c.d.arc(c.box([cx - r * 0.06, cy - r * 0.12, cx + r * 0.06, cy + r * 0.05]), 180, 360, fill=color, width=lw)


def stamp(c, cx, cy, r, glyph, color=BRICK, rot=-12, seed=1):
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
def page_frame():
    W, H = 1654, 2339                     # A4 @ 200 dpi
    c = Canvas(W, H, bg=rgba(PAPER), k=1)
    step = 39.37                          # 5 mm grid
    x = 0.0
    while x < W:
        c.d.line([(int(x), 0), (int(x), H)], fill=rgba(GRID), width=1)
        x += step
    y = 0.0
    while y < H:
        c.d.line([(0, int(y)), (W, int(y))], fill=rgba(GRID), width=1)
        y += step
    # binder strip with punched holes
    c.d.rectangle([0, 0, 72, H], fill=rgba(INK))
    c.d.rectangle([72, 0, 80, H], fill=rgba(MUSTARD))
    for i in range(24):
        yy = 70 + i * 96
        c.circle(36, yy + 3, 13, fill=(0, 0, 0, 90))
        c.circle(36, yy, 13, fill=rgba(PAPER))
    # notebook margin line
    c.d.line([(150, 0), (150, H)], fill=rgba(BRICK, 110), width=3)
    # fingerprint watermark, top right
    fingerprint(c, 1540, 130, 110, rgba(INK, 34))
    c.save(f'{OUT}/v2_page_bg.jpg', rgb_bg=WHITE, quality=90)


# ---------------------------------------------------------------- hero
def hero():
    W, H = 1937, 800
    c = Canvas(W, H, k=2)
    blk = [0, 30, W, H - 10]
    c.shadow(blk, 22, color=INK + (70,), blur=10, off=(0, 8))
    c.rrect(blk, 22, fill=rgba(INK))
    # blueprint grid clipped to the block
    g = Canvas(W, H, k=2)
    for x in range(0, W, 40):
        g.line([(x, blk[1]), (x, blk[3])], (255, 255, 255, 20), 1.4)
    for y in range(blk[1], blk[3], 40):
        g.line([(0, y), (W, y)], (255, 255, 255, 20), 1.4)
    m = Image.new('L', g.im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle(c.box(blk), radius=c.s(22), fill=255)
    g.im.putalpha(ImageChops.multiply(g.im.split()[3], m))
    c.im.alpha_composite(g.im)
    # mustard corner accent
    c.poly([(0, 30 + 22), (0, 230), (190, 30), (22, 30)], fill=rgba(MUSTARD, 235))
    # titles
    c.text((96, 210), '队伍侦探社', F_QK, 178, rgba((10, 25, 55)), anchor='lm')
    c.text((88, 200), '队伍侦探社', F_QK, 178, rgba(MUSTARD), anchor='lm')
    c.text((92, 380), '寻回“最美一条线”', F_QK, 112, rgba(WHITE), anchor='lm')
    # the beautiful queue: evenly spaced people on a straight line
    base = 560
    c.line([(96, base), (1130, base)], rgba(MUSTARD), 7)
    for i in range(9):
        person(c, 150 + i * 112, base - 4, 96, (255, 255, 255) if i % 2 == 0 else (150, 195, 245))
    # subtitle as kraft label with eyelet
    sub = '——二年级行为习惯主题班会'
    tw = c.text_w(sub, F_SANS_B, 44)
    lb = [96, 618, 96 + tw + 110, 708]
    c.rrect(lb, 10, fill=rgba(KRAFT))
    c.circle(lb[0] + 34, (lb[1] + lb[3]) / 2, 12, fill=rgba(INK))
    c.circle(lb[0] + 34, (lb[1] + lb[3]) / 2, 12, outline=rgba(KRAFT_D), width=4)
    c.text((lb[0] + 70, (lb[1] + lb[3]) / 2), sub, F_SANS_B, 44, rgba(INK), anchor='lm')
    # giant magnifier with the detective inside
    cx, cy, r = 1560, 400, 292
    a = math.radians(48)
    hx0, hy0 = cx + (r + 10) * math.cos(a), cy + (r + 10) * math.sin(a)
    hx1, hy1 = cx + (r + 230) * math.cos(a), cy + (r + 230) * math.sin(a)
    c.line([(hx0, hy0), (hx1, hy1)], rgba((120, 78, 40)), 64)
    c.circle(hx1, hy1, 32, fill=rgba((120, 78, 40)))
    c.circle(cx, cy, r, fill=rgba((214, 232, 252)))
    c.circle(cx, cy, r * 0.82, fill=rgba((232, 243, 255)))
    c.d.arc(c.box([cx - r * 0.78, cy - r * 0.78, cx + r * 0.78, cy + r * 0.78]), 200, 250, fill=rgba(WHITE), width=c.s(16))
    ch = char_img()
    ch_h = 700
    c.paste(ch, cx - ch.width * ch_h / ch.height / 2, H - 10 - ch_h - 30, h=ch_h)
    c.circle(cx, cy, r, outline=rgba(MUSTARD), width=30)
    # thread with pins at top right
    pushpin(c, 1250, 92, 16)
    pushpin(c, 1880, 70, 16)
    c.line([(1250, 92), (1560, 120), (1880, 70)], rgba(BRICK), 4)
    fingerprint(c, 1200, 690, 80, (255, 255, 255, 45))
    c.export().save(f'{OUT}/v2_hero.png')


# ---------------------------------------------------------------- section label
def tag(name, text):
    W, H = 1937, 112
    c = Canvas(W, H, k=2)
    size = 58
    inner = text.strip('【】')
    tw = c.text_w(inner, F_QK, size) + c.text_w('【】', F_QK, size)
    x0, y0, y1 = 44, 16, 96
    x1 = x0 + tw + 92
    c.shadow([x0, y0, x1, y1], 8, color=INK + (60,), blur=4, off=(0, 4))
    c.poly([(x0, y0), (x1, y0), (x1 + 34, (y0 + y1) / 2), (x1, y1), (x0, y1)], fill=rgba(INK))
    c.d.rectangle(c.box([x0, y1 - 8, x1, y1]), fill=rgba(MUSTARD))
    x = x0 + 44
    cy = (y0 + y1) / 2 - 3
    c.text((x, cy), '【', F_QK, size, rgba(MUSTARD), anchor='lm')
    x += c.text_w('【', F_QK, size)
    c.text((x, cy), inner, F_QK, size, rgba(WHITE), anchor='lm')
    x += c.text_w(inner, F_QK, size)
    c.text((x, cy), '】', F_QK, size, rgba(MUSTARD), anchor='lm')
    # rule to the right edge
    c.line([(x1 + 52, 72), (W - 30, 72)], rgba(INK, 140), 3)
    c.circle(W - 24, 72, 7, fill=rgba(INK))
    pushpin(c, x0 + 6, y0 + 8, 17)
    c.export().save(f'{OUT}/v2_tag_{name}.png')


# ---------------------------------------------------------------- stage folder banner
def folder(name, label, title, color, glyph, seed):
    W, H = 1937, 300
    c = Canvas(W, H, k=2)
    # tab
    tw = c.text_w(label, F_QK, 50)
    tab = [36, 14, 36 + tw + 90, 100]
    c.rrect(tab, 18, fill=rgba(color))
    c.text(((tab[0] + tab[2]) / 2, 54), label, F_QK, 50, rgba(WHITE), anchor='mm')
    # paper sheet peeking out
    c.rrect([tab[2] + 40, 36, 1500, 140], 6, fill=rgba(WHITE), outline=rgba((210, 214, 220)), width=2)
    for yy in (62, 86, 110):
        c.line([(tab[2] + 80, yy), (1460, yy)], rgba((205, 215, 230)), 2.5)
    # folder body
    body = [16, 92, W - 16, H - 14]
    c.shadow(body, 18, color=(120, 90, 40, 70), blur=8, off=(0, 6))
    c.rrect(body, 18, fill=rgba(KRAFT))
    c.rrect([body[0] + 12, body[1] + 12, body[2] - 12, body[3] - 12], 12, outline=rgba(KRAFT_D), width=3)
    c.d.rectangle(c.box([body[0] + 12, body[1] + 12, body[0] + 26, body[3] - 12]), fill=rgba(color))
    # title
    tsize = 92
    while c.text_w(title, F_QK, tsize) > 1480:
        tsize -= 2
    c.text((80, (body[1] + body[3]) / 2 + 2), title, F_QK, tsize, rgba(INK), anchor='lm')
    # clip + stamp
    paperclip(c, 1560, 40, 130)
    stamp(c, 1770, 196, 82, glyph, color=BRICK, rot=-14, seed=seed)
    c.export().save(f'{OUT}/v2_banner_{name}.png')


def icons():
    # pushpin icon
    c = Canvas(120, 120, k=3)
    c.line([(62, 64), (88, 104)], rgba((120, 125, 135)), 7)
    pushpin(c, 56, 52, 34)
    c.export().save(f'{OUT}/v2_ic_pin.png')
    # newspaper icon (no text)
    c = Canvas(140, 120, k=3)
    c.rrect([14, 14, 126, 106], 10, fill=rgba(WHITE), outline=rgba(INK), width=7)
    c.d.rectangle(c.box([30, 30, 70, 64]), fill=rgba(BRICK))
    for yy in (34, 48, 62):
        c.line([(80, yy), (110, yy)], rgba(INK), 5)
    for yy in (78, 92):
        c.line([(30, yy), (110, yy)], rgba(INK), 5)
    c.export().save(f'{OUT}/v2_ic_paper.png')
    # square bullet
    c = Canvas(60, 60, k=3)
    c.rrect([6, 6, 54, 54], 8, fill=rgba(INK))
    c.rrect([20, 20, 40, 40], 4, fill=rgba(MUSTARD))
    c.export().save(f'{OUT}/v2_ic_sq.png')
    # card icons drawn in the v2 palette (school, medal, home, megaphone) via emoji kept for colour
    for nm, ch in [('school', '🏫'), ('medal', '🏅'), ('home', '🏠'), ('mega', '📣')]:
        c = Canvas(140, 140, k=1)
        c.emoji(ch, 70, 70, 128)
        c.export().save(f'{OUT}/ic_{nm}.png')


if __name__ == '__main__':
    page_frame()
    hero()
    for nm, tx in [('bjfx', '【背景分析】'), ('bhmb', '【班会目标】'), ('bhzb', '【班会准备】'),
                   ('bhgc', '【班会过程】'), ('yshd', '【班会后延伸教育活动】'),
                   ('bssj', '【板书设计】'), ('bhfs', '【班会反思】')]:
        tag(nm, tx)
    folder('dr', '导入：', '侦探集结令——初识队伍一条线', INK, '★', 1)
    folder('h1', '环节一', '循线索·辨队列之乱', ST2[0], '知', 2)
    folder('h2', '环节二', '探现场·察隐患之危', ST2[1], '情', 3)
    folder('h3', '环节三', '解密码·立守护之法', ST2[2], '意', 4)
    folder('h4', '环节四', '守勋章·践文明之美', ST2[3], '行', 5)
    icons()
