"""GB 机械制图通用工具: 图层/字体/标注样式, 以及常用的绘图与标注函数 (基于 ezdxf)."""
import math

import ezdxf
from ezdxf.enums import MTextEntityAlignment, TextEntityAlignment

FONT_FILE = "simfang.ttf"          # DXF 中使用的字体 (长仿宋)
PREVIEW_FONT = "wqy-zenhei.ttc"    # 预览渲染使用的开源字体

LAYERS = {
    "粗实线": dict(color=7, lineweight=50, linetype="Continuous"),
    "细实线": dict(color=3, lineweight=25, linetype="Continuous"),
    "波浪线": dict(color=3, lineweight=25, linetype="Continuous"),
    "中心线": dict(color=1, lineweight=25, linetype="GB_CENTER"),
    "双点画线": dict(color=6, lineweight=25, linetype="GB_PHANTOM"),
    "剖面线": dict(color=8, lineweight=25, linetype="Continuous"),
    "尺寸": dict(color=3, lineweight=25, linetype="Continuous"),
    "文字": dict(color=7, lineweight=25, linetype="Continuous"),
    "图框": dict(color=7, lineweight=50, linetype="Continuous"),
    "图框细": dict(color=7, lineweight=25, linetype="Continuous"),
    "图片": dict(color=7, lineweight=25, linetype="Continuous"),
}


# ---------------------------------------------------------------- 纯几何工具
def rot(p, a):
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def add(p, q):
    return (p[0] + q[0], p[1] + q[1])


def bulge_of(c, p1, p2):
    """以 c 为圆心、由 p1 到 p2 的劣弧对应的 bulge 值."""
    a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
    a2 = math.atan2(p2[1] - c[1], p2[0] - c[0])
    sw = a2 - a1
    while sw > math.pi:
        sw -= 2 * math.pi
    while sw <= -math.pi:
        sw += 2 * math.pi
    return math.tan(sw / 4)


def tol(upper, lower):
    """MTEXT 堆叠公差 (上偏差^下偏差)."""
    return r"\H0.7x;\S%s^ %s;\H1.4286x;" % (upper, lower)


def wavy(p1, p2, amp, waves):
    """波浪线 (两端点在 p1/p2 上)."""
    n = max(int(waves * 12), 12)
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    L = math.hypot(dx, dy)
    nx, ny = -dy / L, dx / L
    pts = []
    for i in range(n + 1):
        t = i / n
        o = amp * math.sin(2 * math.pi * waves * t)
        pts.append((p1[0] + dx * t + nx * o, p1[1] + dy * t + ny * o))
    return pts


def wavy_arc(c, r, a1, a2, amp, waves):
    n = max(int(waves * 12), 12)
    pts = []
    for i in range(n + 1):
        t = i / n
        a = a1 + (a2 - a1) * t
        rr = r + amp * math.sin(2 * math.pi * waves * t)
        pts.append((c[0] + rr * math.cos(a), c[1] + rr * math.sin(a)))
    return pts


def sample_bulge_polyline(verts, closed=False, max_step=0.2):
    """把 (x, y, bulge) 多段线离散成稠密点列 (用于几何计算)."""
    pts = []
    n = len(verts)
    segs = n if closed else n - 1
    for i in range(segs):
        x1, y1, b = verts[i][0], verts[i][1], verts[i][2] if len(verts[i]) > 2 else 0.0
        x2, y2 = verts[(i + 1) % n][0], verts[(i + 1) % n][1]
        chord = math.hypot(x2 - x1, y2 - y1)
        if abs(b) < 1e-12 or chord < 1e-12:
            m = max(1, int(chord / max_step))
            pts += [(x1 + (x2 - x1) * k / m, y1 + (y2 - y1) * k / m) for k in range(m)]
            continue
        sweep = 4 * math.atan(b)
        r = chord / (2 * math.sin(abs(sweep) / 2))
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        d = math.sqrt(max(r * r - (chord / 2) ** 2, 0.0))
        ux, uy = (x2 - x1) / chord, (y2 - y1) / chord
        sgn = 1 if (sweep > 0) == (abs(sweep) < math.pi) else -1
        cx, cy = mx - uy * d * sgn, my + ux * d * sgn
        a1 = math.atan2(y1 - cy, x1 - cx)
        m = max(2, int(abs(sweep) * r / max_step))
        pts += [(cx + r * math.cos(a1 + sweep * k / m), cy + r * math.sin(a1 + sweep * k / m))
                for k in range(m)]
    if not closed:
        pts.append((verts[-1][0], verts[-1][1]))
    return pts


