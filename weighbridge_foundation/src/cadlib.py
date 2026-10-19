# -*- coding: utf-8 -*-
"""基于 ezdxf 的结构施工图绘图工具。

约定：
- 模型空间单位 mm。每张图为 A1 图框，按 1:SHEET_SCALE 放大绘于模型空间。
- 同一张图内的不同比例视图，几何按 f = SHEET_SCALE/比例 缩放绘制，
  尺寸标注用 DIMLFAC = 1/f 还原真实尺寸。
- View 的所有绘图方法均使用“真实尺寸(mm)”的局部坐标；
  文字高度、符号大小均以“图纸毫米”给出。
"""
import math

import ezdxf
from ezdxf import bbox
from ezdxf.enums import TextEntityAlignment as TA
from shapely.geometry import LineString, Polygon, box as sbox
from shapely.ops import unary_union
from shapely.strtree import STRtree

SHEET_SCALE = 50
A1 = (841.0, 594.0)

LAYERS = {
    "S-AXIS": dict(color=1, linetype="AXIS", lineweight=18),
    "S-CONC": dict(color=7, linetype="Continuous", lineweight=50),
    "S-THIN": dict(color=7, linetype="Continuous", lineweight=18),
    "S-HIDE": dict(color=8, linetype="DASH", lineweight=18),
    "S-HIDE2": dict(color=6, linetype="DASH", lineweight=35),
    "S-REBAR": dict(color=2, linetype="Continuous", lineweight=50),
    "S-STEEL": dict(color=4, linetype="Continuous", lineweight=35),
    "S-PIPE": dict(color=5, linetype="DASH", lineweight=35),
    "S-HATCH": dict(color=8, linetype="Continuous", lineweight=13),
    "S-SOIL": dict(color=8, linetype="Continuous", lineweight=13),
    "S-DIM": dict(color=3, linetype="Continuous", lineweight=13),
    "S-TEXT": dict(color=7, linetype="Continuous", lineweight=18),
    "S-SYMB": dict(color=7, linetype="Continuous", lineweight=25),
    "S-WATER": dict(color=5, linetype="DASHDOT2", lineweight=25),
    "S-FRAME": dict(color=7, linetype="Continuous", lineweight=90),
    "S-TABLE": dict(color=7, linetype="Continuous", lineweight=18),
}

# 填充图案比例（图纸尺度下的经验值）
PAT_SCALE = {
    "ANSI31": 40.0,
    "AR-CONC": 2.0,
    "GRAVEL": 14.0,
    "EARTH": 70.0,
    "AR-SAND": 2.0,
    "ANSI37": 40.0,
}

# 自定义图案（定义单位：图纸毫米，按 SHEET_SCALE 放大）
CUSTOM_PAT = {
    # 级配砂石：交错圆点 + 短斜线
    "ZJ-GRAVEL": [
        [0.0, (0.0, 0.0), (2.2, 2.6), [0.0, -4.4]],
        [0.0, (1.1, 1.3), (2.2, 2.6), [0.0, -4.4]],
        [35.0, (0.6, 0.4), (2.9, 3.4), [0.55, -5.0]],
        [125.0, (2.3, 2.1), (3.1, 3.7), [0.45, -6.0]],
    ],
}


def cjk_width(s):
    """估算字符串宽度（以字高为单位，宽度系数0.7）。"""
    w = 0.0
    for ch in s:
        w += 1.0 if ord(ch) > 0x2E80 else 0.6
    return w


NO_LINE_START = set("，。；：、）)」』》,.;:!?！？%℃”’")


