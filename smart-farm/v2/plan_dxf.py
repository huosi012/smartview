"""Editable CAD version (DXF, millimetres) of the 2D site plan in plan2d.py.

    python plan_dxf.py            ->  renders/plan2d.dxf  (+ renders/plan2d_dxf_preview.png)

Origin (0, 0) = corner of the kerb line and the corridor parapet's terrace face.
+X runs along the terrace towards the red wall, +Y from the corridor towards the street.
Everything is on named layers so the site can be edited and sent back as DXF.
"""
import os
import sys

import ezdxf
from ezdxf.enums import TextEntityAlignment

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from plan2d import ALC, COLS, CW, DOOR, L, PHASE1_X, PIER, W  # noqa: E402

OUT = os.path.join(HERE, "renders", "plan2d.dxf")
MM = 1000.0

LAYERS = {
    # name: (ACI colour, linetype)
    "01-露台范围": (8, "CONTINUOUS"),
    "02-原有墙体栏板": (7, "CONTINUOUS"),
    "03-走廊柱": (7, "CONTINUOUS"),
    "04-走廊": (9, "CONTINUOUS"),
    "05-百叶格栅": (30, "CONTINUOUS"),
    "06-红色楼体": (1, "CONTINUOUS"),
    "07-天井(未测)": (1, "DASHED"),
    "08-抬高平台": (8, "CONTINUOUS"),
    "09-教室": (8, "CONTINUOUS"),
    "10-展厅玻璃": (4, "CONTINUOUS"),
    "11-入口门": (30, "CONTINUOUS"),
    "12-展厅布置": (3, "CONTINUOUS"),
    "13-一期分界线": (30, "DASHED"),
    "14-尺寸": (5, "CONTINUOUS"),
    "15-文字": (7, "CONTINUOUS"),
    "16-待确认": (6, "CONTINUOUS"),
    "17-标识": (3, "CONTINUOUS"),
}


def m(v):
    return v * MM


class Plan:
    def __init__(self):
        self.doc = ezdxf.new("R2010", setup=True, units=ezdxf.units.MM)
        self.doc.header["$INSUNITS"] = 4
        self.doc.header["$MEASUREMENT"] = 1
        self.doc.styles.add("CN", font="simsun.ttc")
        for name, (col, lt) in LAYERS.items():
            self.doc.layers.add(name, color=col, linetype=lt)
        self.doc.header["$LTSCALE"] = 20
        self.msp = self.doc.modelspace()

    def rect(self, layer, x0, y0, x1, y1, hatch=None, closed=True):
        pts = [(m(x0), m(y0)), (m(x1), m(y0)), (m(x1), m(y1)), (m(x0), m(y1))]
        self.msp.add_lwpolyline(pts, close=closed, dxfattribs={"layer": layer})
        if hatch:
            h = self.msp.add_hatch(dxfattribs={"layer": layer})
            if hatch == "SOLID":
                h.set_solid_fill()
            else:
                h.set_pattern_fill(hatch, scale=hatch_scale(hatch))
            h.paths.add_polyline_path(pts, is_closed=True)

    def line(self, layer, a, b):
        self.msp.add_line((m(a[0]), m(a[1])), (m(b[0]), m(b[1])), dxfattribs={"layer": layer})

    def circle(self, layer, c, r):
        self.msp.add_circle((m(c[0]), m(c[1])), m(r), dxfattribs={"layer": layer})

    def text(self, layer, s, at, h=0.25, align=TextEntityAlignment.MIDDLE_CENTER, rot=0):
        t = self.msp.add_text(s, height=m(h), rotation=rot, dxfattribs={"layer": layer, "style": "CN"})
        t.set_placement((m(at[0]), m(at[1])), align=align)

    def dim(self, a, b, base, angle=0):
        d = self.msp.add_linear_dim(
            base=(m(base[0]), m(base[1])), p1=(m(a[0]), m(a[1])), p2=(m(b[0]), m(b[1])), angle=angle,
            dimstyle="EZDXF", override={"dimtxsty": "CN", "dimscale": 1, "dimtxt": 220, "dimasz": 120, "dimexe": 100,
                      "dimexo": 60, "dimgap": 60, "dimdec": 0, "dimclrt": 5, "dimtsz": 0, "dimlfac": 1},
            dxfattribs={"layer": "14-尺寸"})
        d.render()


