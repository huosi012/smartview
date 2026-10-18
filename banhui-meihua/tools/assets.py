"""Decorative assets: page frame, hero title, section tags, stage banners, icons, divider."""
import sys, os, math, random
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(__file__))
from gfx import *

OUT = sys.argv[1]
CHAR = Image.open(f'{OUT}/char_full.png')          # 609x1203, 3x of original crop at (66,21)


def char_head(size=600, bg=None):
    """square head crop from the cutout (orig coords 100..280 x 8..188)"""
    ox, oy = 66, 21
    box = [(100 - ox) * 3, max(0, (6 - oy)) * 3, (280 - ox) * 3, (186 - oy) * 3]
    head = Image.new('RGBA', (box[2] - box[0], box[3] - box[1]), (0, 0, 0, 0))
    head.alpha_composite(CHAR.crop((max(0, box[0]), box[1], min(CHAR.width, box[2]), box[3])),
                         (max(0, -box[0]), 0))
    head = head.resize((size, size), Image.LANCZOS)
    return head


def medallion(size, ring=YELLOW, inner=SKY):
    c = Canvas(size, size, k=2)
    r = size / 2
    c.circle(r, r, r - 2, fill=rgba(WHITE))
    c.circle(r, r, r - 2, outline=rgba(ring), width=size * 0.07)
    c.circle(r, r, r - size * 0.1, fill=rgba(inner))
    img = c.export()
    head = char_head(int(size * 0.86))
    m = Image.new('L', (size, size), 0)
    ImageDraw.Draw(m).ellipse([size * 0.1, size * 0.1, size * 0.9, size * 0.9], fill=255)
    layer = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    layer.alpha_composite(head, (int(size * 0.07), int(size * 0.1)))
    layer.putalpha(ImageChops_multiply(layer.split()[3], m))
    img.alpha_composite(layer)
    return img


def ImageChops_multiply(a, b):
    from PIL import ImageChops
    return ImageChops.multiply(a, b)


# ---------------------------------------------------------------- page frame
def page_frame():
    W, H = 1654, 2339                     # A4 @ 200 dpi
    c = Canvas(W, H, bg=rgba(YELLOW_BG), k=1)
    # soft vertical gradient on the band
    grad = Image.new('RGBA', (W, H))
    gd = ImageDraw.Draw(grad)
    for y in range(H):
        t = y / H
        col = tuple(int(a + (b - a) * t) for a, b in zip((255, 238, 178), (255, 224, 140)))
        gd.line([(0, y), (W, y)], fill=col + (255,))
    c.im.alpha_composite(grad)
    # big soft blobs
    blob = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blob)
    bd.ellipse([-120, -150, 260, 230], fill=(255, 255, 255, 235))
    bd.ellipse([1420, 1900, 1900, 2420], fill=(205, 225, 250, 255))
    bd.ellipse([1500, 640, 1760, 900], fill=(255, 246, 214, 255))
    c.im.alpha_composite(blob.filter(ImageFilter.GaussianBlur(2)))
    # card
    card = [62, 74, W - 62, H - 70]
    c.shadow(card, 44, color=(190, 140, 40, 70), blur=16, off=(0, 8))
    c.rrect(card, 44, fill=rgba((255, 254, 250)))
    # thin dashed inner rule
    c.dashed_rrect([card[0] + 18, card[1] + 18, card[2] - 18, card[3] - 18], 32,
                   rgba(YELLOW, 150), 3, dash=14, gap=12)
    # plus signs / sparkles on the band
    for x, y, r in [(1500, 40, 22), (1610, 150, 16), (24, 820, 15), (1628, 1310, 13), (30, 1830, 18)]:
        c.plus(x, y, r, rgba(WHITE), 7)
    for x, y, r in [(1380, 30, 12), (34, 1180, 11), (1630, 1700, 10), (300, H - 30, 12)]:
        c.sparkle(x, y, r, rgba(WHITE))
    # magnifier peeking at top right corner
    magnifier(c, 1560, 70, 44, ring=rgba(NAVY), lens=rgba((228, 240, 253)), handle=rgba(YELLOW), angle=135)
    # footprints trail along the left band
    for i, (x, y) in enumerate([(22, 1960), (44, 2040), (22, 2120), (44, 2200)]):
        c.footprint(x, y, 22, 0, rgba(NAVY, 80))
    # question marks
    c.text((1625, 1010), '?', F_SANS_K, 52, rgba(NAVY, 70), anchor='mm')
    c.text((26, 520), '?', F_SANS_K, 40, rgba(NAVY, 60), anchor='mm')
    # little queue line at the bottom band
    bead_line(c, 520, 1134, H - 34, n=9, line_c=rgba(WHITE), r=7, lw=4)
    c.save(f'{OUT}/page_bg.jpg', rgb_bg=WHITE, quality=90)


