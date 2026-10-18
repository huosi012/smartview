"""Redrawn content images: process overview (staircase), pre-class survey, blackboard design."""
import sys, os, math, random
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(__file__))
from gfx import *

OUT = sys.argv[1]
CHAR = Image.open(f'{OUT}/char_full.png')


# ================================================================ 班会过程总览
def overview():
    W, H = 1937, 1110
    c = Canvas(W, H, k=2)
    panel = [6, 6, W - 6, H - 6]
    c.rrect(panel, 44, fill=rgba((255, 249, 232)))
    c.dashed_rrect([panel[0] + 14, panel[1] + 14, panel[2] - 14, panel[3] - 14], 34, rgba(YELLOW), 4, 16, 12)
    stages = [
        ('知', '环节一', '循线索·辨队列之乱', ['选出“最美队伍线”', '奇怪线条大揭秘']),
        ('情', '环节二', '探现场·察隐患之危', ['实验剧场——现场勘查', '情境剧场——\n混乱与插队现场']),
        ('意', '环节三', '解密码·立守护之法', ['破译排队基础密码', '破译突发应变密码']),
        ('行', '环节四', '守勋章·践文明之美', ['侦探演练场——明礼实战', '填写排队承诺卡']),
    ]
    x0, gap = 44, 26
    colw = (W - 2 * x0 - 3 * gap) / 4
    floor = H - 44
    card_h = 510
    for i, (zh, lab, title, acts) in enumerate(stages):
        col = STAGES[i]
        x = x0 + i * (colw + gap)
        sh = 132 + i * 74
        st = floor - sh
        # step block
        c.shadow([x, st, x + colw, floor], 22, color=col + (70,), blur=8, off=(0, 5))
        c.rrect([x, st, x + colw, floor], 22, fill=rgba(col))
        c.rrect([x + 16, st + 10, x + colw - 16, st + 20], 5, fill=rgba(WHITE, 60))
        c.text((x + colw / 2, st + sh / 2 + 6), zh, F_KUAILE, 104, rgba(WHITE), anchor='mm')
        # card
        top = st - 24 - card_h
        cb = [x, top, x + colw, st - 24]
        c.shadow(cb, 26, color=col + (70,), blur=10, off=(0, 6))
        c.rrect(cb, 26, fill=rgba(WHITE), outline=rgba(col), width=4)
        # little pointer from card to step
        cx = x + colw / 2
        c.poly([(cx - 18, st - 27), (cx + 18, st - 27), (cx, st - 6)], fill=rgba(col))
        # header pill
        pw = c.text_w(lab, F_SANS_B, 32) + 44
        c.rrect([x + 24, top + 26, x + 24 + pw, top + 80], 27, fill=rgba(col))
        c.text((x + 24 + pw / 2, top + 53), lab, F_SANS_B, 32, rgba(WHITE), anchor='mm')
        # title (fit to width)
        tsize = 46
        while c.text_w(title, F_KUAILE, tsize) > colw - 44:
            tsize -= 1
        c.text((x + 22, top + 132), title, F_KUAILE, tsize, rgba(NAVY_D), anchor='lm')
        c.dashed([(x + 24, top + 180), (x + colw - 24, top + 180)], rgba(col, 160), 3, 10, 8)
        y = top + 204
        for j, a in enumerate(acts):
            lb = '活动一' if j == 0 else '活动二'
            lw = c.text_w(lb, F_SANS_B, 28) + 30
            c.rrect([x + 24, y, x + 24 + lw, y + 44], 22, fill=rgba(tint(col, 0.8)))
            c.text((x + 24 + lw / 2, y + 22), lb, F_SANS_B, 28, rgba(shade(col, 0.25)), anchor='mm')
            y += 58
            for ln in [w for part in a.split('\n') for w in c.wrap(part, F_SANS_B, 33, colw - 50)]:
                c.text((x + 26, y + 22), ln, F_SANS_B, 33, rgba(INK), anchor='lm')
                y += 46
            y += 18
    # 导入 pill (start)
    lab, title = '导入', '侦探集结令——初识队伍一条线'
    tw = c.text_w(title, F_KUAILE, 50)
    px0, py0 = 44, 44
    pw = 200 + tw + 60
    c.shadow([px0, py0, px0 + pw, py0 + 108], 54, color=NAVY + (60,), blur=8, off=(0, 5))
    c.rrect([px0, py0, px0 + pw, py0 + 108], 54, fill=rgba(NAVY))
    c.rrect([px0 + 14, py0 + 14, px0 + 168, py0 + 94], 40, fill=rgba(YELLOW))
    c.text((px0 + 91, py0 + 56), lab, F_KUAILE, 50, rgba(NAVY_D), anchor='mm')
    c.text((px0 + 190, py0 + 58), title, F_KUAILE, 50, rgba(WHITE), anchor='lm')
    # journey arrow from 导入 to the medal
    ax0 = px0 + pw + 30
    pts = [(ax0, 98), (ax0 + 120, 80), (ax0 + 260, 74), (1690, 86)]
    c.dashed(pts, rgba(ORANGE), 6, 18, 14)
    c.poly([(1700, 86), (1672, 68), (1676, 104)], fill=rgba(ORANGE))
    c.emoji('🏅', 1790, 86, 108)
    c.sparkle(1880, 40, 18, rgba(YELLOW))
    c.sparkle(1716, 30, 12, rgba(ST_BLUE))
    c.export().save(f'{OUT}/img_overview.png')


