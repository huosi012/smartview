#!/usr/bin/env python3
"""学而思魔法校 · 叶子书房 灯箱软膜（成品 1260 × 2660 mm）。

生成一份 SVG，单位为毫米，所有文字都用字体轮廓直接画成路径（已转曲），
印刷端不需要装字体。画面四周按 BLEED 毫米出血绘制背景。

用法: python3 -I build.py <字体目录> <输出.svg>

字体（均可免费商用，SIL OFL）：
  QingKe.ttf          站酷庆科黄油体   大标题、卖点徽章
  NotoSansSC-500/700/900.ttf  思源黑体 Medium/Bold/Black  正文
"""
import math
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONT_DIR = Path(sys.argv[1])
OUT = Path(sys.argv[2])

W, H = 1260, 2660  # 成品尺寸 mm
BLEED = 30
SAFE = 60  # 文字离成品边缘的最小距离 mm（灯箱边框会压住一圈）

# ---------------------------------------------------------------- 配色
NAVY = "#17306B"
BLUE = "#1F6FE5"
BLUE_DARK = "#0B3A8E"
SKY = "#E8F2FF"
ORANGE = "#FF7A1F"
YELLOW = "#FFC62E"
YELLOW_DEEP = "#F5A300"
RED = "#F0412B"
PINK = "#FF5A8C"
PURPLE = "#8E63F0"
GREEN = "#2DB36A"
LEAF = "#3FAE5A"
LEAF_DARK = "#24874A"
GREY = "#4A5570"
WHITE = "#FFFFFF"


