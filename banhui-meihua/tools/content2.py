"""v2 content images in the 侦探档案 style: evidence-board overview, survey worksheet, blackboard."""
import sys, os, math, random
from PIL import Image, ImageDraw, ImageFilter, ImageChops
sys.path.insert(0, os.path.dirname(__file__))
from gfx import *
from design2 import F_QK, INK, ROYAL, MUSTARD, MUSTARD_L, BRICK, KRAFT, KRAFT_D, PAPER, GRID, ST2, pushpin, stamp, fingerprint, paperclip

OUT = sys.argv[1]
CHAR = Image.open(f'{OUT}/char_full.png')


def card_layer(w, h, draw_fn, rot):
    cc = Canvas(w + 60, h + 60, k=2)
    cc.shadow([30, 30, 30 + w, 30 + h], 6, color=(60, 35, 10, 110), blur=7, off=(4, 8))
    draw_fn(cc, 30, 30, w, h)
    img = cc.im.rotate(rot, resample=Image.BICUBIC, expand=True)
    return img


# ================================================================ 班会过程总览：线索墙
def overview():
    W, H = 1937, 1180
    c = Canvas(W, H, k=2)
    # wooden frame + cork
    c.shadow([8, 8, W - 8, H - 8], 20, color=(0, 0, 0, 70), blur=8, off=(0, 6))
    c.rrect([8, 8, W - 8, H - 8], 20, fill=rgba((128, 88, 52)))
    cork = [30, 30, W - 30, H - 30]
    c.rrect(cork, 10, fill=rgba((205, 164, 116)))
    rnd = random.Random(11)
    sp = Image.new('RGBA', c.im.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sp)
    for _ in range(5200):
        x, y = rnd.uniform(cork[0], cork[2]), rnd.uniform(cork[1], cork[3])
        r = rnd.uniform(1.2, 3.6)
        col = rnd.choice([(150, 105, 62, 120), (232, 196, 150, 120), (120, 80, 45, 90)])
        sd.ellipse(c.box([x - r, y - r, x + r, y + r]), fill=col)
    c.im.alpha_composite(sp)

    stages = [
        ('知', '环节一', '循线索·辨队列之乱', ['选出“最美队伍线”', '奇怪线条大揭秘']),
        ('情', '环节二', '探现场·察隐患之危', ['实验剧场——现场勘查', '情境剧场——\n混乱与插队现场']),
        ('意', '环节三', '解密码·立守护之法', ['破译排队基础密码', '破译突发应变密码']),
        ('行', '环节四', '守勋章·践文明之美', ['侦探演练场——明礼实战', '填写排队承诺卡']),
    ]
    cw, chh = 410, 560
    pos = [(70, 560), (530, 455), (990, 350), (1450, 245)]
    rots = [2.2, -1.6, 1.4, -2.0]
    pins = []

    # 导入 note card
    def intro_card(cc, x, y, w, h):
        cc.rrect([x, y, x + w, y + h], 6, fill=rgba(MUSTARD_L))
        cc.d.rectangle(cc.box([x, y, x + 26, y + h]), fill=rgba(INK))
        lw = cc.text_w('导入', F_QK, 56)
        cc.rrect([x + 56, y + 40, x + 56 + lw + 44, y + 112], 10, fill=rgba(INK))
        cc.text((x + 78, y + 77), '导入', F_QK, 56, rgba(MUSTARD), anchor='lm')
        cc.text((x + 56 + lw + 76, y + 77), '侦探集结令——初识队伍一条线', F_QK, 56, rgba(INK), anchor='lm')
    iw = 1040
    img = card_layer(iw, 150, intro_card, -1.0)
    c.im.alpha_composite(img, (c.s(60) - c.s(30), c.s(62) - c.s(30)))
    pins.append((120, 196))

    for i, (zh, lab, title, acts) in enumerate(stages):
        col = ST2[i]

        def draw(cc, x, y, w, h, col=col, lab=lab, title=title, acts=acts, zh=zh, i=i):
            cc.rrect([x, y, x + w, y + h], 6, fill=rgba(WHITE))
            cc.d.rectangle(cc.box([x, y, x + w, y + 84]), fill=rgba(col))
            cc.text((x + 78, y + 46), lab, F_QK, 46, rgba(WHITE), anchor='lm')
            ts = 44
            while cc.text_w(title, F_QK, ts) > w - 40:
                ts -= 1
            cc.text((x + 22, y + 136), title, F_QK, ts, rgba(INK), anchor='lm')
            # ruled lines like an index card
            for yy in range(y + 182, y + h - 20, 46):
                cc.line([(x + 18, yy), (x + w - 18, yy)], rgba((214, 224, 238)), 2)
            yy = y + 200
            for j, a in enumerate(acts):
                lb = '活动一' if j == 0 else '活动二'
                lw2 = cc.text_w(lb, F_SANS_B, 27) + 26
                cc.rrect([x + 22, yy, x + 22 + lw2, yy + 42], 6, fill=rgba(tint(col, 0.82)))
                cc.text((x + 22 + lw2 / 2, yy + 21), lb, F_SANS_B, 27, rgba(shade(col, 0.3)), anchor='mm')
                yy += 56
                for ln in [w2 for part in a.split('\n') for w2 in cc.wrap(part, F_SANS_B, 32, w - 48)]:
                    cc.text((x + 24, yy + 20), ln, F_SANS_B, 32, rgba((40, 40, 40)), anchor='lm')
                    yy += 44
                yy += 20
            stamp(cc, x + w - 78, y + h - 76, 56, zh, color=BRICK, rot=-12 + i * 5, seed=20 + i)
        img = card_layer(cw, chh, draw, rots[i])
        x, y = pos[i]
        c.im.alpha_composite(img, (c.s(x) - c.s(30), c.s(y) - c.s(30)))
        pins.append((x + 40, y + 6))

    # medal at the top right, end of the thread
    c.emoji('🏅', 1800, 128, 130)
    pins.append((1800, 70))
    # red thread connecting the clues (slight sag)
    pts = []
    for (x0, y0), (x1, y1) in zip(pins, pins[1:]):
        for t in [k / 16 for k in range(17)]:
            sag = math.sin(math.pi * t) * 26
            pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t + sag))
    c.line([(x + 3, y + 5) for x, y in pts], (0, 0, 0, 60), 6)
    c.line(pts, rgba(BRICK), 5)
    for x, y in pins:
        pushpin(c, x, y, 18)
    c.export().save(f'{OUT}/v2_img_overview.png')


