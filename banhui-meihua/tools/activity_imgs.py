"""Activity illustrations: clue cards, domino set-up, promise card, and panels for the generated scenes."""
import sys, os, math
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from gfx import *

OUT = sys.argv[1]
F_NOTE = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def check_badge(c, cx, cy, r, color):
    c.circle(cx, cy, r, fill=rgba(color))
    c.line([(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.35)], rgba(WHITE), r * 0.26)


# ================================================================ 环节一：奇怪线条线索卡
def clue_cards():
    W, H = 1937, 560
    c = Canvas(W, H, k=2)
    cards = [
        ('最美队伍线', '直、齐、不断', ST_GREEN, 'ok'),
        ('插队', '直线上小黑点', ST_BLUE, 'dot'),
        ('队伍脱节', '线条断裂', ST_ORANGE, 'gap'),
        ('队伍歪斜松散', '波浪形线条', ST_CORAL, 'wave'),
    ]
    gap = 22
    cw = (W - 20 - gap * 3) / 4
    for i, (head, cap, col, kind) in enumerate(cards):
        x0 = 10 + i * (cw + gap)
        b = [x0, 16, x0 + cw, H - 24]
        c.shadow(b, 26, color=col + (60,), blur=8, off=(0, 6))
        c.rrect(b, 26, fill=rgba(WHITE), outline=rgba(tint(col, 0.45)), width=3)
        c.rrect([b[0], b[1], b[2], b[1] + 90], 26, fill=rgba(col))
        c.d.rectangle(c.box([b[0], b[1] + 60, b[2], b[1] + 90]), fill=rgba(col))
        hs = 46
        while c.text_w(head, F_KUAILE, hs) > cw - 50:
            hs -= 2
        c.text(((b[0] + b[2]) / 2, b[1] + 48), head, F_KUAILE, hs, rgba(WHITE), anchor='mm')
        # drawing area
        lx0, lx1, ly = b[0] + 44, b[2] - 44, b[1] + 250
        lw = 14
        lc = rgba(shade(col, 0.1))
        if kind == 'ok':
            c.line([(lx0, ly), (lx1, ly)], lc, lw)
        elif kind == 'dot':
            c.line([(lx0, ly), (lx1, ly)], lc, lw)
            for fx in (0.38, 0.66):
                c.circle(lx0 + (lx1 - lx0) * fx, ly, 20, fill=rgba((40, 40, 40)))
        elif kind == 'gap':
            mid = (lx0 + lx1) / 2
            c.line([(lx0, ly), (mid - 40, ly)], lc, lw)
            c.line([(mid + 40, ly), (lx1, ly)], lc, lw)
            c.dashed([(mid - 30, ly), (mid + 30, ly)], rgba((190, 190, 190)), 4, 8, 8)
        else:
            pts = [(lx0 + t, ly + 38 * math.sin(t / 34)) for t in range(0, int(lx1 - lx0) + 1, 4)]
            c.line(pts, lc, lw)
        # corner mark
        if kind == 'ok':
            check_badge(c, b[2] - 52, b[1] + 150, 30, ST_GREEN)
        else:
            magnifier(c, b[2] - 60, b[1] + 142, 22, ring=rgba(NAVY), lens=rgba(SKY_L), handle=rgba(YELLOW), angle=45, ring_w=8)
        # caption
        c.rrect([b[0] + 30, b[3] - 120, b[2] - 30, b[3] - 40], 40, fill=rgba(tint(col, 0.85)))
        cs = 40
        while c.text_w(cap, F_KUAILE, cs) > cw - 90:
            cs -= 2
        c.text(((b[0] + b[2]) / 2, b[3] - 78), cap, F_KUAILE, cs, rgba(shade(col, 0.4)), anchor='mm')
    c.export().save(f'{OUT}/act_clues.png')