def _tokens(s):
    """切分为不可断开的单元：中文逐字；连续西文字符/数字为一个单元；行首禁则标点并入前一单元。"""
    toks = []
    buf = ""
    for ch in s:
        if ord(ch) > 0x2E80 or ch == " ":
            if buf:
                toks.append(buf)
                buf = ""
            if toks and ch in NO_LINE_START:
                toks[-1] += ch
            else:
                toks.append(ch)
        else:
            if ch in NO_LINE_START and not buf and toks:
                toks[-1] += ch
            else:
                buf += ch
    if buf:
        toks.append(buf)
    # 行尾禁则：开括号、开引号与后一单元合并
    out = []
    carry = ""
    for t in toks:
        if t and t[-1] in "(（《“‘[":
            carry += t
            continue
        out.append(carry + t)
        carry = ""
    if carry:
        out.append(carry)
    return out


def _tw(t):
    return sum(1.0 if ord(c) > 0x2E80 else 0.55 for c in t)


def wrap_text(s, max_chars):
    """按显示宽度折行（中文按1、西文按0.55计），不拆分西文/数字串，避免标点出现在行首。"""
    lines, cur, cw = [], "", 0.0
    for t in _tokens(s):
        w = _tw(t)
        if cw + w > max_chars and cur:
            lines.append(cur.rstrip())
            cur, cw = "", 0.0
            if t == " ":
                continue
        cur += t
        cw += w
    if cur:
        lines.append(cur.rstrip())
    return lines


class CAD:
    def __init__(self, font="simfang.ttf"):
        doc = ezdxf.new("R2013", setup=True)
        doc.header["$INSUNITS"] = 4
        doc.header["$MEASUREMENT"] = 1
        doc.header["$LUNITS"] = 2
        doc.header["$LTSCALE"] = SHEET_SCALE
        doc.header["$PSLTSCALE"] = 1
        # 线型（单位：图纸毫米，乘 LTSCALE）
        if "AXIS" not in doc.linetypes:
            doc.linetypes.add("AXIS", pattern=[24.0, 18.0, -2.5, 1.0, -2.5],
                              description="Axis ____ _ ____ _")
        if "DASH" not in doc.linetypes:
            doc.linetypes.add("DASH", pattern=[5.0, 3.5, -1.5],
                              description="Dash __ __ __")
        if "DASHDOT2" not in doc.linetypes:
            doc.linetypes.add("DASHDOT2", pattern=[12.0, 8.0, -1.5, 1.0, -1.5],
                              description="Dash dot __ . __ .")
        doc.styles.new("HZ", dxfattribs={"font": font, "width": 0.7})
        ds = doc.dimstyles.new("ZJ")
        ds.dxf.dimtxsty = "HZ"
        ds.dxf.dimtxt = 2.5
        ds.dxf.dimasz = 1.2
        ds.dxf.dimblk = "ARCHTICK"
        ds.dxf.dimscale = SHEET_SCALE
        ds.dxf.dimexe = 1.5
        ds.dxf.dimexo = 1.5
        ds.dxf.dimgap = 0.6
        ds.dxf.dimtad = 1
        ds.dxf.dimtih = 0
        ds.dxf.dimtoh = 0
        ds.dxf.dimdec = 0
        ds.dxf.dimtmove = 2
        ds.dxf.dimclrd = 3
        ds.dxf.dimclre = 3
        ds.dxf.dimclrt = 7
        ds.dxf.dimdle = 0
        for name, a in LAYERS.items():
            doc.layers.add(name, color=a["color"], linetype=a["linetype"],
                           lineweight=a["lineweight"])
        self.doc = doc
        self.msp = doc.modelspace()

    def sheet(self, x0, y0=0.0):
        return Sheet(self, x0, y0)


class Sheet:
    def __init__(self, cad, x0, y0):
        self.cad = cad
        self.x0, self.y0 = x0, y0
        self.paper = View(self, 0.0, 0.0, 1.0)

    def view(self, ox, oy, scale):
        """ox, oy：视图局部原点在图纸上的位置（图纸毫米）；scale：比例分母。"""
        return View(self, ox, oy, scale)


