#!/usr/bin/env python3
"""学而思魔法校 · 叶子书房 灯箱软膜（成品 1260 × 2660 mm）。

主题：作业本 + 一周日历。方格纸底、荧光笔标题、价签、日历卡、便利贴卖点、体验券。
生成一份 SVG，单位为毫米，所有文字都用字体轮廓直接画成路径（已转曲），
印刷端不需要装字体。画面四周按 BLEED 毫米出血绘制背景。

用法: python3 -I build.py <字体目录> <输出.svg>

字体（均可免费商用，SIL OFL）：
  KuaiLe.ttf                  站酷快乐体       标题、手写感小标题
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
X0, X1 = 90, W - 90  # 版心左右边

# ---------------------------------------------------------------- 配色
INK = "#1B2A5E"       # 正文深蓝
BLUE = "#2F6BFF"
ORANGE = "#FF6B2C"
RED = "#EF3E36"
YELLOW = "#FFD23F"     # 荧光笔
GREEN = "#2DB36A"
GRID = "#E3EDFA"
GREY = "#4A5570"
WHITE = "#FFFFFF"
NOTE_COLORS = ["#FFE76A", "#FFC2D4", "#BFE0FF", "#C6EFB0"]  # 便利贴
NOTE_NUM = ["#F5B400", "#FF7FA6", "#6FAEFF", "#6CCB55"]


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


def runs(items, size, x, y, anchor="start", track=0.0, stroke=None, sw=0, check=True):
    """items: [(文字, 字体, 颜色), ...]，同一行内按顺序排；返回 (svg, 起点x, 宽度)。"""
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
    out = []
    if stroke:
        d = " ".join(p for p, _ in paths)
        out.append(f'<path d="{d}" fill="{stroke}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>')
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


def highlighter(x, y, w, h, color=YELLOW):
    """荧光笔涂抹：两端略斜、边缘不齐的色块。"""
    return (
        f'<path d="M{x+10} {y+6} L{x+w-4} {y} Q{x+w+10} {y+h*0.5} {x+w-2} {y+h} '
        f'L{x+6} {y+h-4} Q{x-10} {y+h*0.45} {x+10} {y+6}Z" fill="{color}"/>'
    )


def check_mark(x, y, s, color=RED, sw=None):
    """手写对勾，(x, y) 为左端点。"""
    sw = sw or s * 0.18
    return line(f"M{x} {y} Q{x+s*0.2} {y+s*0.22} {x+s*0.32} {y+s*0.42} Q{x+s*0.6} {y-s*0.1} {x+s} {y-s*0.48}", color, sw)


def sparkle(cx, cy, r, color):
    k = r * 0.22
    return (
        f'<path d="M{cx} {cy-r} Q{cx+k} {cy-k} {cx+r} {cy} Q{cx+k} {cy+k} {cx} {cy+r} '
        f'Q{cx-k} {cy+k} {cx-r} {cy} Q{cx-k} {cy-k} {cx} {cy-r}Z" fill="{color}"/>'
    )


def alarm_clock(cx, cy, r):
    """闹钟：表盘上半小时的扇区涂成橙色。"""
    out = [
        # 铃铛与腿
        f'<path d="M{cx-r*0.95} {cy-r*0.55} A{r*0.42} {r*0.42} 0 0 1 {cx-r*0.4} {cy-r*1.05}Z" fill="{RED}" stroke="{INK}" stroke-width="6" stroke-linejoin="round"/>',
        f'<path d="M{cx+r*0.95} {cy-r*0.55} A{r*0.42} {r*0.42} 0 0 0 {cx+r*0.4} {cy-r*1.05}Z" fill="{RED}" stroke="{INK}" stroke-width="6" stroke-linejoin="round"/>',
        line(f"M{cx-r*0.55} {cy+r*0.8} L{cx-r*0.78} {cy+r*1.1}", INK, 9),
        line(f"M{cx+r*0.55} {cy+r*0.8} L{cx+r*0.78} {cy+r*1.1}", INK, 9),
        circle(cx, cy, r, WHITE, f'stroke="{INK}" stroke-width="9"'),
        # 0—30 分钟扇区
        f'<path d="M{cx} {cy} L{cx} {cy-r*0.82} A{r*0.82} {r*0.82} 0 0 1 {cx} {cy+r*0.82}Z" fill="{ORANGE}" opacity="0.9"/>',
    ]
    for i in range(12):
        x1, y1 = polar(cx, cy, r * 0.84, i * 30)
        x2, y2 = polar(cx, cy, r * 0.72 if i % 3 == 0 else r * 0.77, i * 30)
        out.append(line(f"M{_num(x1)} {_num(y1)} L{_num(x2)} {_num(y2)}", INK, 6 if i % 3 == 0 else 4))
    out += [
        line(f"M{cx} {cy} L{cx} {cy+r*0.62}", INK, 9),
        line(f"M{cx} {cy} L{cx-r*0.3} {cy-r*0.36}", INK, 9),
        circle(cx, cy, r * 0.09, INK),
    ]
    return "\n".join(out)


def pencil(x, y, length, deg):
    L, w = length, length * 0.16
    return (
        f'<g transform="translate({x} {y}) rotate({deg})">'
        f'<rect x="0" y="{-w/2}" width="{L*0.72}" height="{w}" fill="{YELLOW}" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/>'
        f'<rect x="{-L*0.12}" y="{-w/2}" width="{L*0.12}" height="{w}" rx="{w*0.3}" fill="#FF8FB1" stroke="{INK}" stroke-width="5"/>'
        f'<path d="M{L*0.72} {-w/2} L{L} 0 L{L*0.72} {w/2}Z" fill="#F7D9B0" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/>'
        f'<path d="M{L*0.9} {-w*0.18} L{L} 0 L{L*0.9} {w*0.18}Z" fill="{INK}"/>'
        f'<line x1="0" y1="0" x2="{L*0.72}" y2="0" stroke="#E5A800" stroke-width="4"/>'
        "</g>"
    )


# ---------------------------------------------------------------- 画面
def background():
    b = BLEED
    out = [f'<rect x="{-b}" y="{-b}" width="{W+2*b}" height="{H+2*b}" fill="{WHITE}"/>']
    step = 40
    d = []
    for x in range(-b // step * step, W + b + 1, step):
        d.append(f"M{x} {-b} V{H+b}")
    for y in range(-b // step * step, H + b + 1, step):
        d.append(f"M{-b} {y} H{W+b}")
    out.append(f'<path d="{" ".join(d)}" stroke="{GRID}" stroke-width="1.6" fill="none"/>')
    return "\n".join(out)


def spiral_top():
    """顶部线圈装订。"""
    out = []
    for i in range(14):
        x = 75 + i * 85
        out.append(circle(x, 62, 13, "#2B3A67"))
        out.append(line(f"M{x-4} 62 C{x-30} 30 {x-26} -10 {x-8} -40", "#8E9BBD", 10))
    return "\n".join(out)


def brand(cy):
    tag_size, name_size = 42, 62
    tag_w = N9.width("叶子书房", tag_size) + 112
    out = [
        rrect(X0, cy - 38, tag_w, 76, 38, GREEN),
        f'<g transform="translate({X0+26} {cy+6}) rotate(-40)">'
        f'<path d="M0 0 Q20 -16 44 0 Q24 16 0 0Z" fill="{WHITE}"/></g>',
        text("叶子书房", N9, tag_size, X0 + 78, baseline(cy, tag_size), WHITE),
        text("学而思魔法校", N9, name_size, X0 + tag_w + 26, baseline(cy, name_size), INK),
    ]
    return "\n".join(out)


def headline(top):
    s1, s2 = 192, 138
    b1 = top + 0.79 * s1
    w_mei = KL.width("每天", s1)
    w_ban = KL.width("半小时", s1)
    out = [highlighter(X0 + w_mei - 6, b1 - 0.36 * s1, w_ban + 18, 0.42 * s1)]
    l1, _, w1 = runs([("每天半小时", KL, INK)], s1, X0, b1, stroke=INK, sw=3)
    b2 = b1 + 0.07 * s1 + 46 + 0.79 * s2
    l2, _, w2 = runs([("不把问题", KL, BLUE), ("攒到周末", KL, BLUE)], s2, X0, b2, stroke=BLUE, sw=3)
    out += [l1, l2]
    # 第一行右侧：闹钟
    out.append(alarm_clock(X0 + w1 + 145, top + 0.42 * s1, 96))
    out.append(sparkle(X0 + w1 + 40, top + 6, 20, YELLOW))
    out.append(sparkle(1196, b2 - 70, 16, "#FF8FB1"))
    return "\n".join(out), b2 + 0.07 * s2


def price_tag(top):
    """吊牌：左侧服务说明，右侧均价。整体轻微倾斜。"""
    x, w, h = X0 + 20, X1 - X0 - 20, 220
    y = top
    split = x + w - 330
    body = (
        f'M{x+70} {y} H{x+w-28} Q{x+w} {y} {x+w} {y+28} V{y+h-28} Q{x+w} {y+h} {x+w-28} {y+h} '
        f'H{x+70} L{x} {y+h/2}Z'
    )
    cy = y + h / 2
    out = [
        # 吊绳
        line(f"M{x+48} {cy} C{x-10} {cy-90} {x-40} {cy-40} {x-60} {cy-150}", "#8E9BBD", 6),
        f'<path transform="translate(8 10)" d="{body}" fill="{INK}" opacity="0.15"/>',
        f'<path d="{body}" fill="{BLUE}"/>',
        circle(x + 48, cy, 15, WHITE, f'stroke="{INK}" stroke-width="5"'),
        line(f"M{split} {y+26} V{y+h-26}", WHITE, 5, 'stroke-dasharray="4 14" opacity="0.85"'),
    ]
    lx = x + 110
    out.append(runs([("双师一对一", N9, YELLOW), ("的服务", N9, WHITE)], 62, lx, baseline(cy - 46, 62))[0])
    out.append(runs([("小班课", N9, YELLOW), ("的价格", N9, WHITE)], 62, lx, baseline(cy + 46, 62))[0])
    rx = split + 165
    out.append(text("均价", N7, 34, rx, baseline(cy - 66, 34), WHITE, "middle"))
    out.append(text("100+", N9, 104, rx, baseline(cy + 4, 104), YELLOW, "middle"))
    out.append(text("元/小时", N7, 32, rx, baseline(cy + 70, 32), WHITE, "middle"))
    return f'<g transform="rotate(-2 {W/2} {cy})">' + "\n".join(out) + "</g>", y + h


def week(top):
    """一周日历：周二至周五各约 30 分钟，周末 2 小时。"""
    out = []
    head_cy = top + 30
    out.append(text("一周这样安排", KL, 62, X0, baseline(head_cy, 62), INK))
    _, sx, sw_ = runs([("每周至少4小时学练", KL, RED)], 40, X1, baseline(head_cy + 4, 40), "end", check=False)
    out.append(text("每周至少4小时学练", KL, 40, X1, baseline(head_cy + 4, 40), RED, "end"))
    out.append(line(f"M{sx-4} {head_cy+34} Q{sx+sw_/2} {head_cy+24} {sx+sw_+4} {head_cy+32}", RED, 5))

    cards_top, ch = top + 100, 296
    small_w, gap = 168, 22
    x = X0
    for d in ["周二", "周三", "周四", "周五"]:
        out.append(calendar_card(x, cards_top, small_w, ch, d, BLUE, "30", "分钟", "约"))
        x += small_w + gap
    out.append(calendar_card(x, cards_top, X1 - x, ch, "周末", ORANGE, "2", "小时", None, "同类题复测"))
    note_cy = cards_top + ch + 56
    out.append(runs([("老师答疑、补讲、复盘", N7, INK), ("不占这4小时", N7, RED), ("，已含在课程费内", N7, INK)],
                    34, W / 2, baseline(note_cy, 34), "middle")[0])
    return "\n".join(out), note_cy + 24


def calendar_card(x, y, w, h, day, color, big, unit, prefix=None, sub=None):
    band = 74
    out = [
        rrect(x + 7, y + 9, w, h, 22, INK, extra='opacity="0.14"'),
        rrect(x, y, w, h, 22, WHITE, INK, 5),
        f'<path d="M{x} {y+band} V{y+22} Q{x} {y} {x+22} {y} H{x+w-22} Q{x+w} {y} {x+w} {y+22} V{y+band}Z" fill="{color}" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/>',
    ]
    for rx in (x + w * 0.3, x + w * 0.7):
        out.append(rrect(rx - 7, y - 20, 14, 42, 7, "#8E9BBD", INK, 4))
    out.append(text(day, N9, 40, x + w / 2, baseline(y + band / 2 + 4, 40), WHITE, "middle"))
    num_cy, sub_cy = y + band + 66, y + band + 132
    size = 86
    if prefix:  # 工作日：小字"约" + 数字，单位放下一行
        bw, pw = N9.width(big, size), N7.width(prefix, 30)
        bx = x + w / 2 - (bw + pw + 4) / 2
        out.append(text(prefix, N7, 30, bx, baseline(num_cy, size), GREY))
        out.append(text(big, N9, size, bx + pw + 4, baseline(num_cy, size), INK))
        out.append(text(unit, N7, 32, x + w / 2, baseline(sub_cy, 32), INK, "middle"))
    else:  # 周末：数字与单位同一行，下一行写安排
        bw, uw = N9.width(big, size), N7.width(unit, 34)
        bx = x + w / 2 - (bw + 6 + uw) / 2
        out.append(text(big, N9, size, bx, baseline(num_cy, size), INK))
        out.append(text(unit, N7, 34, bx + bw + 6, baseline(num_cy, size), INK))
        out.append(text(sub, N9, 34, x + w / 2, baseline(sub_cy, 34), RED, "middle"))
    out.append(check_mark(x + w / 2 - 24, y + h - 36, 48))
    return "\n".join(out)


NOTES = [
    ([[("哪里不会，", INK)], [("就从哪里补", RED)]], ["先找准薄弱点，", "再制定个人学习计划"]),
    ([[("固定老师跟进，", INK)], [("卡点单独讲", RED)]], ["学习时老师全程在场，", "走神有人提醒，", "不会有人补讲"]),
    ([[("学没学会持续查，", INK)], [("学得咋样看得见", RED)]], ["当天检查 · 周末复测", "每月回查"]),
    ([[("免费体验一周，", RED)], [("合适再报名", INK)]], ["让孩子真实学一学，", "让家长亲眼看一看"]),
]
NOTE_TILT = [-1.6, 1.3, 1.1, -1.4]


def notes(top):
    out = []
    head_cy = top + 30
    sx = X0 + KL.width("家长最关心的", 62)
    out.append(highlighter(sx - 6, head_cy - 4, KL.width("四件事", 62) + 14, 34, "#FFC2D4"))
    out.append(text("家长最关心的四件事", KL, 62, X0, baseline(head_cy, 62), INK))
    out.append(pencil(X1 - 250, head_cy + 8, 240, -8))

    nw, nh, gap = (X1 - X0 - 40) / 2, 326, 30
    y0 = top + 104
    for i, (title, desc) in enumerate(NOTES):
        r_, c_ = divmod(i, 2)
        x = X0 + c_ * (nw + 40)
        y = y0 + r_ * (nh + gap)
        out.append(note(x, y, nw, nh, title, desc, i))
    return "\n".join(out), y0 + 2 * nh + gap


def note(x, y, w, h, title, desc, i):
    cx, cy = x + w / 2, y + h / 2
    g = [
        rrect(x + 8, y + 12, w, h, 10, INK, extra='opacity="0.13"'),
        rrect(x, y, w, h, 10, NOTE_COLORS[i]),
        # 右下角折角
        f'<path d="M{x+w} {y+h-60} L{x+w-60} {y+h} L{x+w-10} {y+h} Q{x+w} {y+h} {x+w} {y+h-10}Z" fill="{WHITE}" opacity="0.55"/>',
        f'<g opacity="0.55">{text(str(i + 1), KL, 170, x + w - 30, y + h - 22, NOTE_NUM[i], "end", check=False)}</g>',
    ]
    tx = x + 40
    for k, line_runs in enumerate(title):
        g.append(runs([(t, N9, c) for t, c in line_runs], 52, tx, y + 90 + k * 64)[0])
    for k, d in enumerate(desc):
        g.append(text(d, N5, 34, tx, y + 208 + k * 44, GREY))
    # 胶带
    g.append(f'<g transform="rotate({-NOTE_TILT[i]*3} {cx} {y})">' + rrect(cx - 80, y - 24, 160, 48, 4, WHITE, "#C9D3E6", 2, 'opacity="0.8"') + "</g>")
    return f'<g transform="rotate({NOTE_TILT[i]} {cx} {cy})">' + "\n".join(g) + "</g>"


def ticket(top):
    """体验券：左侧主券 + 右侧二维码存根，中间打孔虚线。"""
    x, w, h = X0 - 10, X1 - X0 + 20, 290
    y = top
    stub = 310
    sx = x + w - stub
    r = 26
    body = (
        f'M{x+24} {y} H{sx-r} A{r} {r} 0 0 0 {sx+r} {y} H{x+w-24} Q{x+w} {y} {x+w} {y+24} '
        f'V{y+h-24} Q{x+w} {y+h} {x+w-24} {y+h} H{sx+r} A{r} {r} 0 0 0 {sx-r} {y+h} H{x+24} '
        f'Q{x} {y+h} {x} {y+h-24} V{y+24} Q{x} {y} {x+24} {y}Z'
    )
    out = [
        f'<path transform="translate(8 12)" d="{body}" fill="{INK}" opacity="0.15"/>',
        f'<path d="{body}" fill="{ORANGE}"/>',
        line(f"M{sx} {y+r+14} V{y+h-r-14}", WHITE, 5, 'stroke-dasharray="4 14"'),
    ]
    tx = x + 52
    out.append(runs([("联系欧老师 · ", KL, WHITE), ("预约免费体验", KL, YELLOW)], 62, tx, y + 92)[0])
    py = y + 192
    out.append(circle(tx + 36, py - 30, 36, WHITE))
    out.append(
        f'<path transform="translate({tx+36} {py-30}) scale(1.35)" d="M-9 -13 C-12 -13 -14 -10 -13 -6 C-10 6 -3 12 7 14 '
        f'C10 15 13 13 13 10 L13 6 C13 4 11 3 9 3 L5 4 C3 2 -1 -2 -3 -5 L-2 -9 C-1 -11 -3 -13 -5 -13Z" fill="{ORANGE}"/>'
    )
    out.append(text("191 6627 8890", N9, 86, tx + 88, py, WHITE, track=0.01))
    out.append(text("深圳南山 · 缤纷年华三楼叶子书房（麒麟中学斜对面）", N7, 28, tx, y + 252, WHITE))
    # 二维码存根
    qs = 186
    qx, qy = sx + (stub - qs) / 2, y + 30
    out += [
        rrect(qx, qy, qs, qs, 18, WHITE),
        rrect(qx + 12, qy + 12, qs - 24, qs - 24, 10, "none", "#9AA5BE", 4, 'stroke-dasharray="12 9"'),
        text("微信二维码", N7, 28, qx + qs / 2, qy + qs / 2 - 2, "#7A859E", "middle"),
        text("（待替换）", N5, 22, qx + qs / 2, qy + qs / 2 + 32, "#9AA5BE", "middle"),
        text("扫码加微信", N9, 30, sx + stub / 2, y + h - 26, WHITE, "middle"),
    ]
    return "\n".join(out), y + h


def build():
    parts = [background(), spiral_top(), brand(168)]
    head, y = headline(250)
    parts.append(head)
    tag, y = price_tag(y + 60)
    parts.append(tag)
    wk, y = week(y + 76)
    parts.append(wk)
    nt, y = notes(y + 50)
    parts.append(nt)
    tk, _ = ticket(H - 60 - 290)
    parts.append(tk)
    print(f"便利贴底部 y={y:.0f}mm，体验券顶部 y={H - 60 - 290}mm")
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