def hatch_scale(p):
    return {"ANSI31": 40.0, "ANSI37": 40.0, "DOTS": 40.0}.get(p, 40.0)


def main():
    P = Plan()
    CORR = -0.25 - CW                       # corridor inner wall line (classroom side)

    # terrace (= hall footprint) and raised platform
    P.rect("01-露台范围", 0.0, 0.0, L, W)
    P.rect("08-抬高平台", -3.0, -0.25, 0.0, W + 0.25, hatch="ANSI37")
    P.text("15-文字", "抬高平台（高出露台约0.9m）", (-1.5, 4.25), 0.22, rot=90)
    P.text("15-文字", "坎", (-0.15, W + 0.55), 0.22)

    # existing walls: corridor parapet (door gap), street parapet
    P.rect("02-原有墙体栏板", -3.0, -0.25, DOOR[0], 0.0, hatch="ANSI31")
    P.rect("02-原有墙体栏板", DOOR[1], -0.25, PIER - 0.25, 0.0, hatch="ANSI31")
    P.rect("02-原有墙体栏板", -3.0, W, L, W + 0.25, hatch="ANSI31")
    P.text("15-文字", "沿街围墙（保留原宣传栏）", (L / 2, W + 0.6), 0.25)
    P.text("15-文字", "走廊栏板（原不锈钢栏杆保留，外侧加玻璃封闭）", (3.4, -0.5), 0.18)

    # corridor columns + end pier
    for cx in COLS + [PIER]:
        P.rect("03-走廊柱", cx - 0.25, -0.55, cx + 0.25, 0.0, hatch="SOLID")
        P.text("16-待确认", f"柱≈{cx * 1000:.0f}(待量)", (cx, -0.8), 0.13)

    # corridor + classrooms
    P.line("04-走廊", (-3.0, CORR), (L + ALC + 0.25, CORR))
    P.text("15-文字", "教学楼走廊（净宽约2600，待量）", (4.0, -1.6), 0.28)
    P.rect("09-教室", -3.0, CORR - 0.3, L + ALC + 0.25, CORR, hatch="ANSI31")
    P.text("15-文字", "教室", (1.8, CORR - 0.55), 0.3)

    # louver alcove at the corridor end (side + end louvers)
    ax0, ax1 = PIER + 0.25, L + ALC
    x = ax0
    while x < ax1 - 0.01:
        P.rect("05-百叶格栅", x, -0.25, min(ax1, x + 0.12), 0.0, hatch="SOLID")
        x += 0.3
    y = CORR
    while y < -0.25 - 0.01:
        P.rect("05-百叶格栅", ax1, y, ax1 + 0.25, min(-0.25, y + 0.12), hatch="SOLID")
        y += 0.3
    P.text("15-文字", "百叶格栅段", ((ax0 + ax1) / 2, -1.2), 0.22)
    P.text("15-文字", "外封玻璃+灯带+盆栽观察", ((ax0 + ax1) / 2, -1.55), 0.12)
    P.text("16-待确认", "长≈2400(待量)", ((ax0 + ax1) / 2, -1.85), 0.13)

    # red block + light well (light-well shape is a guess)
    pts = [(L, 1.4), (L + ALC + 0.3, 1.4), (L + ALC + 0.3, 0.0), (L + 5.5, 0.0), (L + 5.5, W + 2.0), (L, W + 2.0)]
    pts_mm = [(m(a), m(b)) for a, b in pts]
    P.msp.add_lwpolyline(pts_mm, close=True, dxfattribs={"layer": "06-红色楼体"})
    h = P.msp.add_hatch(dxfattribs={"layer": "06-红色楼体"})
    h.set_pattern_fill("ANSI31", scale=60)
    h.paths.add_polyline_path(pts_mm, is_closed=True)
    P.text("15-文字", "红色楼体（红墙）", (L + 2.8, 5.0), 0.35)
    P.rect("07-天井(未测)", L, 0.0, L + ALC + 0.3, 1.4)
    P.text("16-待确认", "天井（形状未测）", (L + 1.35, 0.7), 0.15)

    # hall glazing
    P.line("10-展厅玻璃", (0.0, 0.06), (DOOR[0], 0.06))
    P.line("10-展厅玻璃", (DOOR[1], 0.06), (PIER - 0.25, 0.06))
    P.line("10-展厅玻璃", (0.03, 0.0), (0.03, W))
    P.line("10-展厅玻璃", (0.0, W - 0.06), (L, W - 0.06))
    for i in range(17):
        xx = i * L / 16
        P.line("10-展厅玻璃", (xx, W - 0.16), (xx, W))
    P.text("15-文字", "沿街推拉玻璃窗", (15.0, W - 0.3), 0.15)
    P.text("15-文字", "坎边端墙：钢化玻璃", (0.35, 2.2), 0.15, rot=90)

    # entrance: double door, swing into the hall
    half = (DOOR[1] - DOOR[0]) / 2
    for hinge, a0, a1, leaf_end in ((DOOR[0], 0, 90, (DOOR[0], half)), (DOOR[1], 90, 180, (DOOR[1], half))):
        P.msp.add_arc((m(hinge), 0), m(half), a0, a1, dxfattribs={"layer": "11-入口门"})
        P.line("11-入口门", (hinge, 0.0), leaf_end)
    P.text("15-文字", "入口（双开玻璃门1500）", ((DOOR[0] + DOOR[1]) / 2 - 0.1, -1.35), 0.15)
    P.rect("11-入口门", DOOR[0], 0.0, DOOR[1], 2.2)
    P.text("15-文字", "入口通道", ((DOOR[0] + DOOR[1]) / 2, 1.5), 0.15)

    # signage in the corridor
    P.rect("17-标识", DOOR[0] - 0.9, -0.8, DOOR[0] - 0.3, -0.7, hatch="SOLID")
    P.text("15-文字", "入口立牌", (DOOR[0] - 0.6, -1.0), 0.12)

    # interior layout (same positions as scene_v2.py)
    lay = "12-展厅布置"
    P.rect(lay, 0.03, 0.4, 0.42, W - 0.4)
    P.text("15-文字", "种子萌发观察窗（与坎齐平）", (0.6, W / 2 + 1.0), 0.15, rot=90)
    for a, b in ((1.2, 3.6), (3.9, 6.3), (6.6, 9.0), (9.3, 11.7)):
        P.rect(lay, a, 0.35, b, 0.95)
        P.text("15-文字", "立体水培架", ((a + b) / 2, 0.65), 0.15)
    grades = ["一年级", "二年级", "三年级", "四年级", "五年级", "六年级", "一年级", "二年级"]
    for k in range(8):
        a = 1.0 + k * 1.65
        P.rect(lay, a, 7.35, a + 1.4, 8.25)
        P.text("15-文字", f"{grades[k]}种植箱", (a + 0.7, 7.8), 0.13)
    for (cx, cy) in [(2.2, 3.1), (3.2, 3.1), (2.2, 5.4), (3.2, 5.4), (12.75, 3.0), (12.75, 5.5)]:
        P.circle(lay, (cx, cy), 0.28)
    P.text("15-文字", "气雾栽培塔", (2.7, 4.25), 0.15)
    P.rect(lay, 5.2, 3.85, 7.0, 4.65)
    P.text("15-文字", "鱼菜共生缸", (6.1, 4.25), 0.15)
    for y0, y1 in ((2.6, 3.5), (5.0, 5.9)):
        P.rect(lay, 9.6, y0, 11.6, y1)
        P.text("15-文字", "研学操作台", (10.6, (y0 + y1) / 2), 0.15)
        for sx in (9.95, 10.6, 11.25):
            for sy in (y0 - 0.32, y1 + 0.32):
                P.circle(lay, (sx, sy), 0.17)
    for sx in (14.0, 14.75, 15.5, 16.25):
        for sy in (2.75, 3.55, 4.35, 5.15, 5.95):
            P.circle(lay, (sx, sy), 0.18)
    P.text("15-文字", "科普讲解区（20座）", (15.1, 6.55), 0.18)
    P.rect(lay, L - 0.3, 0.3, L - 0.02, 8.2)
    P.rect(lay, L - 0.36, 3.38, L - 0.3, 5.12, hatch="SOLID")
    P.text("15-文字", "红墙展示墙：大屏·时间轴·照片墙·植物墙", (L - 0.55, 4.25), 0.15, rot=90)
    P.rect(lay, 12.0, 0.35, 13.2, 0.84)
    P.text("15-文字", "育苗架", (12.6, 1.05), 0.13)
    P.rect(lay, 16.9, 7.45, 17.5, 8.25)
    P.circle(lay, (16.4, 7.85), 0.25)
    P.text("15-文字", "水肥一体机", (16.95, 7.15), 0.13)

    # phase line
    P.line("13-一期分界线", (PHASE1_X, -0.1), (PHASE1_X, W + 0.1))
    P.text("13-一期分界线", "← 二期≈100㎡ | 一期 6000×8500≈51㎡ →", (PHASE1_X, W - 1.3), 0.18)

    # roof slope note
    P.line("15-文字", (8.6, 1.8), (8.6, 6.6))
    P.msp.add_solid([(m(8.6), m(6.8)), (m(8.5), m(6.5)), (m(8.7), m(6.5))], dxfattribs={"layer": "15-文字"})
    P.text("15-文字", "单坡屋面：走廊侧高≈3350 → 沿街侧低≈2600", (8.9, 4.25), 0.15, rot=90)

    # dimensions
    P.dim((0.0, W), (L, W), (0.0, W + 1.3))
    P.dim((0.0, 0.0), (0.0, W), (-3.6, 0.0), angle=90)
    P.dim((0.0, -0.25), (COLS[0], -0.25), (0.0, CORR - 0.9))
    P.dim((COLS[0], -0.25), (COLS[1], -0.25), (0.0, CORR - 0.9))
    P.dim((COLS[1], -0.25), (PIER, -0.25), (0.0, CORR - 0.9))
    P.dim((DOOR[0], 0.0), (DOOR[1], 0.0), (0.0, CORR - 1.6))
    P.dim((PIER, -0.25), (ax1, -0.25), (0.0, CORR - 1.6))
    P.dim((L + ALC + 0.6, -0.25), (L + ALC + 0.6, CORR), (L + ALC + 1.1, 0.0), angle=90)

    # title + notes
    P.text("15-文字", "智慧农业科普展厅  二维平面（现场关系确认稿，可编辑）", (-3.6, W + 2.6), 0.5,
           align=TextEntityAlignment.LEFT)
    notes = ["单位：毫米。原点＝坎线与走廊栏板（露台侧面）交点。",
             "图层“16-待确认”内为按照片估计、需要现场测量的尺寸。",
             "改完请另存为 DXF 发回，按此更新三维模型与效果图。"]
    for i, s in enumerate(notes):
        P.text("16-待确认", s, (-3.6, CORR - 2.6 - i * 0.4), 0.2, align=TextEntityAlignment.LEFT)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    P.doc.saveas(OUT, encoding="utf-8")
    print("saved", OUT)
    return P.doc


def preview(doc, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    doc.styles.get("CN").dxf.font = "wqy-zenhei.ttc"          # preview only: this machine has no SimSun
    fig = plt.figure()
    ax = fig.add_axes([0, 0, 1, 1])
    ctx = RenderContext(doc)
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.COLOR,
                        min_lineweight=0.4)
    Frontend(ctx, MatplotlibBackend(ax), config=cfg).draw_layout(doc.modelspace(), finalize=True)
    fig.set_size_inches(32, 18)
    fig.savefig(path, dpi=110, facecolor="white")
    print("preview", path)


if __name__ == "__main__":
    d = main()
    if "--preview" in sys.argv:
        preview(d, os.path.join(HERE, "renders", "plan2d_dxf_preview.png"))