# ================================================================ 环节二：骨牌实验
def domino(c, x, base, h, face=(255, 250, 238), pip=(60, 60, 60)):
    w = h * 0.36
    c.rrect([x + 6, base - h - 4, x + w + 6, base - 4], 8, fill=rgba((0, 0, 0, 40)))
    c.rrect([x, base - h, x + w, base], 8, fill=rgba(face), outline=rgba((120, 110, 95)), width=2.5)
    c.line([(x + 6, base - h / 2), (x + w - 6, base - h / 2)], rgba((120, 110, 95)), 2.5)
    for py in (base - h * 0.75, base - h * 0.25):
        c.circle(x + w / 2, py, h * 0.05, fill=rgba(pip))


def domino_setup():
    W, H = 1937, 600
    c = Canvas(W, H, k=2)
    c.rrect([6, 6, W - 6, H - 6], 30, fill=rgba((255, 247, 232)), outline=rgba(tint(ST_ORANGE, 0.5)), width=3)
    rows = [('红色纸条（间隔近）', (232, 87, 79), 58, 160), ('蓝色纸条（间隔远）', (61, 139, 224), 168, 430)]
    for label, col, step, y in rows:
        # label chip
        lw = c.text_w(label, F_KUAILE, 44) + 60
        c.rrect([40, y, 40 + lw, y + 84], 42, fill=rgba(col))
        c.text((40 + lw / 2, y + 44), label, F_KUAILE, 44, rgba(WHITE), anchor='mm')
        # paper strip + dominoes
        sx0, sx1, base = 560, 1880, y + 112
        c.rrect([sx0, base - 6, sx1, base + 22], 8, fill=rgba(tint(col, 0.25)))
        x = sx0 + 110
        while x < sx1 - 60:
            domino(c, x, base - 2, 128)
            x += step
        # push arrow
        c.line([(sx0 + 14, base - 64), (sx0 + 84, base - 64)], rgba(ORANGE), 9)
        c.poly([(sx0 + 100, base - 64), (sx0 + 74, base - 84), (sx0 + 74, base - 44)], fill=rgba(ORANGE))
    c.export().save(f'{OUT}/act_domino.png')


# ================================================================ 环节四：排队承诺卡
def promise_card():
    W, H = 1300, 720
    c = Canvas(W, H, k=2)
    b = [20, 20, W - 20, H - 30]
    c.shadow(b, 30, color=(230, 120, 100, 70), blur=10, off=(0, 8))
    c.rrect(b, 30, fill=rgba((255, 251, 240)), outline=rgba(ST_CORAL), width=5)
    c.rrect([b[0] + 16, b[1] + 16, b[2] - 16, b[3] - 16], 22, outline=rgba(tint(ST_CORAL, 0.55)), width=2.5)
    c.star(150, 110, 30, rgba(YELLOW), outline=rgba(ORANGE), width=3)
    c.star(W - 150, 110, 30, rgba(YELLOW), outline=rgba(ORANGE), width=3)
    c.text((W / 2, 112), '排队承诺卡', F_KUAILE, 86, rgba(shade(ST_CORAL, 0.25)), anchor='mm')
    bead_line(c, 300, W - 300, 186, n=9, line_c=rgba(tint(ST_CORAL, 0.3)), r=8, lw=4)
    opts = ['不插队', '不大声喧哗', '紧跟前面同学']
    x = 120
    for o in opts:
        c.rrect([x, 250, x + 46, 296], 8, fill=rgba(WHITE), outline=rgba(NAVY), width=4)
        c.line([(x + 8, 272), (x + 20, 288), (x + 40, 258)], rgba(ST_GREEN), 7)
        c.text((x + 66, 274), o, F_SANS_B, 42, rgba(INK), anchor='lm')
        x += 66 + c.text_w(o, F_SANS_B, 42) + 90
    c.text((120, 380), '行动约定：', F_SANS_B, 42, rgba(NAVY), anchor='lm')
    for ly in (400, 488):
        c.line([(340 if ly == 400 else 120, ly), (W - 330, ly)], rgba((200, 185, 160)), 3)
    c.text((120, 572), '小侦探：', F_SANS_B, 42, rgba(NAVY), anchor='lm')
    c.line([(290, 592), (640, 592)], rgba((200, 185, 160)), 3)
    # gold detective badge sticker
    cx, cy = W - 190, 520
    c.poly([(cx - 46, cy + 40), (cx - 76, cy + 150), (cx - 30, cy + 128), (cx - 6, cy + 168), (cx + 2, cy + 52)], fill=rgba(ST_BLUE))
    c.poly([(cx + 46, cy + 40), (cx + 76, cy + 150), (cx + 30, cy + 128), (cx + 6, cy + 168), (cx - 2, cy + 52)], fill=rgba(ST_CORAL))
    c.circle(cx, cy, 96, fill=rgba((255, 196, 40)))
    c.circle(cx, cy, 80, fill=rgba((255, 218, 90)))
    c.star(cx, cy, 56, rgba((255, 248, 220)), outline=rgba(ORANGE), width=4)
    c.export().save(f'{OUT}/act_promise.png')