# ---------------------------------------------------------------- 文字转曲
def _num(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


class Font:
    def __init__(self, path, fallback=None):
        self.tt = TTFont(path)
        self.gs = self.tt.getGlyphSet()
        self.cmap = self.tt.getBestCmap()
        self.upm = self.tt["head"].unitsPerEm
        self.hmtx = self.tt["hmtx"]
        self.fallback = fallback

    def lookup(self, ch):
        f = self
        while ord(ch) not in f.cmap:
            f = f.fallback
            if f is None:
                raise KeyError(f"字体缺字: {ch!r}")
        g = f.cmap[ord(ch)]
        return f, g, f.hmtx[g][0] / f.upm

    def width(self, text, size, track=0.0):
        return sum(self.lookup(c)[2] for c in text) * size + track * size * (len(text) - 1)

    def path(self, text, size, x, y, track=0.0):
        parts = []
        for ch in text:
            f, g, adv = self.lookup(ch)
            pen = SVGPathPen(f.gs, ntos=_num)
            k = size / f.upm
            f.gs[g].draw(TransformPen(pen, (k, 0, 0, -k, x, y)))
            parts.append(pen.getCommands())
            x += adv * size + track * size
        return " ".join(p for p in parts if p)


N5 = Font(FONT_DIR / "NotoSansSC-500.ttf")
N7 = Font(FONT_DIR / "NotoSansSC-700.ttf")
N9 = Font(FONT_DIR / "NotoSansSC-900.ttf")
QK = Font(FONT_DIR / "QingKe.ttf", fallback=N9)


def baseline(cy, size):
    """让一行中文的视觉中心落在 cy 上时的基线位置。"""
    return cy + 0.36 * size


def runs(items, size, x, y, anchor="start", track=0.0, stroke=None, sw=0, shadow=None):
    """items: [(文字, 字体, 颜色), ...]，同一行内按顺序排；返回 (svg, 宽度)。"""
    widths = [f.width(t, size, track) for t, f, _ in items]
    total = sum(widths) + track * size * (len(items) - 1)
    if anchor == "middle":
        x -= total / 2
    elif anchor == "end":
        x -= total
    if x < SAFE or x + total > W - SAFE or y - size < SAFE or y > H - SAFE:
        print(f"警告: 文字超出安全区 {''.join(t for t, _, _ in items)!r} x={x:.0f}..{x + total:.0f} y={y:.0f}")
    paths = []
    for (t, f, color), w in zip(items, widths):
        paths.append((f.path(t, size, x, y, track), color))
        x += w + track * size
    out = []
    if shadow:
        dx, dy, color = shadow
        d = " ".join(p for p, _ in paths)
        out.append(
            f'<path transform="translate({dx} {dy})" d="{d}" fill="{color}" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linejoin="round"/>'
        )
    if stroke:
        d = " ".join(p for p, _ in paths)
        out.append(f'<path d="{d}" fill="{stroke}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>')
    out += [f'<path d="{d}" fill="{c}"/>' for d, c in paths]
    return "\n".join(out), total


def text(s, font, size, x, y, fill, anchor="start", **kw):
    return runs([(s, font, fill)], size, x, y, anchor, **kw)[0]


# ---------------------------------------------------------------- 图形
def rrect(x, y, w, h, r, fill="none", stroke=None, sw=0, extra=""):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<rect x="{_num(x)}" y="{_num(y)}" width="{_num(w)}" height="{_num(h)}" rx="{r}" fill="{fill}"{s} {extra}/>'


def circle(cx, cy, r, fill, extra=""):
    return f'<circle cx="{_num(cx)}" cy="{_num(cy)}" r="{_num(r)}" fill="{fill}" {extra}/>'


def polar(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def flower(cx, cy, r, color, center=YELLOW, petals=5, rot=-90):
    """圆瓣小花。"""
    out = []
    for i in range(petals):
        px, py = polar(cx, cy, r * 0.52, rot + i * 360 / petals)
        out.append(circle(px, py, r * 0.48, color))
    out.append(circle(cx, cy, r * 0.34, center))
    out.append(circle(cx, cy, r * 0.14, WHITE, 'opacity="0.55"'))
    return "\n".join(out)


def scallop(cx, cy, r, color, bumps=10):
    """花边圆形底（卖点徽章用）。"""
    out = [circle(cx, cy, r * 0.84, color)]
    for i in range(bumps):
        px, py = polar(cx, cy, r * 0.8, i * 360 / bumps)
        out.append(circle(px, py, r * 0.27, color))
    out.append(circle(cx, cy, r * 0.7, "none", f'stroke="{WHITE}" stroke-width="5" stroke-dasharray="2 12" stroke-linecap="round" opacity="0.8"'))
    return "\n".join(out)


def leaf(x, y, length, deg, color=LEAF, vein=LEAF_DARK):
    L = length
    return (
        f'<g transform="translate({_num(x)} {_num(y)}) rotate({deg})">'
        f'<path d="M0 0 Q{L*0.45} {-L*0.36} {L} 0 Q{L*0.55} {L*0.36} 0 0Z" fill="{color}"/>'
        f'<path d="M{L*0.06} 0 Q{L*0.5} {-L*0.05} {L*0.86} 0" fill="none" stroke="{vein}" stroke-width="{L*0.035}" stroke-linecap="round"/>'
        "</g>"
    )


def star(cx, cy, r1, r2, n, color, rot=-90, extra=""):
    pts = []
    for i in range(n * 2):
        pts.append(polar(cx, cy, r1 if i % 2 == 0 else r2, rot + i * 180 / n))
    return f'<polygon points="{" ".join(f"{_num(a)},{_num(b)}" for a, b in pts)}" fill="{color}" {extra}/>'


def sparkle(cx, cy, r, color):
    """四角闪光。"""
    k = r * 0.22
    return (
        f'<path d="M{cx} {cy-r} Q{cx+k} {cy-k} {cx+r} {cy} Q{cx+k} {cy+k} {cx} {cy+r} '
        f'Q{cx-k} {cy+k} {cx-r} {cy} Q{cx-k} {cy-k} {cx} {cy-r}Z" fill="{color}"/>'
    )


def check(cx, cy, r, color):
    return circle(cx, cy, r, color) + (
        f'<path d="M{cx-r*0.45} {cy+r*0.02} L{cx-r*0.12} {cy+r*0.34} L{cx+r*0.48} {cy-r*0.32}" '
        f'fill="none" stroke="{WHITE}" stroke-width="{r*0.26}" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def plane(x, y, s, deg):
    """纸飞机 + 虚线轨迹。"""
    return (
        f'<g transform="translate({x} {y}) rotate({deg}) scale({s})">'
        '<path d="M-150 60 C-110 20 -80 70 -40 30" fill="none" stroke="#9CC3FF" stroke-width="5" stroke-dasharray="12 12" stroke-linecap="round"/>'
        f'<path d="M0 0 L100 -40 L35 45 Z" fill="{WHITE}" stroke="{NAVY}" stroke-width="5" stroke-linejoin="round"/>'
        f'<path d="M0 0 L100 -40 L28 14 Z" fill="#D7E7FF" stroke="{NAVY}" stroke-width="5" stroke-linejoin="round"/>'
        f'<path d="M28 14 L35 45 L46 22" fill="#BFD8FF" stroke="{NAVY}" stroke-width="5" stroke-linejoin="round"/>'
        "</g>"
    )


def ribbon(cx, cy, label, size=52):
    """标题飘带：主带 + 两侧燕尾。"""
    tw = N9.width(label, size, 0.08)
    w, h = tw + 150, size + 52
    x0, x1, y0 = cx - w / 2, cx + w / 2, cy - h / 2
    tail, drop = 82, 22
    out = []
    for side in (-1, 1):
        edge = x0 if side < 0 else x1
        outer = edge + side * tail
        notch = edge + side * (tail - 30)
        inner = edge - side * 40
        out.append(
            f'<polygon points="{inner},{y0+drop} {outer},{y0+drop} {notch},{cy+drop} '
            f'{outer},{y0+h+drop} {inner},{y0+h+drop}" fill="{YELLOW_DEEP}"/>'
        )
        out.append(f'<polygon points="{edge},{y0+h} {edge},{y0+h+drop} {edge - side*28},{y0+h}" fill="#B86E00"/>')
    out.append(rrect(x0, y0, w, h, 18, YELLOW))
    out.append(rrect(x0 + 14, y0 + 12, w - 28, h - 24, 12, "none", WHITE, 4, 'stroke-dasharray="3 12" stroke-linecap="round" opacity="0.9"'))
    out.append(text(label, N9, size, cx, baseline(cy, size), WHITE, "middle", track=0.08, stroke="#C76200", sw=9))
    return "\n".join(out)


# ---------------------------------------------------------------- 画面
def background():
    b = BLEED
    out = [f'<rect x="{-b}" y="{-b}" width="{W+2*b}" height="{H+2*b}" fill="{WHITE}"/>']
    # 浅色点阵与淡色圆，避免大面积纯白显得空
    for i, (x, y, r, c) in enumerate(
        [(1150, 760, 90, SKY), (90, 1130, 70, "#FFF1D6"), (1190, 1500, 60, "#FFE3EC"), (60, 1960, 80, SKY), (1210, 2150, 60, "#FFF1D6")]
    ):
        out.append(circle(x, y, r, c))
    for gx, gy in ((40, 640), (1130, 1960)):
        for i in range(4):
            for j in range(4):
                out.append(circle(gx + i * 26, gy + j * 26, 4.5, "#C9DCF7"))
    return "\n".join(out)


def corner_top_left():
    b = BLEED
    out = [
        # 橙色大色块
        f'<path d="M{-b} {-b} L420 {-b} C400 60 330 90 250 110 C180 128 150 190 90 240 C40 280 0 260 {-b} 250Z" fill="{ORANGE}"/>',
        f'<path d="M{-b} {-b} L260 {-b} C240 30 190 60 120 80 C60 98 20 140 {-b} 150Z" fill="#FF9A3D"/>',
        leaf(150, 150, 120, 35), leaf(300, 70, 110, -20), leaf(40, 190, 95, 70, "#56C26F", LEAF),
        flower(95, 70, 70, RED, YELLOW, 5),
        flower(250, 130, 52, YELLOW, ORANGE, 5, -60),
        flower(380, 40, 44, PINK, YELLOW, 5, -30),
        flower(42, 262, 30, "#3D8BFF", YELLOW, 5),
        flower(190, 40, 30, WHITE, YELLOW, 5),
    ]
    return "\n".join(out)


def corner_top_right():
    b = BLEED
    out = [
        f'<path d="M{W+b} {-b} L800 {-b} C820 40 900 70 960 70 C1040 70 1080 130 1130 190 C1170 240 1220 250 {W+b} 230Z" fill="{BLUE}"/>',
        f'<path d="M{W+b} {-b} L990 {-b} C1000 30 1060 50 1110 70 C1170 95 1200 130 {W+b} 140Z" fill="#5A9BFF"/>',
        leaf(1000, 40, 110, 160), leaf(1150, 170, 88, 140, "#56C26F", LEAF),
        flower(1170, 70, 66, YELLOW, ORANGE, 5, -54),
        flower(1040, 105, 46, ORANGE, YELLOW, 5),
        flower(905, 30, 40, PINK, YELLOW, 5, -20),
        flower(1225, 205, 34, WHITE, YELLOW, 5),
        flower(1105, 210, 26, RED, YELLOW, 5),
    ]
    return "\n".join(out)


def brand(cy):
    """叶子书房（绿色标签） + 学而思魔法校。"""
    tag_size, name_size = 44, 64
    tag_w = N9.width("叶子书房", tag_size) + 120
    name_w = N9.width("学而思魔法校", name_size)
    total = tag_w + 28 + name_w
    x = W / 2 - total / 2
    out = [
        rrect(x, cy - 40, tag_w, 80, 40, LEAF),
        leaf(x + 28, cy + 6, 46, -40, WHITE, LEAF),
        text("叶子书房", N9, tag_size, x + 82, baseline(cy, tag_size), WHITE),
        text("学而思魔法校", N9, name_size, x + tag_w + 28, baseline(cy, name_size), NAVY),
    ]
    return "\n".join(out)


def headline(top):
    s1, s2 = 196, 168
    b1 = top + 0.82 * s1
    b2 = b1 + 0.1 * s1 + 44 + 0.82 * s2
    line1, w1 = runs([("每天", QK, BLUE), ("半小时", QK, ORANGE)], s1, 90, b1, track=0.02,
                     stroke=WHITE, sw=22, shadow=(9, 11, BLUE_DARK))
    line2, w2 = runs([("不把问题攒到周末", QK, BLUE)], s2, W / 2, b2, "middle", track=0.02,
                     stroke=WHITE, sw=20, shadow=(8, 10, BLUE_DARK))
    deco = [
        sparkle(1222, b2 - 20, 20, PINK),
        sparkle(34, b2 - 40, 16, "#7DB4FF"),
    ]
    # 价格贴纸：放在第一行右侧
    sx, sy = 1080, top + 100
    sticker = [
        star(sx + 6, sy + 8, 128, 110, 18, BLUE_DARK, extra='opacity="0.25"'),
        star(sx, sy, 128, 110, 18, RED),
        circle(sx, sy, 96, "none", f'stroke="{WHITE}" stroke-width="5" stroke-dasharray="2 11" stroke-linecap="round"'),
        text("均价", N9, 30, sx, sy - 44, WHITE, "middle"),
        text("100+", N9, 70, sx, sy + 26, YELLOW, "middle"),
        text("元/小时", N9, 28, sx, sy + 70, WHITE, "middle"),
    ]
    return "\n".join([line1, line2] + deco + sticker), b2 + 0.12 * s2


def tagline(cy):
    size = 56
    label = [("双师一对一", N9, YELLOW), ("的服务 · ", N9, WHITE), ("小班课", N9, YELLOW), ("的价格", N9, WHITE)]
    tw = sum(f.width(t, size) for t, f, _ in label)
    w, h = tw + 130, 104
    out = [
        rrect(W / 2 - w / 2 + 8, cy - h / 2 + 10, w, h, h / 2, BLUE_DARK),
        rrect(W / 2 - w / 2, cy - h / 2, w, h, h / 2, BLUE),
        runs(label, size, W / 2, baseline(cy, size), "middle")[0],
    ]
    return "\n".join(out)


def schedule_line(cy):
    size = 40
    items = [("周二至周五 ", N7, NAVY), ("每天约半小时", N9, RED), (" ＋ 周末2小时", N7, NAVY)]
    return runs(items, size, W / 2, baseline(cy, size), "middle")[0] + plane(1105, cy - 12, 0.75, -10)


BADGES = [("一人", "一案", PINK), ("固定", "老师", PURPLE), ("日查", "周测", ORANGE), ("及时", "反馈", GREEN)]


def badges(cy):
    r, gap = 112, 278
    out = []
    for i, (a, b_, c) in enumerate(BADGES):
        cx = W / 2 + (i - 1.5) * gap
        out.append(scallop(cx, cy, r, c))
        out.append(text(a, QK, 70, cx, baseline(cy - 38, 70), WHITE, "middle", track=0.05))
        out.append(text(b_, QK, 70, cx, baseline(cy + 40, 70), WHITE, "middle", track=0.05))
    return "\n".join(out)


POINTS = [
    ([("哪里不会，", NAVY), ("就从哪里补", RED)], "先找准薄弱点，再制定个人学习计划", PINK),
    ([("固定老师跟进，", NAVY), ("卡点单独讲", RED)], "学习时老师全程在场，走神有人提醒，不会有人补讲", PURPLE),
    ([("学没学会持续查，", NAVY), ("学得咋样看得见", RED)], "当天检查 · 周末复测 · 每月回查", ORANGE),
    ([("免费体验一周，", RED), ("合适再报名", NAVY)], "让孩子真实学一学，让家长亲眼看一看", GREEN),
]


def points_box(top):
    x, w = 70, W - 140
    pitch, first = 122, top + 90
    h = 90 + pitch * len(POINTS) + 10
    out = [
        rrect(x + 8, top + 10, w, h, 50, "#FFE6A8"),
        rrect(x, top, w, h, 50, WHITE, YELLOW_DEEP, 8),
    ]
    for i, (title, desc, color) in enumerate(POINTS):
        y = first + i * pitch
        out.append(circle(x + 92, y + 34, 44, color))
        out.append(text(str(i + 1), N9, 56, x + 92, baseline(y + 34, 56) - 1, WHITE, "middle"))
        out.append(runs([(t, N9, c) for t, c in title], 54, x + 160, y + 40)[0])
        out.append(text(desc, N5, 38, x + 162, y + 98, GREY))
        if i < len(POINTS) - 1:
            out.append(f'<line x1="{x+160}" y1="{y+pitch-8}" x2="{x+w-50}" y2="{y+pitch-8}" stroke="#F1E3C0" stroke-width="3" stroke-dasharray="10 10"/>')
    out.append(ribbon(W / 2, top, "家长最关心的四件事"))
    return "\n".join(out), top + h


STEPS = ["核对计划", "微课精讲", "纸笔练习", "老师巡视", "单独补讲", "当天抽讲", "周末复测", "每月回查", "家长反馈"]
STEP_COLORS = [PINK, PURPLE, ORANGE, BLUE, RED, GREEN, PINK, PURPLE, ORANGE]


def steps_box(top):
    x, w = 70, W - 140
    row0, pitch = top + 98, 78
    h = 96 + pitch * 3 + 8
    out = [
        rrect(x + 8, top + 10, w, h, 50, "#FFE6A8"),
        rrect(x, top, w, h, 50, WHITE, YELLOW_DEEP, 8),
    ]
    col_w = (w - 100) / 3
    for i, s in enumerate(STEPS):
        r_, c_ = divmod(i, 3)
        cx = x + 64 + c_ * col_w
        cy = row0 + r_ * pitch
        out.append(circle(cx + 26, cy, 28, STEP_COLORS[i]))
        out.append(text(str(i + 1), N9, 38, cx + 26, baseline(cy, 38) - 1, WHITE, "middle"))
        out.append(text(s, N7, 46, cx + 74, baseline(cy, 46), NAVY))
        if c_ < 2:
            ax = cx + 74 + N7.width(s, 46) + 22
            out.append(f'<path d="M{ax} {cy-12} L{ax+16} {cy} L{ax} {cy+12}" fill="none" stroke="#F5B941" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>')
    out.append(ribbon(W / 2, top, "学习闭环 · 九步落实"))
    return "\n".join(out), top + h


def footer(top):
    b = BLEED
    out = [
        f'<path d="M{-b} {top+40} C220 {top-30} 420 {top+70} 640 {top+20} C860 {top-30} 1040 {top+10} {W+b} {top-20} L{W+b} {H+b} L{-b} {H+b}Z" fill="#FFE08A"/>',
        f'<path d="M{-b} {top+80} C260 {top+20} 460 {top+110} 680 {top+60} C900 {top+10} 1060 {top+50} {W+b} {top+30} L{W+b} {H+b} L{-b} {H+b}Z" fill="{YELLOW}"/>',
    ]
    # 二维码占位
    qx, qy, qs = 80, top + 108, 220
    out += [
        rrect(qx, qy, qs, qs, 24, WHITE),
        rrect(qx + 14, qy + 14, qs - 28, qs - 28, 14, "none", "#9AA5BE", 4, 'stroke-dasharray="14 10"'),
        text("微信二维码", N7, 34, qx + qs / 2, qy + qs / 2 - 4, "#7A859E", "middle"),
        text("（待替换）", N5, 26, qx + qs / 2, qy + qs / 2 + 38, "#9AA5BE", "middle"),
    ]
    tx = qx + qs + 46
    out.append(runs([("联系欧老师 · ", QK, NAVY), ("预约免费体验", QK, RED)], 64, tx, top + 172, track=0.03)[0])
    # 电话
    py = top + 280
    out.append(circle(tx + 38, py - 31, 38, RED))
    out.append(
        f'<path transform="translate({tx+38} {py-31}) scale(1.4)" d="M-9 -13 C-12 -13 -14 -10 -13 -6 C-10 6 -3 12 7 14 '
        'C10 15 13 13 13 10 L13 6 C13 4 11 3 9 3 L5 4 C3 2 -1 -2 -3 -5 L-2 -9 C-1 -11 -3 -13 -5 -13Z" fill="#FFFFFF"/>'
    )
    out.append(text("191 6627 8890", N9, 90, tx + 92, py, NAVY, track=0.01))
    out.append(text("深圳南山 · 缤纷年华三楼叶子书房（麒麟中学斜对面）", N5, 33, tx, top + 336, NAVY))
    return "\n".join(out)


def build():
    parts = [background(), corner_top_left(), corner_top_right(), brand(185)]
    head, y = headline(272)
    parts.append(head)
    parts.append(tagline(y + 78))
    parts.append(schedule_line(y + 170))
    parts.append(badges(y + 330))
    box1, y = points_box(y + 520)
    parts.append(box1)
    box2, y = steps_box(y + 86)
    parts.append(box2)
    parts.append(footer(H - 400))
    body = "\n".join(parts)
    b = BLEED
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W+2*b}mm" height="{H+2*b}mm" '
        f'viewBox="{-b} {-b} {W+2*b} {H+2*b}">\n'
        f"<title>学而思魔法校·叶子书房 灯箱软膜 {W}×{H}mm（含{b}mm出血）</title>\n{body}\n</svg>\n"
    )
    OUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1e6:.1f} MB), content bottom ~ {y:.0f}mm")


build()