# ---------------------------------------------------------------- hero title
def hero():
    W, H = 1937, 820
    c = Canvas(W, H, k=2)
    panel = [6, 40, W - 6, H - 10]
    c.shadow(panel, 46, color=(11, 75, 155, 40), blur=14, off=(0, 8))
    c.rrect(panel, 46, fill=rgba((233, 243, 255)))
    # dotted map grid
    for gx in range(40, W - 20, 46):
        for gy in range(80, H - 30, 46):
            c.circle(gx, gy, 2.6, fill=rgba(NAVY, 28))
    c.dashed_rrect([panel[0] + 16, panel[1] + 16, panel[2] - 16, panel[3] - 16], 34, rgba(NAVY, 90), 3.5, 16, 12)
    # sun disc behind character
    c.circle(1600, 430, 300, fill=rgba(YELLOW_L))
    c.circle(1600, 430, 230, fill=rgba((255, 228, 140)))
    # footprints path
    for i, (x, y) in enumerate([(1150, 752), (1215, 722), (1280, 752), (1345, 722)]):
        c.footprint(x, y, 22, 90, rgba(NAVY, 60))
    # titles
    c.text((110, 120), '队伍侦探社', F_KUAILE, 168, rgba(NAVY), stroke=10, stroke_fill=rgba(WHITE), spacing=6)
    c.text((110, 330), '寻回“最美一条线”', F_KUAILE, 118, rgba(ORANGE), stroke=9, stroke_fill=rgba(WHITE))
    # bead line = the beautiful queue line
    bead_line(c, 118, 1090, 528, n=11, line_c=rgba(NAVY), r=15, lw=6)
    # subtitle pill
    sub = '——二年级行为习惯主题班会'
    tw = c.text_w(sub, F_SANS_B, 46)
    c.rrect([110, 590, 110 + tw + 80, 680], 45, fill=rgba(NAVY))
    c.text((150, 635), sub, F_SANS_B, 46, rgba(WHITE), anchor='lm')
    # decorations
    c.star(1060, 150, 34, rgba(YELLOW), outline=rgba(NAVY), width=4)
    c.star(1130, 250, 20, rgba(ST_CORAL))
    c.sparkle(1000, 80, 18, rgba(ORANGE))
    c.sparkle(1880, 120, 20, rgba(ST_BLUE))
    c.star(1860, 640, 22, rgba(YELLOW), outline=rgba(NAVY), width=3)
    c.text((1280, 160), '?', F_SANS_K, 80, rgba(NAVY, 80), anchor='mm')
    # character
    ch_h = 770
    ch_w = CHAR.width * ch_h / CHAR.height
    c.paste(CHAR, 1600 - ch_w / 2, H - 10 - ch_h - 6, h=ch_h)
    out = c.export()
    out.save(f'{OUT}/hero.png')


# ---------------------------------------------------------------- section tag
def tag(name, text):
    size = 64
    tmp = Canvas(10, 10)
    tw = tmp.text_w(text, F_KUAILE, size)
    W, H = int(tw + 150), 128
    c = Canvas(W, H, k=2)
    c.rrect([4, 14, W - 4, H - 6], 26, fill=rgba(SKY))
    # yellow marker swipe under text
    c.rrect([78, 70, W - 34, 100], 14, fill=rgba(YELLOW, 200))
    magnifier(c, 44, 58, 17, ring=rgba(NAVY), lens=rgba(WHITE), handle=rgba(ORANGE), angle=45, ring_w=6)
    c.text((80, H / 2 + 4), text, F_KUAILE, size, rgba(NAVY_D), anchor='lm')
    c.star(W - 16, 18, 15, rgba(YELLOW), outline=rgba(NAVY), width=2.5)
    c.export().save(f'{OUT}/tag_{name}.png')
    return W, H