class View:
    def __init__(self, sheet, ox, oy, scale):
        self.sheet = sheet
        self.cad = sheet.cad
        self.msp = sheet.cad.msp
        self.k = scale
        self.f = SHEET_SCALE / scale
        self.X0 = sheet.x0 + ox * SHEET_SCALE
        self.Y0 = sheet.y0 + oy * SHEET_SCALE

    # ---------- 坐标 ----------
    def P(self, x, y):
        return (self.X0 + x * self.f, self.Y0 + y * self.f)

    def pp(self, d):
        """图纸毫米 -> 真实尺寸"""
        return d * self.k

    def H(self, h):
        """图纸毫米 -> 模型单位"""
        return h * SHEET_SCALE

    # ---------- 基本图元 ----------
    def line(self, p1, p2, layer="S-CONC", **kw):
        a = {"layer": layer}
        a.update(kw)
        return self.msp.add_line(self.P(*p1), self.P(*p2), dxfattribs=a)

    def pl(self, pts, layer="S-CONC", closed=False, width=None, **kw):
        a = {"layer": layer}
        a.update(kw)
        e = self.msp.add_lwpolyline([self.P(*p) for p in pts], close=closed, dxfattribs=a)
        if width is not None:
            e.dxf.const_width = self.H(width)
        return e

    def rect(self, x1, y1, x2, y2, layer="S-CONC", **kw):
        return self.pl([(x1, y1), (x2, y1), (x2, y2), (x1, y2)], layer, closed=True, **kw)

    def circle(self, c, r, layer="S-THIN", **kw):
        a = {"layer": layer}
        a.update(kw)
        return self.msp.add_circle(self.P(*c), r * self.f, dxfattribs=a)

    def circle_p(self, c, r_paper, layer="S-THIN"):
        return self.msp.add_circle(self.P(*c), self.H(r_paper), dxfattribs={"layer": layer})

    def arc(self, c, r, a1, a2, layer="S-THIN"):
        return self.msp.add_arc(self.P(*c), r * self.f, a1, a2, dxfattribs={"layer": layer})

    def dot(self, c, d_paper=1.0, layer="S-REBAR", real_d=None):
        """实心圆点（钢筋截面）。real_d 给出时按真实直径但不小于 d_paper。"""
        r = self.H(d_paper) / 2
        if real_d is not None:
            r = max(r, real_d * self.f / 2)
        h = self.msp.add_hatch(color=256, dxfattribs={"layer": layer})
        h.set_solid_fill(color=256)
        ep = h.paths.add_edge_path()
        ep.add_arc(self.P(*c), r, 0, 360)
        return h

    def hatch(self, loops, pattern="ANSI31", layer="S-HATCH", rel=1.0, angle=0.0):
        """loops：一个或多个闭合轮廓（真实坐标）；第一个为外轮廓，其余为孔。"""
        if loops and isinstance(loops[0][0], (int, float)):
            loops = [loops]
        h = self.msp.add_hatch(color=256, dxfattribs={"layer": layer})
        if pattern == "SOLID":
            h.set_solid_fill(color=256)
        elif pattern in CUSTOM_PAT:
            h.set_pattern_fill(pattern, color=256, scale=SHEET_SCALE * rel, angle=angle,
                               definition=CUSTOM_PAT[pattern])
        else:
            h.set_pattern_fill(pattern, color=256, scale=PAT_SCALE.get(pattern, 20.0) * rel,
                               angle=angle)
        for i, lp in enumerate(loops):
            h.paths.add_polyline_path([self.P(*p) for p in lp], is_closed=True,
                                      flags=1 if i == 0 else 0)
        return h

    def rc_hatch(self, loops, layer="S-HATCH"):
        """钢筋混凝土断面填充（45°斜线+混凝土）。"""
        self.hatch(loops, "ANSI31", layer)
        self.hatch(loops, "AR-CONC", layer)

    # ---------- 文字 ----------
    def text(self, x, y, s, h=3.5, align="MC", rot=0.0, layer="S-TEXT", wf=0.7):
        al = {
            "MC": TA.MIDDLE_CENTER, "ML": TA.MIDDLE_LEFT, "MR": TA.MIDDLE_RIGHT,
            "BL": TA.BOTTOM_LEFT, "BC": TA.BOTTOM_CENTER, "BR": TA.BOTTOM_RIGHT,
            "TL": TA.TOP_LEFT, "TC": TA.TOP_CENTER, "TR": TA.TOP_RIGHT,
        }[align]
        e = self.msp.add_text(s, height=self.H(h), rotation=rot,
                              dxfattribs={"layer": layer, "style": "HZ", "width": wf})
        e.set_placement(self.P(x, y), align=al)
        return e

    def text_lines(self, x, y, lines, h=3.5, gap=1.6, layer="S-TEXT", indent=None):
        """自 (x, y) 向下逐行书写（左对齐），返回结束处 y（真实坐标）。"""
        step = self.pp(h * gap)
        for ln in lines:
            if ln is None:
                y -= step * 0.5
                continue
            self.text(x, y, ln, h, "TL", layer=layer)
            y -= step
        return y

    def para(self, x, y, s, width_chars, h=3.5, gap=1.6, hang=0):
        """带悬挂缩进的段落。hang：续行缩进的字数。"""
        first = wrap_text(s, width_chars)
        if hang and len(first) > 1:
            head = first[0]
            rest = wrap_text(s[len(head):], width_chars - hang)
            lines = [head] + ["　" * hang + r for r in rest]
        else:
            lines = first
        return self.text_lines(x, y, lines, h, gap)

    # ---------- 尺寸 ----------
    def _dim(self, base, p1, p2, angle, text=None, layer="S-DIM", loc=None):
        ov = {}
        if abs(self.f - 1.0) > 1e-9:
            ov["dimlfac"] = 1.0 / self.f
        kw = dict(base=self.P(*base), p1=self.P(*p1), p2=self.P(*p2), angle=angle,
                  dimstyle="ZJ", override=ov, dxfattribs={"layer": layer})
        if text is not None:
            kw["text"] = text
        if loc is not None:
            kw["location"] = self.P(*loc)
        d = self.msp.add_linear_dim(**kw)
        d.render()
        return d

    def dimh(self, x1, x2, y, by, text=None, ext=None, tx=None):
        """水平尺寸：被测点高度 y，尺寸线位置 by（真实坐标）。
        ext：尺寸界线长度（图纸mm），给出时界线起点取在尺寸线附近；tx：文字中心 X（真实坐标）。"""
        if ext is not None:
            y = by + (self.pp(ext) if y > by else -self.pp(ext))
        loc = None if tx is None else (tx, by + self.pp(2.2))
        return self._dim((x1, by), (x1, y), (x2, y), 0, text, loc=loc)

    def dimv(self, y1, y2, x, bx, text=None, ext=None):
        if ext is not None:
            x = bx + (self.pp(ext) if x > bx else -self.pp(ext))
        return self._dim((bx, y1), (x, y1), (x, y2), 90, text)

    def chainh(self, xs, y, by, texts=None, ext=None, avoid=()):
        """连续水平尺寸。avoid：竖向线（如轴线）的 X 坐标，文字若居中压在其上则侧移。"""
        for i in range(len(xs) - 1):
            t = None if texts is None else texts[i]
            if t == "":
                continue
            mid = (xs[i] + xs[i + 1]) / 2
            tx = None
            if any(abs(mid - a) < self.pp(3.0) for a in avoid):
                tx = mid + self.pp(4.5)
            self.dimh(xs[i], xs[i + 1], y, by, t, ext, tx)

    def chainv(self, ys, x, bx, texts=None, ext=None):
        for i in range(len(ys) - 1):
            t = None if texts is None else texts[i]
            if t == "":
                continue
            self.dimv(ys[i], ys[i + 1], x, bx, t, ext)

    # ---------- 符号 ----------
    def elev(self, x, y, label, side="R", down=False, h=2.5, length=13.0):
        """标高符号：三角形尖点位于 (x, y)。side：文字在右(R)/左(L)。"""
        s = self.pp(3.0)
        L = self.pp(length)
        sg = -1 if down else 1
        tip = (x, y)
        a = (x - s, y + sg * s)
        b = (x + s, y + sg * s)
        self.pl([tip, a, b], "S-SYMB", closed=True)
        if side == "R":
            self.line(a, (x - s + L, y + sg * s), "S-SYMB")
            tx = x - s + self.pp(0.8)
            al = "BL"
        else:
            self.line(b, (x + s - L, y + sg * s), "S-SYMB")
            tx = x + s - self.pp(0.8)
            al = "BR"
        # 向下的标高：文字整体置于横线以下（考虑字形上沿高出字高约 30%）
        ty = y + sg * s + self.pp(0.6) if not down else y + sg * s - self.pp(1.35 * h + 0.8)
        self.text(tx, ty, label, h, al)

    def leader(self, pts, s, h=3.0, side="R", layer="S-SYMB", under=True, marks=None):
        """引出线：pts 为折线（真实坐标），最后一点起画水平线，文字写在横线上方。
        marks：钢筋编号列表，在文字前绘制带圆圈的编号。"""
        self.pl(pts, layer)
        x, y = pts[-1]
        lines = s if isinstance(s, (list, tuple)) else [s]
        r = h * 0.62
        mw = (2 * r + 0.6) * len(marks) if marks else 0.0
        wmax = max(cjk_width(t) for t in lines) * h + 1.0 + mw
        L = self.pp(wmax)
        if side == "R":
            self.line((x, y), (x + L, y), layer)
            x0 = x + self.pp(0.5)
        else:
            self.line((x, y), (x - L, y), layer)
            x0 = x - L + self.pp(0.5)
        ty = y + self.pp(0.8)
        cx = x0
        if marks:
            for m in marks:
                c = (cx + self.pp(r), ty + self.pp(h * 0.5))
                self.circle_p(c, r, "S-SYMB")
                self.text(c[0], c[1], str(m), h * (0.7 if len(str(m)) < 2 else 0.58), "MC")
                cx += self.pp(2 * r + 0.6)
        for i, t in enumerate(lines):
            if i == 0:
                self.text(cx, ty, t, h, "BL")
            else:
                self.text(cx, y - self.pp(0.8 + (h * 1.5) * (i - 1)), t, h, "TL")
        # 起点小圆点
        self.dot(pts[0], 0.8, "S-SYMB")

    def axis_bubble(self, x, y, label, r=4.0, h=4.5):
        self.circle_p((x, y), r, "S-SYMB")
        self.text(x, y, label, h, "MC")

    def section_mark(self, p1, p2, label, direction, length=7.0, tick=4.0, h=5.0):
        """剖切符号：p1, p2 为剖切线两端（真实坐标），direction 为投射方向单位向量。"""
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        n = math.hypot(dx, dy)
        ux, uy = dx / n, dy / n
        L = self.pp(length)
        T = self.pp(tick)
        vx, vy = direction
        for (px, py), sgn in ((p1, 1), (p2, -1)):
            q = (px + sgn * ux * L, py + sgn * uy * L)
            self.pl([(px, py), q], "S-SYMB", width=0.6)
            r = (px + vx * T, py + vy * T)
            self.pl([(px, py), r], "S-SYMB", width=0.6)
            tpos = (px + vx * (T + self.pp(4.6)), py + vy * (T + self.pp(4.6)))
            self.text(tpos[0], tpos[1], label, h, "MC")

    def index_mark(self, x, y, num, sheet="-", r=6.0, h=3.5):
        """详图索引符号：上为详图编号，下为所在图号。"""
        self.circle_p((x, y), r, "S-SYMB")
        self.line((x - self.pp(r), y), (x + self.pp(r), y), "S-SYMB")
        self.text(x, y + self.pp(r * 0.45), str(num), h * 0.85, "MC")
        self.text(x, y - self.pp(r * 0.4), str(sheet), h * 0.5, "MC")

    def detail_title(self, x, y, num, name, scale, h=6.0):
        """详图/视图标题：编号圆圈（可选）+ 名称 + 比例，下划粗细双线。"""
        cur = x
        if num is not None:
            R = 6.0
            self.circle_p((cur + self.pp(R), y + self.pp(R * 0.6)), R, "S-SYMB")
            self.text(cur + self.pp(R), y + self.pp(R * 0.6), str(num), h * 0.8, "MC")
            cur += self.pp(2 * R + 3)
        w = cjk_width(name) * h
        self.text(cur, y, name, h, "BL")
        if scale:
            self.text(cur + self.pp(w + 4), y, scale, h * 0.7, "BL")
            w += 4 + cjk_width(scale) * h * 0.7
        self.pl([(cur, y - self.pp(1.2)), (cur + self.pp(w), y - self.pp(1.2))], "S-SYMB", width=0.7)
        self.line((cur, y - self.pp(2.4)), (cur + self.pp(w), y - self.pp(2.4)), "S-SYMB")

    def break_line(self, p1, p2, layer="S-THIN"):
        """折断线。"""
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        n = math.hypot(dx, dy)
        ux, uy = dx / n, dy / n
        nx, ny = -uy, ux
        m = (p1[0] + dx / 2, p1[1] + dy / 2)
        a = self.pp(1.5)
        b = self.pp(3.0)
        pts = [p1,
               (m[0] - ux * a, m[1] - uy * a),
               (m[0] - ux * a * 0.4 + nx * b, m[1] - uy * a * 0.4 + ny * b),
               (m[0] + ux * a * 0.4 - nx * b, m[1] + uy * a * 0.4 - ny * b),
               (m[0] + ux * a, m[1] + uy * a),
               p2]
        self.pl(pts, layer)

    def arrow(self, p1, p2, layer="S-SYMB", head=2.5):
        """带实心箭头的直线（p1 -> p2）。"""
        self.line(p1, p2, layer)
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        n = math.hypot(dx, dy)
        ux, uy = dx / n, dy / n
        L = self.pp(head)
        W = self.pp(head * 0.3)
        b = (p2[0] - ux * L, p2[1] - uy * L)
        pts = [p2, (b[0] - uy * W, b[1] + ux * W), (b[0] + uy * W, b[1] - ux * W)]
        h = self.msp.add_hatch(color=256, dxfattribs={"layer": layer})
        h.set_solid_fill(color=256)
        h.paths.add_polyline_path([self.P(*p) for p in pts], is_closed=True)

    def slope_mark(self, x, y, s, length=18.0, ang=0.0, h=2.5, rev=False):
        """坡度箭头（指向下坡），文字在箭杆上方。rev=True 时箭头反向。"""
        L = self.pp(length)
        ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        p1 = (x - ca * L / 2, y - sa * L / 2)
        p2 = (x + ca * L / 2, y + sa * L / 2)
        if rev:
            p1, p2 = p2, p1
        self.arrow(p1, p2)
        self.text(x - sa * self.pp(1.8), y + ca * self.pp(1.8), s, h, "BC", rot=ang)

    # ---------- 表格 ----------
    def table(self, x, y, col_w, rows, row_h=7.0, h=3.0, header_rows=1, aligns=None):
        """x, y：表左上角（图纸毫米视图下使用）。rows：二维字符串列表。"""
        ncol = len(col_w)
        W = sum(col_w)
        Ht = row_h * len(rows)
        self.rect(x, y - Ht, x + W, y, "S-SYMB")
        cx = x
        for w in col_w[:-1]:
            cx += w
            self.line((cx, y), (cx, y - Ht), "S-TABLE")
        for i in range(1, len(rows)):
            lyr = "S-SYMB" if i == header_rows else "S-TABLE"
            self.line((x, y - row_h * i), (x + W, y - row_h * i), lyr)
        for i, r in enumerate(rows):
            cx = x
            for j in range(ncol):
                s = r[j] if j < len(r) else ""
                if s:
                    al = "MC"
                    if aligns and i >= header_rows:
                        al = aligns[j]
                    if al == "ML":
                        self.text(cx + 1.5, y - row_h * (i + 0.5), s, h, "ML")
                    else:
                        self.text(cx + col_w[j] / 2, y - row_h * (i + 0.5), s, h, "MC")
                cx += col_w[j]
        return y - Ht