# ---------------------------------------------------------------- 图纸对象
class Sheet:
    """一张 GB 图纸. K: 图纸 mm -> 模型单位 (比例 1:K 时图框放大 K 倍)."""

    def __init__(self, K, txt=3.5):
        self.K = K
        self.TXT = txt
        doc = ezdxf.new("R2010", setup=True, units=4)
        doc.header["$MEASUREMENT"] = 1
        doc.header["$LTSCALE"] = 1.0
        doc.header["$PSLTSCALE"] = 0
        s = K / 2.0   # 线型按图纸长度缩放 (K=2 时: 长划 12mm)
        doc.linetypes.add("GB_CENTER", pattern=[33.0 * s, 24.0 * s, -4.0 * s, 1.0 * s, -4.0 * s],
                          description="GB 细点画线 ____ . ____")
        doc.linetypes.add("GB_PHANTOM",
                          pattern=[38.0 * s, 24.0 * s, -4.0 * s, 1.0 * s, -4.0 * s, 1.0 * s, -4.0 * s],
                          description="GB 细双点画线 ____ . . ____")
        for name, a in LAYERS.items():
            doc.layers.add(name, color=a["color"], linetype=a["linetype"],
                           lineweight=a["lineweight"])
        doc.styles.add("HZ", font=FONT_FILE).dxf.width = 0.7
        ds = doc.dimstyles.new("GB")
        for k, v in dict(
            dimtxsty="HZ", dimtxt=txt, dimasz=3.0, dimscale=K, dimtad=1, dimdec=3,
            dimzin=8, dimtzin=8, dimtdec=3, dimexo=0.0, dimexe=2.0, dimgap=0.8,
            dimdsep=ord("."), dimtih=0, dimtoh=0, dimtmove=0, dimclrd=3, dimclre=3,
            dimclrt=7, dimlwd=25, dimlwe=25,
        ).items():
            ds.dxf.set(k, v)
        self.doc = doc
        self.msp = doc.modelspace()

    # ------------------------------------------------ 基本图元
    def P(self, x, y):
        """图纸坐标(mm) -> 模型坐标."""
        return (x * self.K, y * self.K)

    def pline(self, pts, layer, closed=False):
        """pts: [(x, y) | (x, y, bulge)]"""
        pts = [(p[0], p[1], 0, 0, p[2] if len(p) > 2 else 0) for p in pts]
        return self.msp.add_lwpolyline(pts, format="xyseb", close=closed,
                                       dxfattribs={"layer": layer})

    def line(self, p1, p2, layer):
        return self.msp.add_line(p1, p2, dxfattribs={"layer": layer})

    def circle(self, c, r, layer):
        return self.msp.add_circle(c, r, dxfattribs={"layer": layer})

    def arc(self, c, r, a1_deg, a2_deg, layer):
        return self.msp.add_arc(c, r, a1_deg, a2_deg, dxfattribs={"layer": layer})

    def text(self, pos, s, h=None, align=TextEntityAlignment.MIDDLE_CENTER, rot_deg=0.0,
             layer="文字", width=0.7):
        """pos 为模型坐标, h 为图纸字高."""
        h = self.TXT if h is None else h
        t = self.msp.add_text(s, height=h * self.K, rotation=rot_deg,
                              dxfattribs={"style": "HZ", "layer": layer, "width": width})
        t.set_placement(pos, align=align)
        return t

    def mtext(self, pos, s, h=None, attach=MTextEntityAlignment.MIDDLE_CENTER, rot_deg=0.0,
              layer="文字"):
        h = self.TXT if h is None else h
        m = self.msp.add_mtext(s, dxfattribs={"style": "HZ", "layer": layer,
                                              "char_height": h * self.K, "rotation": rot_deg})
        m.set_location(pos, attachment_point=attach)
        return m

    def hatch(self, region, layer="剖面线", scale=None):
        """ANSI31 剖面线 (45°, 图纸间距约 3mm)."""
        h = self.msp.add_hatch(dxfattribs={"layer": layer})
        h.set_pattern_fill("ANSI31", scale=self.K if scale is None else scale)
        h.paths.add_polyline_path([(p[0], p[1], p[2] if len(p) > 2 else 0) for p in region],
                                  is_closed=True)
        return h

    # ------------------------------------------------ 标注
    def arrow(self, tip, direction, layer="尺寸", size=3.0):
        """实心箭头 (图纸长度 size, 指向 direction)."""
        L = size * self.K
        d = math.hypot(*direction)
        ux, uy = direction[0] / d, direction[1] / d
        w = L / 6
        base = (tip[0] - ux * L, tip[1] - uy * L)
        p1 = (base[0] - uy * w, base[1] + ux * w)
        p2 = (base[0] + uy * w, base[1] - ux * w)
        self.msp.add_solid([tip, p1, p2], dxfattribs={"layer": layer})

    def leader_note(self, tip, knee, s, side=1, h=None, with_arrow=True, layer="尺寸"):
        """引线 + 水平折线 + 文字 (文字写在折线上方). side=+1 向右, -1 向左."""
        h = self.TXT if h is None else h
        if with_arrow:
            self.arrow(tip, (tip[0] - knee[0], tip[1] - knee[1]))
        self.line(tip, knee, layer)
        w = (len(s) * 0.62 + 1.0) * h * self.K
        end = (knee[0] + side * w, knee[1])
        self.line(knee, end, layer)
        mid = ((knee[0] + end[0]) / 2, knee[1] + 0.8 * self.K)
        self.mtext(mid, s, h, attach=MTextEntityAlignment.BOTTOM_CENTER)

    def roughness(self, tip, axis_deg, value, h=None):
        """GB/T 131 表面粗糙度符号 (去除材料), 尖端在 tip, 符号轴向 axis_deg."""
        h = self.TXT if h is None else h
        a = math.radians(axis_deg - 90)
        s = self.K
        h1, h2 = 1.4 * h, 2.6 * h
        t30 = math.tan(math.radians(30))
        loc = [(0, 0), (-h1 * t30, h1), (h1 * t30, h1), (h2 * t30, h2)]
        g = [add(tip, rot((x * s, y * s), a)) for x, y in loc]
        self.line(g[0], g[1], "细实线")
        self.line(g[1], g[2], "细实线")
        self.line(g[0], g[3], "细实线")
        tpos = add(tip, rot((0.45 * h1 * t30 * s, (h1 + 0.6) * s), a))
        t = self.msp.add_text(value, height=h * self.K, rotation=math.degrees(a),
                              dxfattribs={"style": "HZ", "layer": "文字", "width": 0.7})
        t.set_placement(tpos, align=TextEntityAlignment.BOTTOM_RIGHT)

    def roughness_leader(self, tip, knee, value, side=1, h=None):
        """带引出线的粗糙度符号 (用于朝右/朝下的表面)."""
        self.arrow(tip, (tip[0] - knee[0], tip[1] - knee[1]))
        self.line(tip, knee, "尺寸")
        end = (knee[0] + side * 10 * self.K, knee[1])
        self.line(knee, end, "尺寸")
        self.roughness(((knee[0] + end[0]) / 2, knee[1]), 90, value, h)

    def lin_dim(self, p1, p2, base, angle, text_str, location=None):
        d = self.msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dimstyle="GB",
                                    text=text_str, location=location,
                                    dxfattribs={"layer": "尺寸"})
        d.render()
        return d

    def datum(self, foot, direction, letter, h=None):
        """GB/T 1182 基准符号: 实心三角形底边在 foot 处, 沿 direction 引出到方框."""
        h = self.TXT if h is None else h
        K = self.K
        d = math.hypot(*direction)
        ux, uy = direction[0] / d, direction[1] / d
        tw, th, gap, box = 1.3 * K, 2.0 * K, 3.0 * K, 6.0 * K
        p1 = (foot[0] - uy * tw, foot[1] + ux * tw)
        p2 = (foot[0] + uy * tw, foot[1] - ux * tw)
        apex = (foot[0] + ux * th, foot[1] + uy * th)
        self.msp.add_solid([p1, p2, apex], dxfattribs={"layer": "尺寸"})
        bc = (apex[0] + ux * (gap + box / 2), apex[1] + uy * (gap + box / 2))
        self.line(apex, (bc[0] - ux * box / 2, bc[1] - uy * box / 2), "尺寸")
        hb = box / 2
        self.pline([(bc[0] - hb, bc[1] - hb), (bc[0] + hb, bc[1] - hb),
                    (bc[0] + hb, bc[1] + hb), (bc[0] - hb, bc[1] + hb)], "尺寸", closed=True)
        self.text(bc, letter, h)

    def gdt_frame(self, origin, cells, h=None, cell_w=None):
        """形位公差框格. origin 为左下角 (模型坐标); cells: [(文字, 图纸宽度), ...].
        返回 (左端中点, 右端中点)."""
        h = self.TXT if h is None else h
        K = self.K
        H = (h + 2.5) * K
        x = origin[0]
        for s, w in cells:
            w *= K
            self.pline([(x, origin[1]), (x + w, origin[1]), (x + w, origin[1] + H),
                        (x, origin[1] + H)], "尺寸", closed=True)
            cx, cy = x + w / 2, origin[1] + H / 2
            g = h * K / 2
            if s == "PERP":        # 垂直度 ⊥
                self.line((cx - g, cy - g), (cx + g, cy - g), "尺寸")
                self.line((cx, cy - g), (cx, cy + g), "尺寸")
            elif s == "RUNOUT":    # 圆跳动 ↗
                tip = (cx + g * 0.8, cy + g * 0.8)
                self.line((cx - g * 0.8, cy - g * 0.8), tip, "尺寸")
                self.arrow(tip, (1, 1), size=h * 0.6)
            else:
                self.text((cx, cy), s, h)
            x += w
        return (origin[0], origin[1] + H / 2), (x, origin[1] + H / 2)

    def image(self, filename, insert, size, px_size):
        """插入外部光栅图片 (filename 相对 DXF 所在目录)."""
        idef = self.doc.add_image_def(filename=filename, size_in_pixel=px_size)
        img = self.msp.add_image(idef, insert=insert, size_in_units=size,
                                 dxfattribs={"layer": "图片"})
        img.dxf.flags = img.SHOW_IMAGE | img.USE_TRANSPARENCY
        return img

    def table(self, xs, ys, cells, h=3.5):
        """表格. xs/ys: 列/行分隔线 (图纸坐标, ys 自上而下);
        cells: [(行起, 行止, 列起, 列止, 文字), ...] (止为开区间). 文字支持 MTEXT 格式."""
        P = self.P
        self.pline([P(xs[0], ys[0]), P(xs[-1], ys[0]), P(xs[-1], ys[-1]), P(xs[0], ys[-1])],
                   "图框", closed=True)
        for r0, r1, c0, c1, s in cells:
            x0, x1, y0, y1 = xs[c0], xs[c1], ys[r0], ys[r1]
            if c1 < len(xs) - 1:
                self.line(P(x1, y0), P(x1, y1), "图框细")
            if r1 < len(ys) - 1:
                self.line(P(x0, y1), P(x1, y1), "图框细")
            if s:
                hh = h if isinstance(h, (int, float)) else h(r0, c0)
                self.mtext(P((x0 + x1) / 2, (y0 + y1) / 2), s, hh)

    # ------------------------------------------------ 输出
    def save(self, path):
        self.doc.saveas(path)

    def render_preview(self, out_base, paper_w, paper_h, dpi=300):
        """用开源字体渲染 PNG/PDF 预览 (DXF 本身保持仿宋)."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        from ezdxf.addons.drawing.config import (BackgroundPolicy, ColorPolicy,
                                                 Configuration, ImagePolicy)

        style = self.doc.styles.get("HZ")
        style.dxf.font = PREVIEW_FONT
        try:
            fig = plt.figure(figsize=(paper_w / 25.4, paper_h / 25.4))
            ax = fig.add_axes((0, 0, 1, 1))
            ax.set_axis_off()
            cfg = Configuration(color_policy=ColorPolicy.BLACK,
                                background_policy=BackgroundPolicy.WHITE,
                                image_policy=ImagePolicy.DISPLAY)
            Frontend(RenderContext(self.doc), MatplotlibBackend(ax), config=cfg).draw_layout(
                self.msp, finalize=True)
            ax.set_xlim(0, paper_w * self.K)
            ax.set_ylim(0, paper_h * self.K)
            ax.set_aspect("equal")
            fig.savefig(out_base + ".png", dpi=dpi, facecolor="white")
            fig.savefig(out_base + ".pdf", facecolor="white")
            plt.close(fig)
        finally:
            style.dxf.font = FONT_FILE