# ---------------------------------------------------------------- stage banners
def banner(name, label, title, color):
    W, H = 1830, 236
    c = Canvas(W, H, k=2)
    body = [120, 46, W - 60, H - 30]
    c.shadow(body, 70, color=color + (60,), blur=8, off=(0, 6))
    c.rrect(body, 70, fill=rgba(tint(color, 0.84)))
    c.dashed_rrect([body[0] + 12, body[1] + 12, body[2] - 12, body[3] - 12], 58, rgba(color), 4, 18, 12)
    # text
    size = 76
    lw = c.text_w(label, F_KUAILE, size)
    tw = c.text_w(title, F_KUAILE, size)
    gap = 26
    total = lw + gap + tw
    x0 = body[0] + 150 + (body[2] - body[0] - 150 - 130 - total) / 2
    cy = (body[1] + body[3]) / 2 + 4
    c.rrect([x0 - 22, cy - 50, x0 + lw + 22, cy + 46], 30, fill=rgba(color))
    c.text((x0, cy), label, F_KUAILE, size, rgba(WHITE), anchor='lm')
    c.text((x0 + lw + gap + 14, cy), title, F_KUAILE, size, rgba(NAVY_D), anchor='lm')
    # stars at the right end
    c.star(W - 150, 78, 30, rgba(YELLOW), outline=rgba(NAVY), width=3.5)
    c.star(W - 92, 132, 22, rgba(YELLOW), outline=rgba(NAVY), width=3)
    c.star(W - 160, 165, 15, rgba(color))
    # medallion at left
    med = medallion(220, ring=YELLOW, inner=tint(color, 0.6))
    c.paste(med, 0, 8, w=220)
    c.export().save(f'{OUT}/banner_{name}.png')


# ---------------------------------------------------------------- small icons
def icons():
    # activity magnifier
    c = Canvas(120, 120, k=3)
    magnifier(c, 50, 50, 30, ring=rgba(NAVY), lens=rgba((214, 233, 252)), handle=rgba(YELLOW), angle=45, ring_w=9)
    c.sparkle(96, 22, 12, rgba(ORANGE))
    c.export().save(f'{OUT}/ic_mag.png')
    # news badge
    c = Canvas(150, 150, k=3)
    c.circle(75, 75, 70, fill=rgba(NAVY))
    c.circle(75, 75, 70, outline=rgba((120, 170, 230)), width=6)
    c.d.arc(c.box([20, 20, 130, 130]), 200, 250, fill=rgba(WHITE, 160), width=c.s(5))
    c.text((75, 78), 'NEWS', F_SANS_K, 36, rgba(WHITE), anchor='mm')
    c.export().save(f'{OUT}/ic_news.png')
    # music note
    c = Canvas(120, 120, k=3)
    c.text((60, 64), '♫', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 96, rgba(ORANGE), anchor='mm')
    c.export().save(f'{OUT}/ic_note.png')
    # bullet dot
    c = Canvas(60, 60, k=3)
    c.circle(30, 30, 26, fill=rgba(YELLOW))
    c.circle(30, 30, 26, outline=rgba(ORANGE), width=6)
    c.export().save(f'{OUT}/ic_dot.png')
    # emoji icons for the extension cards
    for nm, ch in [('school', '🏫'), ('medal', '🏅'), ('home', '🏠'), ('mega', '📣')]:
        c = Canvas(140, 140, k=1)
        c.emoji(ch, 70, 70, 128)
        c.export().save(f'{OUT}/ic_{nm}.png')


def divider():
    W, H = 1937, 70
    c = Canvas(W, H, k=2)
    bead_line(c, 260, W - 260, 35, n=13, line_c=rgba(NAVY, 200), r=11, lw=4)
    magnifier(c, 170, 33, 18, ring=rgba(NAVY), lens=rgba(SKY_L), handle=rgba(YELLOW), angle=45, ring_w=6)
    c.star(W - 180, 35, 20, rgba(YELLOW), outline=rgba(NAVY), width=3)
    c.export().save(f'{OUT}/divider.png')


if __name__ == '__main__':
    page_frame()
    hero()
    sizes = {}
    for nm, tx in [('bjfx', '【背景分析】'), ('bhmb', '【班会目标】'), ('bhzb', '【班会准备】'),
                   ('bhgc', '【班会过程】'), ('yshd', '【班会后延伸教育活动】'),
                   ('bssj', '【板书设计】'), ('bhfs', '【班会反思】')]:
        sizes[nm] = tag(nm, tx)
    print(sizes)
    banner('dr', '导入：', '侦探集结令——初识队伍一条线', NAVY)
    banner('h1', '环节一', '循线索·辨队列之乱', ST_BLUE)
    banner('h2', '环节二', '探现场·察隐患之危', ST_ORANGE)
    banner('h3', '环节三', '解密码·立守护之法', ST_GREEN)
    banner('h4', '环节四', '守勋章·践文明之美', ST_CORAL)
    icons()
    divider()
    # character variants used in the doc
    CHAR.save(f'{OUT}/char_stand.png')
    CHAR.transpose(Image.FLIP_LEFT_RIGHT).save(f'{OUT}/char_stand_flip.png')