def draw_frame(sheet, title, number, scale_str, project, subitem, date="2026.10", size=A1):
    """图框 + 标题栏（图纸毫米坐标），size 为图幅 (宽, 高)。"""
    v = sheet.paper
    W, H = size
    v.rect(0, 0, W, H, "S-THIN")
    v.rect(25, 10, W - 10, H - 10, "S-FRAME")
    # 标题栏 220 x 62，右下角
    x0, y0, x1, y1 = W - 10 - 220, 10, W - 10, 72
    v.rect(x0, y0, x1, y1, "S-FRAME")
    # 竖向分区
    xa = x0 + 70   # 左：签字区
    xb = x0 + 150  # 中：工程名称/图名
    v.line((xa, y0), (xa, y1), "S-SYMB")
    v.line((xb, y0), (xb, y1), "S-SYMB")
    # 左签字区 6 行
    labels = ["审  定", "审  核", "项目负责", "专业负责", "校  对", "设  计"]
    rh = (y1 - y0) / 6
    for i, lb in enumerate(labels):
        yy = y1 - rh * (i + 1)
        if i > 0:
            v.line((x0, yy + rh), (xa, yy + rh), "S-TABLE")
        v.text(x0 + 11, yy + rh / 2, lb, 2.8, "MC")
    v.line((x0 + 22, y0), (x0 + 22, y1), "S-TABLE")
    v.line((x0 + 50, y0), (x0 + 50, y1), "S-TABLE")
    # 中区：设计单位 / 工程名称 / 子项 / 图名
    v.line((xa, y1 - 12), (xb, y1 - 12), "S-TABLE")
    v.text((xa + xb) / 2, y1 - 6, "（设计单位名称及出图章）", 3.0, "MC")
    v.line((xa, y1 - 30), (xb, y1 - 30), "S-TABLE")
    v.text(xa + 2, y1 - 15, "工程名称", 2.5, "TL")
    for i, s in enumerate(project):
        v.text((xa + xb) / 2 + 3, y1 - 19.5 - i * 4.5, s, 3.0, "MC")
    v.line((xa, y1 - 40), (xb, y1 - 40), "S-TABLE")
    v.text(xa + 2, y1 - 31.5, "子项", 2.5, "TL")
    v.text((xa + xb) / 2 + 4, y1 - 35.5, subitem, 3.2, "MC")
    v.text(xa + 2, y1 - 41.5, "图名", 2.5, "TL")
    v.text((xa + xb) / 2 + 3, y0 + 10, title, 5.0, "MC")
    # 右区：图号/比例/阶段/日期/版次
    items = [("专业", "结构"), ("阶段", "施工图"), ("图号", number), ("比例", scale_str),
             ("日期", date), ("版次", "A")]
    for i, (k, val) in enumerate(items):
        yy = y1 - rh * (i + 1)
        if i > 0:
            v.line((xb, yy + rh), (x1, yy + rh), "S-TABLE")
        v.text(xb + 9, yy + rh / 2, k, 2.8, "MC")
        v.text(xb + 18 + (x1 - xb - 18) / 2, yy + rh / 2, val, 3.2 if k != "图号" else 4.0, "MC")
    v.line((xb + 18, y0), (xb + 18, y1), "S-TABLE")
    # 图框外左上角图号（便于检索）
    v.text(W - 12, H - 7, number, 3.5, "MR")