# ================================================================ 课前小调查
def checkbox(c, x, y, s=32):
    c.rrect([x, y, x + s, y + s], 7, fill=rgba(WHITE), outline=rgba(NAVY), width=3.5)


def survey():
    W, H = 1937, 2150
    c = Canvas(W, H, k=2)
    panel = [6, 6, W - 6, H - 6]
    c.rrect(panel, 48, fill=rgba((236, 244, 253)))
    for gx in range(36, W - 20, 46):
        for gy in range(36, H - 20, 46):
            c.circle(gx, gy, 2.4, fill=rgba(NAVY, 22))
    c.dashed_rrect([panel[0] + 16, panel[1] + 16, panel[2] - 16, panel[3] - 16], 36, rgba(NAVY, 110), 4, 18, 13)
    # title
    magnifier(c, 118, 120, 46, ring=rgba(NAVY), lens=rgba(WHITE), handle=rgba(ORANGE), angle=45, ring_w=13)
    c.text((200, 124), '队伍侦探社·课前小调查', F_KUAILE, 104, rgba(NAVY), anchor='lm', stroke=7, stroke_fill=rgba(WHITE))
    c.star(1700, 84, 34, rgba(YELLOW), outline=rgba(NAVY), width=4)
    c.text((1830, 150), '?', F_SANS_K, 110, rgba(ST_BLUE, 120), anchor='mm')
    c.star(1640, 190, 20, rgba(ST_CORAL))
    c.sparkle(1880, 44, 20, rgba(ORANGE))
    c.text((80, 262), '亲爱的小侦探们：', F_SANS_B, 46, rgba(NAVY_D), anchor='lm')
    intro = '侦探社要破解一桩神秘案件——为什么有的队伍整整齐齐，有的队伍却乱成一团？请做一名小小侦探，安静、诚实地回答几个小问题，不用写名字，放心写出真实想法'
    y = 336
    for ln in c.wrap(intro, F_SANS, 40, 1770):
        c.text((80, y), ln, F_SANS, 40, rgba(INK), anchor='lm')
        y += 60

    def qpanel(b, num, q, opts, cols=2):
        c.shadow(b, 30, color=NAVY + (40,), blur=8, off=(0, 5))
        c.rrect(b, 30, fill=rgba(WHITE), outline=rgba((176, 205, 240)), width=3)
        c.circle(b[0] + 60, b[1] + 62, 34, fill=rgba(ORANGE))
        c.text((b[0] + 60, b[1] + 64), str(num), F_SANS_K, 44, rgba(WHITE), anchor='mm')
        c.text((b[0] + 116, b[1] + 62), q, F_SANS_B, 40, rgba(NAVY_D), anchor='lm')
        yy0 = b[1] + 150
        colw = (b[2] - b[0] - 80) / cols
        rows = (len(opts) + cols - 1) // cols
        for k, o in enumerate(opts):
            cx = b[0] + 60 + (k // rows) * colw
            yy = yy0 + (k % rows) * 78
            checkbox(c, cx, yy - 20, 40)
            c.text((cx + 64, yy), o, F_SANS, 40, rgba(INK), anchor='lm')

    q1 = ['有人插队抢到我前面', '有人推我挤我', '有人大声吵闹队伍很乱', '队伍歪歪扭扭前后对不齐',
          '有人排着排着跑了队伍断了', '上下楼梯追跑打闹', '食堂接水拥挤抢位置', '我基本没遇到过排队问题']
    q2 = ['觉得不公平有点不舒服', '有点生气但只能忍着', '会被挤到踩到觉得危险', '觉得队伍很乱不知听谁的',
          '会提醒别人但人家不听', '有时自己也跟着乱插队吵闹', '没什么感觉已经习惯了']
    qpanel([50, 470, W - 50, 945], 1, '你遇到过下面这些排队问题吗？（可多选，打√）', q1)
    qpanel([50, 980, W - 50, 1455], 2, '遇到这些排队问题时，你的心情或想法是怎样的？（打√，可多选）', q2)
    b3 = [50, 1490, 1440, 1880]
    c.shadow(b3, 30, color=NAVY + (40,), blur=8, off=(0, 5))
    c.rrect(b3, 30, fill=rgba(WHITE), outline=rgba((176, 205, 240)), width=3)
    c.circle(b3[0] + 60, b3[1] + 62, 34, fill=rgba(ORANGE))
    c.text((b3[0] + 60, b3[1] + 64), '3', F_SANS_K, 44, rgba(WHITE), anchor='mm')
    c.text((b3[0] + 116, b3[1] + 62), '你觉得排队最重要的是什么？', F_SANS_B, 40, rgba(NAVY_D), anchor='lm')
    c.text((b3[0] + 116, b3[1] + 122), '（请写下心里的一句话）', F_SANS_B, 36, rgba((90, 120, 170)), anchor='lm')
    for ly in (b3[1] + 230, b3[1] + 320):
        c.dashed([(b3[0] + 70, ly), (b3[2] - 60, ly)], rgba((150, 180, 220)), 3.5, 16, 10)
    c.text((80, H - 120), '谢谢你愿意当一名认真观察的小侦探，帮侦探社破案！', F_KUAILE, 58, rgba(NAVY), anchor='lm')
    bead_line(c, 80, 1300, H - 52, n=11, line_c=rgba(NAVY, 160), r=10, lw=4)
    # character at bottom right
    ch_h = 640
    c.circle(1675, 1800, 210, fill=rgba(YELLOW_L))
    c.paste(CHAR, 1675 - CHAR.width * ch_h / CHAR.height / 2, H - 40 - ch_h, h=ch_h)
    c.export().save(f'{OUT}/img_survey.png')


# ================================================================ 板书设计
def paper(c, cx, cy, text, fg, bg, size=50, rot=0, magnet=ST_CORAL):
    tmp = Canvas(10, 10)
    tw = tmp.text_w(text, F_KUAILE, size)
    w, h = int(tw + 56), int(size + 40)
    pc = Canvas(w + 20, h + 30, k=2)
    pc.shadow([10, 18, w + 10, h + 18], 10, color=(0, 0, 0, 90), blur=5, off=(2, 5))
    pc.rrect([10, 18, w + 10, h + 18], 10, fill=rgba(bg))
    pc.text((10 + w / 2, 18 + h / 2 + 2), text, F_KUAILE, size, rgba(fg), anchor='mm')
    pc.circle(10 + w / 2, 18, 11, fill=rgba(magnet))
    pc.circle(10 + w / 2 - 3, 15, 4, fill=rgba(WHITE, 160))
    img = pc.im.rotate(rot, resample=Image.BICUBIC, expand=True)
    c.im.alpha_composite(img, (c.s(cx) - img.width // 2, c.s(cy) - img.height // 2))


def board():
    W, H = 1937, 1100
    c = Canvas(W, H, k=2)
    c.shadow([10, 10, W - 10, H - 10], 34, color=(0, 0, 0, 80), blur=10, off=(0, 8))
    c.rrect([10, 10, W - 10, H - 18], 34, fill=rgba((186, 132, 82)))
    c.rrect([22, 22, W - 22, H - 30], 26, outline=rgba((140, 92, 52)), width=3)
    bb = [44, 44, W - 44, H - 52]
    c.rrect(bb, 18, fill=rgba((40, 88, 72)))
    # chalk dust
    rnd = random.Random(7)
    dust = Image.new('RGBA', c.im.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(dust)
    for _ in range(26):
        x, y = rnd.randint(80, W - 80), rnd.randint(80, H - 90)
        rx, ry = rnd.randint(60, 220), rnd.randint(20, 70)
        dd.ellipse(c.box([x - rx, y - ry, x + rx, y + ry]), fill=(255, 255, 255, rnd.randint(5, 11)))
    dust = dust.filter(ImageFilter.GaussianBlur(c.s(18)))
    m = Image.new('L', c.im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle(c.box(bb), radius=c.s(18), fill=255)
    from PIL import ImageChops
    dust.putalpha(ImageChops.multiply(dust.split()[3], m))
    c.im.alpha_composite(dust)
    # chalk tray
    c.rrect([300, H - 50, W - 300, H - 26], 8, fill=rgba((160, 108, 62)))
    for i, col in enumerate([(255, 255, 255), (255, 220, 90), (255, 150, 160), (140, 200, 255)]):
        c.rrect([380 + i * 70, H - 62, 430 + i * 70, H - 48], 6, fill=rgba(col))

    # title in coloured chalk letters
    title = '队伍侦探社  寻回最美一条线'
    cols = [(255, 214, 92), (255, 160, 170), (140, 205, 255), (170, 235, 170), (255, 255, 255)]
    size = 80
    tw = c.text_w(title, F_KUAILE, size)
    x = W / 2 - tw / 2 + 40
    magnifier(c, x - 70, 170, 30, ring=rgba((255, 255, 255)), lens=rgba((40, 88, 72)), handle=rgba((255, 214, 92)), angle=45, ring_w=9)
    k = 0
    for ch in title:
        if ch != ' ':
            c.text((x, 172), ch, F_KUAILE, size, rgba(cols[k % len(cols)]), anchor='lm')
            k += 1
        x += c.text_w(ch, F_KUAILE, size)
    # 直 齐 不断
    for i, t in enumerate(['直', '齐', '不断']):
        paper(c, 1560 + i * 120 + (16 if i == 2 else 0), 290, t, NAVY, (255, 255, 255), size=46,
              rot=[4, -3, 3][i], magnet=[ST_BLUE, YELLOW, ST_GREEN][i])

    # ---- left: messy queue
    paper(c, 330, 405, '没秩序', (214, 66, 58), (255, 222, 222), rot=-5)
    paper(c, 630, 390, '不公平', (214, 66, 58), (255, 222, 222), rot=4)
    wave = [(150 + t * 8, 640 + 45 * math.sin(t * 0.115)) for t in range(0, 86)]
    c.line(wave, rgba((255, 140, 140)), 10)
    red = (232, 87, 79)
    for t, tl in [(8, -10), (22, 8), (31, -14), (52, 12), (60, -6), (77, 10)]:
        px = 150 + t * 8
        py = 640 + 45 * math.sin(t * 0.115)
        person(c, px, py - 4, 120, red, tilt=tl)
    paper(c, 480, 830, '不安全', (214, 66, 58), (255, 222, 222), rot=-3)

    # arrow (chalk)
    c.dashed([(880, 640), (1040, 640)], rgba((255, 255, 255, 220)), 8, 18, 14)
    c.poly([(1072, 640), (1036, 616), (1036, 664)], fill=rgba((255, 255, 255, 220)))

    # ---- right: neat queue
    paper(c, 1290, 455, '守秩序', (36, 128, 80), (220, 244, 228), rot=3)
    paper(c, 1590, 440, '有间隔', (36, 128, 80), (220, 244, 228), rot=-4)
    c.line([(1130, 670), (1800, 670)], rgba((150, 225, 170)), 10)
    green = (76, 175, 110)
    for i in range(6):
        person(c, 1180 + i * 115, 666, 120, green)
    paper(c, 1460, 830, '有先后', (36, 128, 80), (220, 244, 228), rot=2)
    # little chalk stars
    for sx, sy, r in [(120, 120, 18), (1820, 130, 16), (1830, 900, 14), (110, 900, 12)]:
        c.star(sx, sy, r, rgba((255, 255, 255, 150)))
    c.export().save(f'{OUT}/img_board.png')


if __name__ == '__main__':
    which = sys.argv[2:] or ['overview', 'survey', 'board']
    for w in which:
        globals()[w]()
