#!/usr/bin/env python3
"""学而思魔法校 · 叶子书房 灯箱软膜（成品 1260 × 2660 mm），放在商场门口。

版式按"路过 3 秒能看懂"来排：
  上部（离地约 1.9–2.6 m，远处可见）  品牌 + 闹钟主视觉 + 价格/服务徽章
  中部（离地约 1.5–1.9 m，平视）      大标题"每天半小时 / 不把问题攒到周末"
  胸口高度（离地约 1.0–1.4 m）        免费体验券 + 电话 + 二维码，方便扫码
  下部（停下来的人看）                四条卖点、地址
整幅铺高饱和蓝底，背光后最亮眼。

生成一份 SVG，单位为毫米，所有文字都用字体轮廓直接画成路径（已转曲），
印刷端不需要装字体。画面四周按 BLEED 毫米出血绘制背景。

用法: python3 -I build.py <字体目录> <输出.svg>

字体（均可免费商用，SIL OFL）：
  KuaiLe.ttf                  站酷快乐体       大标题、体验券
  NotoSansSC-500/700/900.ttf  思源黑体 Medium/Bold/Black  其余文字
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
X0, X1 = 80, W - 80  # 版心左右边

# ---------------------------------------------------------------- 配色
BG = "#1F55F0"         # 主底色：高饱和蓝
RAY = "#2A62FF"        # 放射线
DEEP = "#0E2B8F"       # 描边、投影、页脚
INK = "#132463"
YELLOW = "#FFD43B"
ORANGE = "#FF7A1F"
RED = "#F23B2F"
GREEN = "#2DB36A"
PINK = "#FF5E8E"
PURPLE = "#8B5CF6"
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
KL = Font(FONT_DIR / "KuaiLe.ttf", fallback=N9)


def baseline(cy, size):
    """让一行中文的视觉中心落在 cy 上时的基线位置。"""
    return cy + 0.36 * size


def runs(items, size, x, y, anchor="start", track=0.0, stroke=None, sw=0, shadow=None, check=True):
    """items: [(文字, 字体, 颜色), ...]，同一行内按顺序排；返回 (svg, 起点x, 宽度)。
    stroke: 外描边颜色；shadow: (dx, dy, 颜色) 立体投影，与描边同宽。"""
    widths = [f.width(t, size, track) for t, f, _ in items]
    total = sum(widths) + track * size * (len(items) - 1)
    if anchor == "middle":
        x -= total / 2
    elif anchor == "end":
        x -= total
    if check and (x < SAFE or x + total > W - SAFE or y - size < SAFE or y > H - SAFE):
        print(f"警告: 文字超出安全区 {''.join(t for t, _, _ in items)!r} x={x:.0f}..{x + total:.0f} y={y:.0f}")
    start = x
    paths = []
    for (t, f, color), w in zip(items, widths):
        paths.append((f.path(t, size, x, y, track), color))
        x += w + track * size
    d_all = " ".join(p for p, _ in paths)
    out = []
    if shadow:
        dx, dy, c = shadow
        out.append(f'<path transform="translate({dx} {dy})" d="{d_all}" fill="{c}" stroke="{c}" stroke-width="{sw}" stroke-linejoin="round"/>')
    if stroke:
        out.append(f'<path d="{d_all}" fill="{stroke}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>')
    out += [f'<path d="{d}" fill="{c}"/>' for d, c in paths]
    return "\n".join(out), start, total


def text(s, font, size, x, y, fill, anchor="start", **kw):
    return runs([(s, font, fill)], size, x, y, anchor, **kw)[0]


# ---------------------------------------------------------------- 图形
def rrect(x, y, w, h, r, fill="none", stroke=None, sw=0, extra=""):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<rect x="{_num(x)}" y="{_num(y)}" width="{_num(w)}" height="{_num(h)}" rx="{r}" fill="{fill}"{s} {extra}/>'


def circle(cx, cy, r, fill, extra=""):
    return f'<circle cx="{_num(cx)}" cy="{_num(cy)}" r="{_num(r)}" fill="{fill}" {extra}/>'


def line(d, color=INK, sw=6, extra=""):
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" {extra}/>'


def polar(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def starburst(cx, cy, r1, r2, n, color, rot=-90, extra=""):
    pts = [polar(cx, cy, r1 if i % 2 == 0 else r2, rot + i * 180 / n) for i in range(2 * n)]
    return f'<polygon points="{" ".join(f"{_num(a)},{_num(b)}" for a, b in pts)}" fill="{color}" {extra}/>'


def sparkle(cx, cy, r, color):
    k = r * 0.22
    return (
        f'<path d="M{cx} {cy-r} Q{cx+k} {cy-k} {cx+r} {cy} Q{cx+k} {cy+k} {cx} {cy+r} '
        f'Q{cx-k} {cy+k} {cx-r} {cy} Q{cx-k} {cy-k} {cx} {cy-r}Z" fill="{color}"/>'
    )


def check_mark(x, y, s, color, sw=None):
    """对勾，(x, y) 为左端点。"""
    sw = sw or s * 0.2
    return line(f"M{x} {y} L{x+s*0.36} {y+s*0.36} L{x+s} {y-s*0.38}", color, sw)


def sunburst(cx, cy, n=28, r=2600):
    """以 (cx, cy) 为中心的放射线背景。"""
    out = []
    step = 360 / n
    for i in range(n):
        a0 = -90 + i * step
        p1, p2 = polar(cx, cy, r, a0), polar(cx, cy, r, a0 + step / 2)
        out.append(f'<polygon points="{cx},{cy} {_num(p1[0])},{_num(p1[1])} {_num(p2[0])},{_num(p2[1])}" fill="{RAY}"/>')
    return "\n".join(out)


def alarm_clock(cx, cy, r):
    """闹钟主视觉：表盘上 0–30 分钟的扇区涂成橙色。"""
    o = r * 0.07  # 描边宽
    out = [
        # 投影
        circle(cx + r * 0.05, cy + r * 0.07, r * 1.02, DEEP),
        # 铃铛、提手、腿
        f'<path d="M{cx-r*0.98} {cy-r*0.5} A{r*0.45} {r*0.45} 0 0 1 {cx-r*0.42} {cy-r*1.06}Z" fill="{RED}" stroke="{DEEP}" stroke-width="{o}" stroke-linejoin="round"/>',
        f'<path d="M{cx+r*0.98} {cy-r*0.5} A{r*0.45} {r*0.45} 0 0 0 {cx+r*0.42} {cy-r*1.06}Z" fill="{RED}" stroke="{DEEP}" stroke-width="{o}" stroke-linejoin="round"/>',
        line(f"M{cx-r*0.6} {cy+r*0.78} L{cx-r*0.85} {cy+r*1.12}", DEEP, o * 1.5),
        line(f"M{cx+r*0.6} {cy+r*0.78} L{cx+r*0.85} {cy+r*1.12}", DEEP, o * 1.5),
        rrect(cx - r * 0.12, cy - r * 1.18, r * 0.24, r * 0.2, r * 0.06, YELLOW, DEEP, o * 0.8),
        circle(cx, cy, r, WHITE, f'stroke="{DEEP}" stroke-width="{o*1.3}"'),
        f'<path d="M{cx} {cy} L{cx} {cy-r*0.84} A{r*0.84} {r*0.84} 0 0 1 {cx} {cy+r*0.84}Z" fill="{ORANGE}"/>',
    ]
    for i in range(12):
        x1, y1 = polar(cx, cy, r * 0.86, i * 30)
        x2, y2 = polar(cx, cy, r * 0.72 if i % 3 == 0 else r * 0.78, i * 30)
        out.append(line(f"M{_num(x1)} {_num(y1)} L{_num(x2)} {_num(y2)}", INK, o * (0.75 if i % 3 == 0 else 0.5)))
    out += [
        line(f"M{cx} {cy} L{cx} {cy+r*0.64}", INK, o * 1.1),
        line(f"M{cx} {cy} L{cx-r*0.32} {cy-r*0.38}", INK, o * 1.1),
        circle(cx, cy, r * 0.08, INK),
        # 响铃的震动线
        line(f"M{cx-r*1.2} {cy-r*0.95} Q{cx-r*1.32} {cy-r*0.72} {cx-r*1.22} {cy-r*0.5}", YELLOW, o),
        line(f"M{cx-r*1.36} {cy-r*1.05} Q{cx-r*1.5} {cy-r*0.72} {cx-r*1.38} {cy-r*0.4}", YELLOW, o),
        line(f"M{cx+r*1.2} {cy-r*0.95} Q{cx+r*1.32} {cy-r*0.72} {cx+r*1.22} {cy-r*0.5}", YELLOW, o),
        line(f"M{cx+r*1.36} {cy-r*1.05} Q{cx+r*1.5} {cy-r*0.72} {cx+r*1.38} {cy-r*0.4}", YELLOW, o),
    ]
    return "\n".join(out)


def phone_icon(cx, cy, r, bg, fg):
    return circle(cx, cy, r, bg) + (
        f'<path transform="translate({cx} {cy}) scale({r/26})" d="M-9 -13 C-12 -13 -14 -10 -13 -6 C-10 6 -3 12 7 14 '
        f'C10 15 13 13 13 10 L13 6 C13 4 11 3 9 3 L5 4 C3 2 -1 -2 -3 -5 L-2 -9 C-1 -11 -3 -13 -5 -13Z" fill="{fg}"/>'
    )


# 卖点图标：圆底白图形
def icon_target(cx, cy, r, c):
    return "\n".join([
        circle(cx, cy, r, c),
        circle(cx, cy, r * 0.62, "none", f'stroke="{WHITE}" stroke-width="{r*0.12}"'),
        circle(cx, cy, r * 0.32, "none", f'stroke="{WHITE}" stroke-width="{r*0.12}"'),
        circle(cx, cy, r * 0.09, WHITE),
        line(f"M{cx} {cy} L{cx+r*0.62} {cy-r*0.62}", WHITE, r * 0.1),
        f'<path d="M{cx+r*0.5} {cy-r*0.78} L{cx+r*0.78} {cy-r*0.78} L{cx+r*0.78} {cy-r*0.5}" fill="none" stroke="{WHITE}" stroke-width="{r*0.1}" stroke-linecap="round" stroke-linejoin="round"/>',
    ])


def icon_teacher(cx, cy, r, c):
    return "\n".join([
        circle(cx, cy, r, c),
        circle(cx, cy - r * 0.22, r * 0.26, WHITE),
        f'<path d="M{cx-r*0.52} {cy+r*0.58} Q{cx-r*0.5} {cy+r*0.1} {cx} {cy+r*0.1} Q{cx+r*0.5} {cy+r*0.1} {cx+r*0.52} {cy+r*0.58}Z" fill="{WHITE}"/>',
    ])


def icon_check(cx, cy, r, c):
    return "\n".join([
        circle(cx, cy, r, c),
        rrect(cx - r * 0.42, cy - r * 0.52, r * 0.84, r * 1.06, r * 0.1, "none", WHITE, r * 0.1),
        rrect(cx - r * 0.2, cy - r * 0.64, r * 0.4, r * 0.22, r * 0.06, WHITE),
        check_mark(cx - r * 0.24, cy + r * 0.04, r * 0.5, WHITE, r * 0.11),
    ])


def icon_database(cx, cy, r, c):
    """错题库：三层圆柱。"""
    rx, ry, sw = r * 0.46, r * 0.16, r * 0.1
    out = [circle(cx, cy, r, c)]
    top, step = cy - r * 0.38, r * 0.3
    out.append(f'<path d="M{cx-rx} {top} V{top+3*step} A{rx} {ry} 0 0 0 {cx+rx} {top+3*step} V{top}" fill="none" stroke="{WHITE}" stroke-width="{sw}" stroke-linejoin="round"/>')
    out.append(f'<ellipse cx="{cx}" cy="{top}" rx="{rx}" ry="{ry}" fill="none" stroke="{WHITE}" stroke-width="{sw}"/>')
    for k in (1, 2):
        out.append(f'<path d="M{cx-rx} {top+k*step} A{rx} {ry} 0 0 0 {cx+rx} {top+k*step}" fill="none" stroke="{WHITE}" stroke-width="{sw}"/>')
    return "\n".join(out)


# ---------------------------------------------------------------- 画面
def background(clock_c):
    b = BLEED
    return "\n".join([
        f'<rect x="{-b}" y="{-b}" width="{W+2*b}" height="{H+2*b}" fill="{BG}"/>',
        f'<clipPath id="top-area"><rect x="{-b}" y="{-b}" width="{W+2*b}" height="{1280+b}"/></clipPath>',
        f'<g clip-path="url(#top-area)">{sunburst(*clock_c)}</g>',
    ])


def confetti():
    items = [
        sparkle(70, 300, 26, YELLOW), sparkle(1200, 760, 22, WHITE), sparkle(60, 760, 18, PINK),
        sparkle(1205, 280, 18, YELLOW), circle(150, 720, 12, YELLOW), circle(1120, 250, 10, PINK),
        circle(1185, 1215, 10, YELLOW), circle(75, 1215, 12, PINK),
        f'<path d="M120 1180 q20 -26 40 0 t40 0" fill="none" stroke="{YELLOW}" stroke-width="8" stroke-linecap="round"/>',
        f'<path d="M1070 1190 q20 -26 40 0 t40 0" fill="none" stroke="{WHITE}" stroke-width="8" stroke-linecap="round"/>',
    ]
    return "\n".join(items)


def brand(cy):
    tag_size, name_size = 46, 78
    tag_w = N9.width("叶子书房", tag_size) + 118
    name_w = N9.width("学而思魔法校", name_size)
    total = tag_w + 30 + name_w
    x = W / 2 - total / 2
    return "\n".join([
        rrect(x, cy - 42, tag_w, 84, 42, GREEN, WHITE, 5),
        f'<g transform="translate({x+28} {cy+6}) rotate(-40)"><path d="M0 0 Q21 -17 46 0 Q25 17 0 0Z" fill="{WHITE}"/></g>',
        text("叶子书房", N9, tag_size, x + 84, baseline(cy, tag_size), WHITE),
        text("学而思魔法校", N9, name_size, x + tag_w + 30, baseline(cy, name_size), WHITE),
    ])


def side_badges(cy):
    """闹钟两侧：左价格爆炸贴，右服务圆章。"""
    lx, rx = 205, W - 205
    left = [
        starburst(lx + 8, cy + 12, 168, 142, 16, DEEP),
        starburst(lx, cy, 168, 142, 16, RED),
        circle(lx, cy, 124, "none", f'stroke="{WHITE}" stroke-width="5" stroke-dasharray="2 12" stroke-linecap="round"'),
        text("均价", N7, 36, lx, baseline(cy - 72, 36), WHITE, "middle"),
        text("100+", N9, 98, lx, baseline(cy + 2, 98), YELLOW, "middle"),
        text("元/小时", N7, 34, lx, baseline(cy + 74, 34), WHITE, "middle"),
    ]
    right = [
        circle(rx + 8, cy + 12, 150, DEEP),
        circle(rx, cy, 150, YELLOW),
        circle(rx, cy, 128, "none", f'stroke="{INK}" stroke-width="5" stroke-dasharray="2 12" stroke-linecap="round"'),
        text("双师", N9, 52, rx, baseline(cy - 66, 52), INK, "middle"),
        text("一对一", N9, 66, rx, baseline(cy + 2, 66), RED, "middle"),
        text("小班课价格", N7, 34, rx, baseline(cy + 70, 34), INK, "middle"),
    ]
    return "\n".join(left + right)


def headline(top):
    s1, s2 = 232, 146
    b1 = top + 0.79 * s1
    b2 = b1 + 0.07 * s1 + 38 + 0.79 * s2
    l1 = runs([("每天半小时", KL, YELLOW)], s1, W / 2, b1, "middle", stroke=DEEP, sw=24, shadow=(0, 16, DEEP))[0]
    l2 = runs([("不把问题攒到周末", KL, WHITE)], s2, W / 2, b2, "middle", stroke=DEEP, sw=18, shadow=(0, 11, DEEP))[0]
    return l1 + "\n" + l2, b2 + 0.07 * s2


def subline(cy):
    size = 44
    items = [("放学来学半小时 · 学完写作业", N7, WHITE), ("不另收费", N9, YELLOW)]
    return runs(items, size, W / 2, baseline(cy, size), "middle")[0]


def ticket(top):
    """免费体验券：左黄色主券，右白色二维码存根。"""
    x, w, h = X0, X1 - X0, 380
    y = top
    stub = 330
    sx = x + w - stub
    r = 30
    main = (
        f'M{x+30} {y} H{sx-r} A{r} {r} 0 0 0 {sx} {y+r} V{y+h-r} A{r} {r} 0 0 0 {sx-r} {y+h} '
        f'H{x+30} Q{x} {y+h} {x} {y+h-30} V{y+30} Q{x} {y} {x+30} {y}Z'
    )
    stubp = (
        f'M{sx} {y+r} A{r} {r} 0 0 0 {sx+r} {y} H{x+w-30} Q{x+w} {y} {x+w} {y+30} V{y+h-30} '
        f'Q{x+w} {y+h} {x+w-30} {y+h} H{sx+r} A{r} {r} 0 0 0 {sx} {y+h-r}Z'
    )
    out = [
        f'<g transform="translate(10 16)" fill="{DEEP}"><path d="{main}"/><path d="{stubp}"/></g>',
        f'<path d="{main}" fill="{YELLOW}"/>',
        f'<path d="{stubp}" fill="{WHITE}"/>',
        line(f"M{sx} {y+r+18} V{y+h-r-18}", DEEP, 6, 'stroke-dasharray="4 16"'),
        rrect(x + 22, y + 22, sx - x - 44, h - 44, 18, "none", "#E0A800", 4, 'stroke-dasharray="14 10"'),
    ]
    tx = x + 60
    out.append(runs([("免费体验一周", KL, RED)], 116, tx, y + 140, stroke=WHITE, sw=14)[0])
    out.append(runs([("带上最近的试卷，", N9, INK), ("现场找卡点", N9, RED)], 42, tx + 4, y + 214)[0])
    py = y + 316
    out.append(phone_icon(tx + 36, py - 28, 36, RED, WHITE))
    out.append(text("191 6627 8890", N9, 80, tx + 88, py, INK, track=0.01))
    assert tx + 88 + N9.width("191 6627 8890", 80, 0.01) < sx - 24, "电话号码压到打孔线"
    # 二维码存根
    qs = 230
    qx, qy = sx + (stub - qs) / 2, y + 30
    out += [
        rrect(qx, qy, qs, qs, 16, "#F3F5FA"),
        rrect(qx + 14, qy + 14, qs - 28, qs - 28, 10, "none", "#9AA5BE", 4, 'stroke-dasharray="12 9"'),
        text("微信二维码", N7, 32, qx + qs / 2, qy + qs / 2 - 2, "#7A859E", "middle"),
        text("（待替换）", N5, 26, qx + qs / 2, qy + qs / 2 + 38, "#9AA5BE", "middle"),
        text("扫码预约体验", N9, 38, sx + stub / 2, y + h - 44, INK, "middle"),
    ]
    return "\n".join(out), y + h


POINTS = [
    (icon_target, PINK, [("先找卡点，", INK), ("再对症补", RED)],
     [("逐个知识点排查，从基础缺口补起，一人一份计划", GREY)]),
    (icon_teacher, PURPLE, [("固定老师，", INK), ("全程盯学", RED)],
     [("同一位老师跟到底：走神有人提醒，卡壳当场单独讲", GREY)]),
    (icon_check, ORANGE, [("错题不过关，", INK), ("不算学完", RED)],
     [("原题正确率", GREY), ("90%", RED), ("以上、同类题", GREY), ("80%", RED), ("以上，才算真学会", GREY)]),
    (icon_database, GREEN, [("专属错题库，", INK), ("数据实时可查", RED)],
     [("每道错题都入库：当天抽讲 · 周末复测 · 每月回查", GREY)]),
]


def points(top):
    x, w = X0, X1 - X0
    pitch, pad = 128, 24
    head_cy = top + 44
    out = [runs([("学完不算，", KL, WHITE), ("学会才算！", KL, YELLOW)], 76, W / 2, baseline(head_cy, 76), "middle",
                stroke=DEEP, sw=14, shadow=(0, 8, DEEP))[0]]
    top += 108
    h = pad * 2 + pitch * len(POINTS)
    out += [
        rrect(x + 10, top + 16, w, h, 40, DEEP),
        rrect(x, top, w, h, 40, WHITE),
    ]
    for i, (icon, c, title, desc) in enumerate(POINTS):
        y = top + pad + i * pitch
        out.append(icon(x + 92, y + pitch / 2, 54, c))
        out.append(runs([(t, N9, col) for t, col in title], 58, x + 176, y + 66)[0])
        out.append(runs([(t, N9 if col == RED else N5, col) for t, col in desc], 33, x + 178, y + 112)[0])
        if i < len(POINTS) - 1:
            out.append(line(f"M{x+176} {y+pitch} H{x+w-50}", "#E3E8F3", 3, 'stroke-dasharray="10 10"'))
    return "\n".join(out), top + h


def footer(top):
    b = BLEED
    return "\n".join([
        f'<path d="M{-b} {top+30} Q{W/2} {top-40} {W+b} {top+30} V{H+b} H{-b}Z" fill="{DEEP}"/>',
        text("深圳南山 · 缤纷年华三楼叶子书房（麒麟中学斜对面）", N7, 42, W / 2, top + 104, WHITE, "middle"),
        runs([("联系欧老师  ", N7, "#B9C8FF"), ("191 6627 8890", N9, YELLOW)], 38, W / 2, top + 164, "middle")[0],
    ])


def build():
    clock_c = (W / 2, 505)
    parts = [background(clock_c), confetti(), brand(150), alarm_clock(*clock_c, 200), side_badges(clock_c[1] + 10)]
    head, y = headline(790)
    parts.append(head)
    parts.append(subline(y + 52))
    tk, y = ticket(y + 108)
    parts.append(tk)
    pt, y = points(y + 34)
    parts.append(pt)
    parts.append(footer(y + 46))
    print(f"卖点框底部 y={y:.0f}mm，页脚末行基线 y={y + 46 + 164:.0f}mm")
    body = "\n".join(parts)
    b = BLEED
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W+2*b}mm" height="{H+2*b}mm" '
        f'viewBox="{-b} {-b} {W+2*b} {H+2*b}">\n'
        f"<title>学而思魔法校·叶子书房 灯箱软膜 {W}×{H}mm（含{b}mm出血）</title>\n{body}\n</svg>\n"
    )
    OUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1e6:.1f} MB)")


build()