# ---------------- 文字遮罩 ----------------
# 穿过文字时断开的细线图层（结构轮廓、钢筋、引出线、表格线不断开，需在布置时避让）
BREAK_LAYERS = {"S-AXIS", "S-THIN", "S-HIDE", "S-HIDE2", "S-PIPE", "S-WATER", "S-SOIL", "S-HATCH"}


def _text_boxes(msp, pad):
    boxes = []
    for e in msp:
        if e.dxftype() == "TEXT":
            items = [e]
        elif e.dxftype() == "DIMENSION":
            items = [v for v in e.virtual_entities() if v.dxftype() in ("TEXT", "MTEXT")]
        else:
            continue
        for t in items:
            b = bbox.extents([t], fast=False)
            if b.has_data:
                boxes.append(sbox(b.extmin.x - pad, b.extmin.y - pad, b.extmax.x + pad, b.extmax.y + pad))
    return boxes


def _attribs(e):
    a = e.dxfattribs()
    for k in ("handle", "owner"):
        a.pop(k, None)
    return a


def mask_texts(msp, pad=0.6):
    """文字遮罩（同 AutoCAD 填充孤岛检测/打断）：
    - 图案填充在文字处挖孔；
    - BREAK_LAYERS 上的直线、多段线在文字处断开。
    pad：文字四周留空（图纸mm）。"""
    boxes = _text_boxes(msp, pad * SHEET_SCALE)
    if not boxes:
        return
    tree = STRtree(boxes)

    def hits(geom):
        return [boxes[i] for i in tree.query(geom) if boxes[i].intersects(geom)]

    for h in list(msp.query("HATCH")):
        if h.dxf.solid_fill:
            continue
        poly = None
        for path in h.paths:
            pts = [(v[0], v[1]) for v in getattr(path, "vertices", [])]
            if len(pts) < 3:
                poly = None
                break
            p = Polygon(pts).buffer(0)
            poly = p if poly is None else poly.symmetric_difference(p)
        if poly is None or poly.is_empty:
            continue
        cut = hits(poly)
        if not cut:
            continue
        res = poly.difference(unary_union(cut))
        if res.is_empty:
            msp.delete_entity(h)
            continue
        h.paths.clear()
        for g in getattr(res, "geoms", [res]):
            if g.geom_type != "Polygon" or g.area <= 0:
                continue
            h.paths.add_polyline_path(list(g.exterior.coords)[:-1], is_closed=True, flags=1)
            for ring in g.interiors:
                h.paths.add_polyline_path(list(ring.coords)[:-1], is_closed=True, flags=0)

    for e in list(msp.query("LINE LWPOLYLINE")):
        if e.dxf.layer not in BREAK_LAYERS:
            continue
        if e.dxftype() == "LINE":
            pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        else:
            if e.dxf.hasattr("const_width") and e.dxf.const_width:
                continue
            pts = [(p[0], p[1]) for p in e.get_points("xy")]
            if e.closed:
                pts.append(pts[0])
        if len(pts) < 2:
            continue
        ln = LineString(pts)
        cut = hits(ln)
        if not cut:
            continue
        res = ln.difference(unary_union(cut))
        a = _attribs(e)
        msp.delete_entity(e)
        for g in getattr(res, "geoms", [res]):
            if g.is_empty or g.length <= 0:
                continue
            c = list(g.coords)
            if e.dxftype() == "LINE" or len(c) == 2:
                la = {k: v for k, v in a.items() if k in ("layer", "linetype", "color", "lineweight",
                                                          "ltscale")}
                msp.add_line(c[0], c[-1], dxfattribs=la)
            else:
                pa = {k: v for k, v in a.items() if k in ("layer", "linetype", "color", "lineweight",
                                                          "ltscale")}
                msp.add_lwpolyline(c, dxfattribs=pa)