# ================================================================ panels for generated scenes
def scene_panel(name, src, W, H, color, extras):
    c = Canvas(W, H, k=2)
    c.rrect([6, 6, W - 6, H - 6], 40, fill=rgba(tint(color, 0.86)), outline=rgba(tint(color, 0.5)), width=3)
    img = Image.open(f'{OUT}/{src}')
    sc = min((W - 80) / img.width, (H - 60) / img.height)
    pw, ph = img.width * sc, img.height * sc
    px, py = (W - pw) / 2, H - 26 - ph
    c.ellipse([px + pw * 0.08, H - 52, px + pw * 0.92, H - 24], fill=shade(color, 0.3) + (55,))
    extras(c, px, py, pw, ph, 'under')
    c.paste(img, px, py, w=pw, h=ph)
    extras(c, px, py, pw, ph, 'over')
    c.export().save(f'{OUT}/act_{name}.png')


def palms_extras(c, px, py, pw, ph, layer):
    if layer != 'over':
        return
    # small force arrows towards the touching palms
    hx, hy = px + pw * 0.505, py + ph * 0.25
    for d in (-1, 1):
        x0 = hx + d * 150
        x1 = hx + d * 62
        c.line([(x0, hy), (x1 + d * 16, hy)], rgba(ORANGE), 9)
        c.poly([(x1, hy), (x1 + d * 26, hy - 18), (x1 + d * 26, hy + 18)], fill=rgba(ORANGE))
    c.sparkle(px + pw * 0.08, py + ph * 0.1, 22, rgba(YELLOW))
    c.sparkle(px + pw * 0.95, py + ph * 0.45, 18, rgba(ST_BLUE))


def train_extras(c, px, py, pw, ph, layer):
    if layer == 'under':
        # railway track under the little train
        ty = py + ph - 8
        for x in range(int(px), int(px + pw), 46):
            c.rrect([x, ty - 6, x + 26, ty + 18], 4, fill=rgba((176, 132, 96)))
        c.line([(px - 10, ty - 2), (px + pw + 10, ty - 2)], rgba((140, 150, 165)), 6)
        c.line([(px - 10, ty + 14), (px + pw + 10, ty + 14)], rgba((140, 150, 165)), 6)
        return
    for i, (fx, fy, s) in enumerate([(0.62, 0.06, 70), (0.78, 0.0, 56), (0.92, 0.08, 64)]):
        c.text((px + pw * fx, py + ph * fy), '♪♫'[i % 2], F_NOTE, s, rgba([ORANGE, ST_BLUE, ST_CORAL][i]), anchor='mm')


if __name__ == '__main__':
    clue_cards()
    domino_setup()
    promise_card()
    scene_panel('palms', 'scene_palms.png', 1200, 900, ST_ORANGE, palms_extras)
    scene_panel('train', 'scene_train.png', 1700, 900, ST_ORANGE, train_extras)