# ================================================================ 课前小调查
def checkbox(c, x, y, s=40):
    c.rrect([x, y, x + s, y + s], 6, fill=rgba(WHITE), outline=rgba(INK), width=3.5)


def survey():
    W, H = 1937, 2150
    c = Canvas(W, H, k=2)
    c.rrect([6, 6, W - 6, H - 6], 18, fill=rgba(PAPER), outline=rgba(INK), width=5)
    g = 46
    for x in range(24, W - 20, g):
        c.line([(x, 20), (x, H - 20)], rgba(GRID), 1.6)
    for y in range(24, H - 20, g):
        c.line([(20, y), (W - 20, y)], rgba(GRID), 1.6)
    # header band
    c.rrect([6, 6, W - 6, 210], 18, fill=rgba(INK))
    c.d.rectangle(c.box([6, 150, W - 6, 210]), fill=rgba(INK))
    c.d.rectangle(c.box([6, 204, W - 6, 216]), fill=rgba(MUSTARD))
    c.text((84, 112), '队伍侦探社·课前小调查', F_QK, 104, rgba(MUSTARD), anchor='lm')
    fingerprint(c, 1790, 108, 76, (255, 255, 255, 70))
    c.text((80, 288), '亲爱的小侦探们：', F_SANS_B, 46, rgba(INK), anchor='lm')
    intro = '侦探社要破解一桩神秘案件——为什么有的队伍整整齐齐，有的队伍却乱成一团？请做一名小小侦探，安静、诚实地回答几个小问题，不用写名字，放心写出真实想法'
    y = 362
    for ln in c.wrap(intro, F_SANS, 40, 1770):
        c.text((80, y), ln, F_SANS, 40, rgba((40, 40, 40)), anchor='lm')
        y += 60

    def head(b, num, q):
        c.shadow(b, 10, color=INK + (40,), blur=6, off=(0, 5))
        c.rrect(b, 10, fill=rgba(WHITE), outline=rgba((190, 202, 222)), width=3)
        c.d.rectangle(c.box([b[0], b[1] + 10, b[0] + 14, b[3] - 10]), fill=rgba(BRICK))
        c.rrect([b[0] + 40, b[1] + 30, b[0] + 104, b[1] + 94], 8, fill=rgba(INK))
        c.text((b[0] + 72, b[1] + 63), str(num), F_SANS_K, 42, rgba(MUSTARD), anchor='mm')
        c.text((b[0] + 128, b[1] + 62), q, F_SANS_B, 40, rgba(INK), anchor='lm')

    def qpanel(b, num, q, opts, cols=2):
        head(b, num, q)
        yy0 = b[1] + 152
        colw = (b[2] - b[0] - 90) / cols
        rows = (len(opts) + cols - 1) // cols
        for k, o in enumerate(opts):
            cx = b[0] + 64 + (k // rows) * colw
            yy = yy0 + (k % rows) * 78
            checkbox(c, cx, yy - 20)
            c.text((cx + 62, yy), o, F_SANS, 40, rgba((40, 40, 40)), anchor='lm')

    q1 = ['有人插队抢到我前面', '有人推我挤我', '有人大声吵闹队伍很乱', '队伍歪歪扭扭前后对不齐',
          '有人排着排着跑了队伍断了', '上下楼梯追跑打闹', '食堂接水拥挤抢位置', '我基本没遇到过排队问题']
    q2 = ['觉得不公平有点不舒服', '有点生气但只能忍着', '会被挤到踩到觉得危险', '觉得队伍很乱不知听谁的',
          '会提醒别人但人家不听', '有时自己也跟着乱插队吵闹', '没什么感觉已经习惯了']
    qpanel([50, 500, W - 50, 975], 1, '你遇到过下面这些排队问题吗？（可多选，打√）', q1)
    qpanel([50, 1005, W - 50, 1480], 2, '遇到这些排队问题时，你的心情或想法是怎样的？（打√，可多选）', q2)
    b3 = [50, 1510, 1420, 1890]
    head(b3, 3, '你觉得排队最重要的是什么？')
    c.text((b3[0] + 128, b3[1] + 122), '（请写下心里的一句话）', F_SANS_B, 36, rgba((90, 105, 135)), anchor='lm')
    for ly in (b3[1] + 230, b3[1] + 320):
        c.line([(b3[0] + 70, ly), (b3[2] - 60, ly)], rgba((150, 165, 190)), 3)
    c.text((80, H - 120), '谢谢你愿意当一名认真观察的小侦探，帮侦探社破案！', F_QK, 58, rgba(INK), anchor='lm')
    c.line([(80, H - 70), (1300, H - 70)], rgba(MUSTARD), 7)
    # detective inside a lens at the bottom right
    cx, cy, r = 1680, 1790, 220
    c.circle(cx, cy, r, fill=rgba((226, 238, 252)))
    ch_h = 600
    c.paste(CHAR, cx - CHAR.width * ch_h / CHAR.height / 2, H - 50 - ch_h, h=ch_h)
    c.circle(cx, cy, r, outline=rgba(MUSTARD), width=20)
    c.export().save(f'{OUT}/v2_img_survey.png')


# ================================================================ 板书设计
def paper(c, cx, cy, text, fg, bg, size=50, rot=0, pin=BRICK):
    tmp = Canvas(10, 10)
    tw = tmp.text_w(text, F_QK, size)
    w, h = int(tw + 56), int(size + 40)
    pc = Canvas(w + 20, h + 30, k=2)
    pc.shadow([10, 18, w + 10, h + 18], 4, color=(0, 0, 0, 90), blur=5, off=(2, 5))
    pc.rrect([10, 18, w + 10, h + 18], 4, fill=rgba(bg))
    pc.text((10 + w / 2, 18 + h / 2 + 2), text, F_QK, size, rgba(fg), anchor='mm')
    pc.circle(10 + w / 2, 18, 11, fill=rgba(pin))
    pc.circle(10 + w / 2 - 3, 15, 4, fill=rgba(WHITE, 160))
    img = pc.im.rotate(rot, resample=Image.BICUBIC, expand=True)
    c.im.alpha_composite(img, (c.s(cx) - img.width // 2, c.s(cy) - img.height // 2))


def board():
    W, H = 1937, 1100
    c = Canvas(W, H, k=2)
    c.shadow([10, 10, W - 10, H - 10], 14, color=(0, 0, 0, 80), blur=10, off=(0, 8))
    c.rrect([10, 10, W - 10, H - 18], 14, fill=rgba((92, 98, 108)))
    bb = [34, 34, W - 34, H - 42]
    c.rrect(bb, 8, fill=rgba((38, 74, 64)))
    rnd = random.Random(7)
    dust = Image.new('RGBA', c.im.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(dust)
    for _ in range(26):
        x, y = rnd.randint(80, W - 80), rnd.randint(80, H - 90)
        rx, ry = rnd.randint(60, 220), rnd.randint(20, 70)
        dd.ellipse(c.box([x - rx, y - ry, x + rx, y + ry]), fill=(255, 255, 255, rnd.randint(5, 11)))
    dust = dust.filter(ImageFilter.GaussianBlur(c.s(18)))
    m = Image.new('L', c.im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle(c.box(bb), radius=c.s(8), fill=255)
    dust.putalpha(ImageChops.multiply(dust.split()[3], m))
    c.im.alpha_composite(dust)
    c.rrect([300, H - 44, W - 300, H - 22], 6, fill=rgba((120, 126, 136)))
    for i, col in enumerate([(255, 255, 255), (255, 220, 90), (255, 150, 160), (140, 200, 255)]):
        c.rrect([380 + i * 70, H - 56, 430 + i * 70, H - 42], 6, fill=rgba(col))

    title = '队伍侦探社  寻回最美一条线'
    size = 84
    tw = c.text_w(title, F_QK, size)
    x = W / 2 - tw / 2 + 40
    fingerprint(c, x - 70, 168, 42, (255, 255, 255, 200))
    cols = [(255, 214, 92), (255, 255, 255)]
    for ch in title:
        if ch != ' ':
            c.text((x, 172), ch, F_QK, size, rgba(cols[0] if x < W / 2 else cols[1]), anchor='lm')
        x += c.text_w(ch, F_QK, size)
    for i, t in enumerate(['直', '齐', '不断']):
        paper(c, 1560 + i * 120 + (16 if i == 2 else 0), 290, t, INK, (255, 255, 255), size=46,
              rot=[4, -3, 3][i], pin=[ROYAL, MUSTARD, BRICK][i])
    paper(c, 330, 405, '没秩序', (190, 56, 50), (255, 222, 222), rot=-5)
    paper(c, 630, 390, '不公平', (190, 56, 50), (255, 222, 222), rot=4)
    wave = [(150 + t * 8, 640 + 45 * math.sin(t * 0.115)) for t in range(0, 86)]
    c.line(wave, rgba((255, 140, 140)), 10)
    red = (232, 87, 79)
    for t, tl in [(8, -10), (22, 8), (31, -14), (52, 12), (60, -6), (77, 10)]:
        px = 150 + t * 8
        py = 640 + 45 * math.sin(t * 0.115)
        person(c, px, py - 4, 120, red, tilt=tl)
    paper(c, 480, 830, '不安全', (190, 56, 50), (255, 222, 222), rot=-3)
    c.dashed([(880, 640), (1040, 640)], rgba((255, 255, 255, 220)), 8, 18, 14)
    c.poly([(1072, 640), (1036, 616), (1036, 664)], fill=rgba((255, 255, 255, 220)))
    paper(c, 1290, 455, '守秩序', (30, 110, 70), (220, 244, 228), rot=3)
    paper(c, 1590, 440, '有间隔', (30, 110, 70), (220, 244, 228), rot=-4)
    c.line([(1130, 670), (1800, 670)], rgba((150, 225, 170)), 10)
    for i in range(6):
        person(c, 1180 + i * 115, 666, 120, (76, 175, 110))
    paper(c, 1460, 830, '有先后', (30, 110, 70), (220, 244, 228), rot=2)
    c.export().save(f'{OUT}/v2_img_board.png')


if __name__ == '__main__':
    which = sys.argv[2:] or ['overview', 'survey', 'board']
    for w in which:
        globals()[w]()
