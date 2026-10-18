"""Cover title banner and small icons (v1 pieces kept in v3)."""
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


# ---------------------------------------------------------------- page frame
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
    hero_char = Image.open(f'{OUT}/char_A.png')
    ch_h = 770
    ch_w = hero_char.width * ch_h / hero_char.height
    c.paste(hero_char, 1600 - ch_w / 2, H - 10 - ch_h - 6, h=ch_h)
    out = c.export()
    out.save(f'{OUT}/hero.png')


# ---------------------------------------------------------------- section tag
# ---------------------------------------------------------------- stage banners
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


if __name__ == '__main__':
    hero()
    icons()
    CHAR.save(f'{OUT}/char_stand.png')
