"""
生成 链轮 2292-IH-000139 内花键图纸 (JIS D2001, m2.5 z85 α20° x+0.8) —— DXF + 预览图.

约定:
  * 模型空间 1:1 绘制主视图/左视图 (图纸比例 1:2), 图框按 K=2 放大;
  * B-B 局部剖视图图纸比例 5:1, 在模型空间中按 5*K = 10 倍绘制;
  * 所有尺寸数值使用替代文字, 以保证放大视图中标注真实尺寸.

运行:  python3 make_internal_spline.py
输出:  2292-IH-000139_内花键_JISD2001.dxf / .png / .pdf
"""
import math
import os
import sys

import ezdxf
from ezdxf.enums import TextEntityAlignment, MTextEntityAlignment

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spline_geom import (  # noqa: E402
    M_MOD, Z, ALPHA, X, D_PITCH, D_BASE, D_MAJOR, D_MINOR, R_MAJOR, R_MINOR,
    R_BASE, E_PITCH, S_BASE, PIN_D, psi, pin_measurement, half_space_profile,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_BASE = os.path.join(HERE, "2292-IH-000139_内花键_JISD2001")

K = 2.0  # 图纸 mm -> 模型单位 (主视图比例 1:2)
TXT = 3.5  # 图纸字高 (mm)

# ---------------------------------------------------------------- 文档设置
doc = ezdxf.new("R2010", setup=True, units=4)
doc.header["$MEASUREMENT"] = 1
doc.header["$LTSCALE"] = 1.0
doc.header["$PSLTSCALE"] = 0
msp = doc.modelspace()

doc.linetypes.add("GB_CENTER", pattern=[33.0, 24.0, -4.0, 1.0, -4.0],
                  description="GB 细点画线 ____ . ____")
doc.linetypes.add("GB_PHANTOM", pattern=[38.0, 24.0, -4.0, 1.0, -4.0, 1.0, -4.0],
                  description="GB 细双点画线 ____ . . ____")

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
}
for name, a in LAYERS.items():
    doc.layers.add(name, color=a["color"], linetype=a["linetype"], lineweight=a["lineweight"])

# 字体: 长仿宋 (simfang.ttf, 宽度因子 0.7)
FONT_FILE = "simfang.ttf"
doc.styles.add("HZ", font=FONT_FILE).dxf.width = 0.7

ds = doc.dimstyles.new("GB")
for k, v in dict(
    dimtxsty="HZ", dimtxt=TXT, dimasz=3.0, dimscale=K, dimtad=1, dimdec=3,
    dimzin=8, dimtzin=8, dimtdec=3, dimexo=0.0, dimexe=2.0, dimgap=0.8,
    dimdsep=ord("."), dimtih=0, dimtoh=0, dimtmove=0, dimclrd=3, dimclre=3,
    dimclrt=7, dimlwd=25, dimlwe=25,
).items():
    ds.dxf.set(k, v)


# ---------------------------------------------------------------- 工具函数
def P(x, y):
    """图纸坐标(mm) -> 模型坐标."""
    return (x * K, y * K)


def rot(p, a):
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def add(p, q):
    return (p[0] + q[0], p[1] + q[1])


def bulge_of(c, p1, p2):
    a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
    a2 = math.atan2(p2[1] - c[1], p2[0] - c[0])
    sw = a2 - a1
    while sw > math.pi:
        sw -= 2 * math.pi
    while sw <= -math.pi:
        sw += 2 * math.pi
    return math.tan(sw / 4)


def pline(pts, layer, closed=False):
    """pts: [(x, y) | (x, y, bulge)]"""
    pts = [(p[0], p[1], 0, 0, p[2] if len(p) > 2 else 0) for p in pts]
    return msp.add_lwpolyline(pts, format="xyseb", close=closed, dxfattribs={"layer": layer})


def line(p1, p2, layer):
    return msp.add_line(p1, p2, dxfattribs={"layer": layer})


def circle(c, r, layer):
    return msp.add_circle(c, r, dxfattribs={"layer": layer})


def text(pos, s, h=TXT, align=TextEntityAlignment.MIDDLE_CENTER, rot_deg=0.0,
         layer="文字", width=0.7):
    """pos 为模型坐标, h 为图纸字高."""
    t = msp.add_text(s, height=h * K, rotation=rot_deg,
                     dxfattribs={"style": "HZ", "layer": layer, "width": width})
    t.set_placement(pos, align=align)
    return t


def mtext(pos, s, h=TXT, attach=MTextEntityAlignment.MIDDLE_CENTER, rot_deg=0.0,
          layer="文字"):
    m = msp.add_mtext(s, dxfattribs={"style": "HZ", "layer": layer,
                                     "char_height": h * K, "rotation": rot_deg})
    m.set_location(pos, attachment_point=attach)
    return m


def tol(upper, lower):
    """MTEXT 堆叠公差 (上偏差^下偏差)."""
    return r"\H0.7x;\S%s^ %s;\H1.4286x;" % (upper, lower)


def arrow(tip, direction, layer="尺寸", size=3.0):
    """实心箭头 (图纸长度 size, 指向 direction)."""
    L = size * K
    d = math.hypot(*direction)
    ux, uy = direction[0] / d, direction[1] / d
    w = L / 6
    base = (tip[0] - ux * L, tip[1] - uy * L)
    p1 = (base[0] - uy * w, base[1] + ux * w)
    p2 = (base[0] + uy * w, base[1] - ux * w)
    msp.add_solid([tip, p1, p2], dxfattribs={"layer": layer})


def leader_note(tip, knee, s, side=1, h=TXT, with_arrow=True, layer="尺寸"):
    """引线 + 水平折线 + 文字 (文字写在折线上方). side=+1 向右, -1 向左."""
    if with_arrow:
        arrow(tip, (tip[0] - knee[0], tip[1] - knee[1]))
    line(tip, knee, layer)
    w = (len(s) * 0.62 + 1.0) * h * K
    end = (knee[0] + side * w, knee[1])
    line(knee, end, layer)
    mid = ((knee[0] + end[0]) / 2, knee[1] + 0.8 * K)
    mtext(mid, s, h, attach=MTextEntityAlignment.BOTTOM_CENTER)


def roughness(tip, axis_deg, value, h=TXT):
    """GB/T 131 表面粗糙度符号 (去除材料), 尖端在 tip, 符号轴向 axis_deg."""
    a = math.radians(axis_deg - 90)
    s = K
    h1, h2 = 1.4 * h, 2.6 * h
    t30 = math.tan(math.radians(30))
    loc = [(0, 0), (-h1 * t30, h1), (h1 * t30, h1), (h2 * t30, h2)]
    g = [add(tip, rot((x * s, y * s), a)) for x, y in loc]
    line(g[0], g[1], "细实线")
    line(g[1], g[2], "细实线")
    line(g[0], g[3], "细实线")
    tpos = add(tip, rot((0.45 * h1 * t30 * s, (h1 + 0.6) * s), a))
    t = msp.add_text(value, height=h * K, rotation=math.degrees(a),
                     dxfattribs={"style": "HZ", "layer": "文字", "width": 0.7})
    t.set_placement(tpos, align=TextEntityAlignment.BOTTOM_RIGHT)


def roughness_leader(tip, knee, value, side=1, h=TXT):
    """带引出线的粗糙度符号 (用于朝右/朝下的表面)."""
    arrow(tip, (tip[0] - knee[0], tip[1] - knee[1]))
    line(tip, knee, "尺寸")
    end = (knee[0] + side * 10 * K, knee[1])
    line(knee, end, "尺寸")
    roughness(((knee[0] + end[0]) / 2, knee[1]), 90, value, h)


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


def lin_dim(p1, p2, base, angle, text_str, location=None):
    d = msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dimstyle="GB",
                           text=text_str, location=location,
                           dxfattribs={"layer": "尺寸"})
    d.render()
    return d


# ---------------------------------------------------------------- 花键齿形
HP = half_space_profile()
TIP_T = HP["tip_theta"]
R_CH = HP["chamfer_r"]
R_FL = HP["fillet_r"]
FC = HP["fillet_center"]
TH_R = HP["root_theta"]
PITCH_ANG = 2 * math.pi / Z


def space_chain(phi, n_flank=10):
    """一个齿槽 (中心角 phi) 的轮廓顶点 (x, y, bulge), 逆时针."""
    def pol(r, t):
        return (r * math.cos(phi + t), r * math.sin(phi + t))

    def flank(r, side):
        return pol(r, side * psi(r))

    rs = [R_CH + (R_FL - R_CH) * i / n_flank for i in range(n_flank + 1)]
    v = [[*pol(R_MINOR, -TIP_T), 0.0]]
    for r in rs:
        v.append([*flank(r, -1), 0.0])
    c_minus = rot((FC[0], -FC[1]), phi)
    p2 = pol(R_MAJOR, -TH_R)
    v[-1][2] = bulge_of(c_minus, v[-1][:2], p2)
    v.append([*p2, math.tan(2 * TH_R / 4)])
    p3 = pol(R_MAJOR, TH_R)
    c_plus = rot(FC, phi)
    v.append([*p3, bulge_of(c_plus, p3, flank(R_FL, +1))])
    for r in reversed(rs):
        v.append([*flank(r, +1), 0.0])
    v.append([*pol(R_MINOR, TIP_T), 0.0])
    return v


def full_profile():
    verts = []
    for k in range(Z):
        phi = math.pi / 2 + k * PITCH_ANG
        ch = space_chain(phi)
        ch[-1][2] = math.tan((PITCH_ANG - 2 * TIP_T) / 4)
        verts.extend(ch)
    return verts


def window_profile(ks, th_s, th_e):
    """齿槽 ks 范围内的开口轮廓, 起止于小径圆上角度 th_s / th_e."""
    phis = [math.pi / 2 + k * PITCH_ANG for k in ks]
    verts = [[R_MINOR * math.cos(th_s), R_MINOR * math.sin(th_s),
              math.tan(((phis[0] - TIP_T) - th_s) / 4)]]
    for i, phi in enumerate(phis):
        ch = space_chain(phi)
        if i + 1 < len(phis):
            ch[-1][2] = math.tan((PITCH_ANG - 2 * TIP_T) / 4)
        else:
            ch[-1][2] = math.tan((th_e - (phi + TIP_T)) / 4)
        verts.extend(ch)
    verts.append([R_MINOR * math.cos(th_e), R_MINOR * math.sin(th_e), 0.0])
    return verts


def xform(verts, s, off, ref=(0.0, 0.0)):
    return [((v[0] - ref[0]) * s + off[0], (v[1] - ref[1]) * s + off[1],
             v[2] if len(v) > 2 else 0.0) for v in verts]


# ================================================================ 图框
W, H = 420, 297
pline([P(0, 0), P(W, 0), P(W, H), P(0, H)], "图框细", closed=True)
pline([P(25, 10), P(410, 10), P(410, 287), P(25, 287)], "图框", closed=True)
for a, b in (((217.5, 0), (217.5, 10)), ((217.5, 287), (217.5, 297)),
             ((0, 148.5), (25, 148.5)), ((410, 148.5), (420, 148.5))):
    line(P(*a), P(*b), "图框")  # 对中符号


# ================================================================ 主视图 (全剖, 1:2)
SX0, SY0 = 124.0, 370.0   # 左端面与轴线交点 (模型坐标)


def S(x, y):
    return (SX0 + x, SY0 + y)


L_HUB = 110.5
X_P1 = L_HUB - 19.0 - 50.67   # 40.83 腹板左侧面
X_P2 = L_HUB - 19.0           # 91.5 腹板右侧面
RB = 178.0                    # 腹板断裂处
R_RLF = 111.0                 # 退刀槽 Ø222
X_RLF = L_HUB - 10.0          # 100.5
X_CH_R = X_RLF - 4.0          # 96.5 右侧 C4 倒角起点
Y_RIGHT_FILLET_END = 165.0 - math.sqrt(20.0 ** 2 - 1.0 ** 2)   # R20 与右端面交点

fl_l_c = (X_P1 - 20.0, 170.0)
fl_r_c = (X_P2 + 20.0, 165.0)
brk = wavy((X_P1, RB), (X_P2, RB), 1.2 * K, 1.5)

# 上半部轮廓 (除断裂线外), 由右侧断裂处起顺序走到左侧断裂处
upper = [
    (X_P2, RB, 0), (X_P2, 165.0, bulge_of(fl_r_c, (X_P2, 165.0), (L_HUB, Y_RIGHT_FILLET_END))),
    (L_HUB, Y_RIGHT_FILLET_END, 0), (L_HUB, R_RLF, 0), (X_RLF, R_RLF, 0),
    (X_RLF, R_MINOR + 4.0, 0), (X_CH_R, R_MINOR, 0), (4.0, R_MINOR, 0),
    (0.0, R_MINOR + 4.0, 0), (0.0, 145.0, 0), (10.0, 145.0, 0), (17.0, 150.0, 0),
    (X_P1 - 20.0, 150.0, bulge_of(fl_l_c, (X_P1 - 20.0, 150.0), (X_P1, 170.0))),
    (X_P1, 170.0, 0), (X_P1, RB, 0),
]


def mirror(vs):
    return [(v[0], -v[1], -v[2]) for v in vs]


for half in (1, -1):
    contour = upper if half > 0 else mirror(upper)
    wave = brk if half > 0 else [(x, -y) for x, y in brk]
    pline([(SX0 + v[0], SY0 + v[1], v[2]) for v in contour], "粗实线")
    pline([S(*p) for p in wave], "波浪线")
    # 剖面线区域 (轮廓 + 断裂线)
    region = [(SX0 + v[0], SY0 + v[1], v[2]) for v in contour]
    region += [(*S(*p), 0) for p in wave[1:-1]]
    hatch = msp.add_hatch(dxfattribs={"layer": "剖面线"})
    hatch.set_pattern_fill("ANSI31", scale=2.0)
    hatch.paths.add_polyline_path(region, is_closed=True)
    # 内花键大径线 (粗实线)
    y = half * R_MAJOR
    line(S(4.0 - (R_MAJOR - R_MINOR), y), S(X_CH_R + (R_MAJOR - R_MINOR), y), "粗实线")

# 孔内可见轮廓线 (倒角/台阶处的圆投影)
for x, r in ((0.0, R_MINOR + 4.0), (4.0, R_MINOR), (X_CH_R, R_MINOR),
             (X_RLF, R_MINOR + 4.0), (L_HUB, R_RLF)):
    line(S(x, -r), S(x, r), "粗实线")
line(S(X_RLF, R_MINOR + 4.0), S(X_RLF, R_RLF), "粗实线")
line(S(X_RLF, -R_MINOR - 4.0), S(X_RLF, -R_RLF), "粗实线")

# 轴线
line(S(-8.0, 0), S(L_HUB + 8.0, 0), "中心线")

# --- B-B 剖切符号 (x = 25)
XB = 25.0
for sgn in (1, -1):
    line(S(XB, sgn * 155.0), S(XB, sgn * 165.0), "粗实线")
    arrow(S(XB + 9.0, sgn * 165.0), (1, 0), "粗实线", size=3.0)
    line(S(XB, sgn * 165.0), S(XB + 9.0, sgn * 165.0), "细实线")
    text(S(XB + 13.0, sgn * 165.0), "B", 5)

# --- 尺寸
LIFT = (TXT / 2 + 0.8) * K   # 指定位置的尺寸文字抬高到尺寸线上方
lin_dim(S(4.0, -R_MINOR), S(4.0, R_MINOR), S(-16.0, 0), 90,
        r"%%c<>H7(" + tol("+0.046", "0") + ")")
lin_dim(S(0.0, -145.0), S(0.0, 145.0), S(-32.0, 0), 90, "%%c<>")
lin_dim(S(17.0, -150.0), S(17.0, 150.0), S(-46.0, 0), 90, "%%c<>")
lin_dim(S(X_CH_R + (R_MAJOR - R_MINOR), -R_MAJOR), S(X_CH_R + (R_MAJOR - R_MINOR), R_MAJOR),
        S(L_HUB + 14.0, 0), 90, r"%%c<>H11(" + tol("+0.29", "0") + ")")
lin_dim(S(L_HUB, -R_RLF), S(L_HUB, R_RLF), S(L_HUB + 28.0, 0), 90, "%%c<>")
lin_dim(S(0.0, 145.0), S(L_HUB, Y_RIGHT_FILLET_END), S(0, 189.0), 0,
        "<>" + r"\H0.7x;\S+0.1^ 0;")
lin_dim(S(X_P2, 172.0), S(L_HUB, Y_RIGHT_FILLET_END), S(0, 172.0), 0, "<>±0.1",
        location=S(L_HUB + 16.0, 172.0 + LIFT))
lin_dim(S(X_P1, -RB), S(X_P2, -RB), S(0, -192.0), 0, "<>±0.1")
lin_dim(S(0.0, -145.0), S(10.0, -145.0), S(0, -160.0), 0, "<>",
        location=S(-8.0, -160.0 + LIFT))
lin_dim(S(0.0, -145.0), S(17.0, -150.0), S(0, -175.0), 0, "<>",
        location=S(-8.0, -175.0 + LIFT))
lin_dim(S(X_RLF, -R_MINOR - 4.0), S(L_HUB, -R_RLF), S(0, -94.0), 0, "<>",
        location=S(L_HUB + 10.0, -94.0 + LIFT))

# 基准 A (Ø212.5H7 孔轴线)
bx, by = -16.0, -R_MINOR
msp.add_solid([S(bx - 2.6, by), S(bx + 2.6, by), S(bx, by - 4.0)], dxfattribs={"layer": "尺寸"})
line(S(bx, by - 4.0), S(bx, by - 10.0), "尺寸")
pline([S(bx - 6, by - 10), S(bx + 6, by - 10), S(bx + 6, by - 22), S(bx - 6, by - 22)],
      "尺寸", closed=True)
text(S(bx, by - 16), "A", TXT)

# 倒角 C4
leader_note(S(2.0, R_MINOR + 2.0), S(14.0, 92.0), "C4", side=1)
leader_note(S(X_CH_R + 2.0, R_MINOR + 2.0), S(86.0, 92.0), "C4", side=-1)

# 粗糙度
roughness(S(0.0, 128.0), 180, "3.2")
roughness_leader(S(L_HUB, 128.0), S(L_HUB + 8.0, 138.0), "3.2")

# ================================================================ 左视图 (1:2)
CE = (444.0, 370.0)
RBE = 156.0
prof = full_profile()
pline([(v[0] + CE[0], v[1] + CE[1], v[2]) for v in prof], "粗实线", closed=True)
for r in ((D_MINOR + 8.0) / 2, 145.0, 150.0):
    circle(CE, r, "粗实线")
pline(wavy_arc(CE, RBE, 0, 2 * math.pi, 0.6 * K, 40), "波浪线", closed=True)
line(add(CE, (-RBE - 8, 0)), add(CE, (RBE + 8, 0)), "中心线")
line(add(CE, (0, -RBE - 8)), add(CE, (0, RBE + 8)), "中心线")

# 花键标记引线
ang = math.radians(225)
tip = add(CE, (R_MINOR * math.cos(ang), R_MINOR * math.sin(ang)))
knee = add(CE, (-30.0, -40.0))
arrow(tip, (tip[0] - knee[0], tip[1] - knee[1]))
line(tip, knee, "尺寸")
line(knee, add(knee, (62.0, 0)), "尺寸")
mtext(add(knee, (31.0, 1.6)), "渐开线内花键 JIS D2001", 3.0,
      attach=MTextEntityAlignment.BOTTOM_CENTER)
mtext(add(knee, (31.0, -1.6)), "m2.5×z85×20°  x=+0.8", 3.0,
      attach=MTextEntityAlignment.TOP_CENTER)

# ================================================================ B-B 局部剖视 (5:1)
SD = 5.0 * K                       # 模型中的放大倍数
REF = (0.0, R_MINOR)
DO = P(118.0, 40.0)
W_ANG = 1.5 * PITCH_ANG            # 窗口半角 (止于齿中部)
th_s, th_e = math.pi / 2 - W_ANG, math.pi / 2 + W_ANG
R_OUT = R_MAJOR + 3.5


def D(p):
    return ((p[0] - REF[0]) * SD + DO[0], (p[1] - REF[1]) * SD + DO[1])


wprof = xform(window_profile([-1, 0, 1], th_s, th_e), SD, DO, REF)
pline(wprof, "粗实线")
amp = 0.8 * K
side_r = wavy(D((R_MINOR * math.cos(th_e), R_MINOR * math.sin(th_e))),
              D((R_OUT * math.cos(th_e), R_OUT * math.sin(th_e))), amp, 1.0)
top = [D(p) for p in wavy_arc((0, 0), R_OUT, th_e, th_s, amp / SD, 3.0)]
side_l = wavy(D((R_OUT * math.cos(th_s), R_OUT * math.sin(th_s))),
              D((R_MINOR * math.cos(th_s), R_MINOR * math.sin(th_s))), amp, 1.0)
pline(side_r + top[1:] + side_l[1:], "波浪线")
region = [(v[0], v[1], v[2]) for v in wprof]
region[-1] = (region[-1][0], region[-1][1], 0.0)
region += [(*p, 0) for p in side_r[1:]] + [(*p, 0) for p in top[1:]] + \
          [(*p, 0) for p in side_l[1:-1]]
hatch = msp.add_hatch(dxfattribs={"layer": "剖面线"})
hatch.set_pattern_fill("ANSI31", scale=2.0)
hatch.paths.add_polyline_path(region, is_closed=True)

# 量棒 (双点画线示意)
m_val, d_m = pin_measurement()
pc = D((0.0, d_m / 2))
circle(pc, PIN_D / 2 * SD, "双点画线")
line((pc[0] - 4 * K, pc[1]), (pc[0] + 4 * K, pc[1]), "中心线")
line((pc[0], pc[1] - 4 * K), (pc[0], pc[1] + 4 * K), "中心线")


def polar(r, a):
    return (r * math.cos(a), r * math.sin(a))


# Ø212.5H7 小径 (左侧齿顶)
a_tooth = math.pi / 2 + PITCH_ANG / 2
p_tip = D(polar(R_MINOR, a_tooth))
p_low = D(polar(R_MINOR - 4.0, a_tooth))
arrow(p_tip, (p_tip[0] - p_low[0], p_tip[1] - p_low[1]))
line(p_tip, p_low, "尺寸")
line(p_low, (p_low[0] - 50 * K, p_low[1]), "尺寸")
mtext((p_low[0] - 21 * K, p_low[1] + 0.8 * K),
      r"%%c212.5H7(" + tol("+0.046", "0") + ")", TXT,
      attach=MTextEntityAlignment.BOTTOM_CENTER)
roughness((p_low[0] - 45 * K, p_low[1]), 90, "3.2", h=3.0)

# Ø218.25H11 大径 (右侧齿槽槽底)
a_sp = math.pi / 2 - PITCH_ANG
p_root = D(polar(R_MAJOR, a_sp))
p_low2 = D(polar(R_MINOR - 4.0, a_sp))
arrow(p_root, (p_root[0] - p_low2[0], p_root[1] - p_low2[1]))
line(p_root, p_low2, "尺寸")
line(p_low2, (p_low2[0] + 54 * K, p_low2[1]), "尺寸")
mtext((p_low2[0] + 22 * K, p_low2[1] + 0.8 * K),
      r"%%c218.25H11(" + tol("+0.29", "0") + ")", TXT,
      attach=MTextEntityAlignment.BOTTOM_CENTER)
roughness((p_low2[0] + 49 * K, p_low2[1]), 90, "6.3", h=3.0)

# 齿根圆角 R0.5 (左齿槽左侧)
phi1 = math.pi / 2 + PITCH_ANG
fc1 = rot(FC, phi1)
p_fil = D(add(fc1, rot((0.5 * math.cos(0.9), 0.5 * math.sin(0.9)), phi1)))
leader_note(p_fil, add(p_fil, (-22 * K, 18 * K)), "R0.5", side=-1)

# 齿顶倒角 C0.2 (最左侧齿)
phi_c = math.pi / 2 + PITCH_ANG
p_ch = D(polar((R_MINOR + R_CH) / 2, phi_c + (TIP_T + psi(R_MINOR)) / 2 + 0.0))
leader_note(p_ch, add(p_ch, (-14 * K, -5 * K)), "C0.2", side=-1)

# 量棒标注
leader_note(add(pc, (0.0, -PIN_D / 2 * SD)), add(pc, (0.0, -27 * K)),
            "量棒%%c5.0(参考)", side=1, with_arrow=False, h=3.0)

# 表面粗糙度: 齿面 3.2, 槽底 6.3
phi_m1 = math.pi / 2 - PITCH_ANG
r_mid = (R_CH + R_FL) / 2
pf = polar(r_mid, phi_m1 - psi(r_mid))
dr = 0.01
pf2 = polar(r_mid + dr, phi_m1 - psi(r_mid + dr))
tang = math.atan2(pf2[1] - pf[1], pf2[0] - pf[0])
roughness(D(pf), math.degrees(tang) + 90, "3.2", h=3.0)

# 视图名称
text(P(60.0, 84.0), "B-B", 5)
line(P(53.0, 80.5), P(67.0, 80.5), "细实线")
text(P(60.0, 76.5), "5:1", 5)

# ================================================================ 其余粗糙度
text(P(246.0, 281.0), "其余", 5, align=TextEntityAlignment.MIDDLE_RIGHT)
roughness(P(252.0, 277.5), 90, "12.5")

# ================================================================ 参数表
TX0, TY0, TW = 303.0, 287.0, 107.0
C1, C2 = 24.0, 34.0         # 列宽: 名称 | 代号 | 数值
RH, HH = 6.5, 8.0
rows = [
    ("模数", "m", "2.5"),
    ("齿数", "Z", "85"),
    ("压力角", "α", "20°"),
    ("分度圆直径", "d", "%%c212.5"),
    ("基圆直径", "db", "%%c199.685"),
    ("齿形", None, "短齿"),
    ("变位系数", "X", "+0.8"),
    ("大径", "D1", r"%%c218.25H11(" + tol("+0.29", "0") + ")"),
    ("小径", "d1", r"%%c212.5H7(" + tol("+0.046", "0") + ")"),
    ("齿厚", "公法线长度W", "——"),
    ("", "圆棒(球)测跨距M", "207.63(" + tol("+0.075", "-0.1") + ")"),
    ("", "圆棒(球)直径", "%%c5.0(4.2削边后)[B]"),
    ("基圆齿厚", "sb", "8.034"),
    ("齿面配合", None, "c"),
    ("加工方法", None, "插齿"),
    ("定心方式", None, "齿面定心"),
    ("相配件图号", None, "2292-IH-000080"),
    ("", None, "2292-IH-000142"),
]
yb = TY0 - HH - RH * len(rows)
pline([P(TX0, TY0), P(TX0 + TW, TY0), P(TX0 + TW, yb), P(TX0, yb)], "图框", closed=True)
line(P(TX0, TY0 - HH), P(TX0 + TW, TY0 - HH), "图框细")
text(P(TX0 + TW / 2, TY0 - HH / 2), "渐开线花键孔参数表 (JIS D2001)", 4)
merged_first = {10, 11, 17}       # 首列与上一行合并
for i, (a, b, c) in enumerate(rows):
    y1 = TY0 - HH - RH * i
    y0 = y1 - RH
    yc = (y0 + y1) / 2
    if i > 0:
        x_from = TX0 + C1 if i in merged_first else TX0
        line(P(x_from, y1), P(TX0 + TW, y1), "图框细")
    if a:
        span = 1
        while i + span < len(rows) and (i + span) in merged_first:
            span += 1
        text(P(TX0 + C1 / 2, y1 - RH * span / 2), a, 3.0)
    if b is not None:
        text(P(TX0 + C1 + C2 / 2, yc), b, 3.0 if len(b) < 4 else 2.6)
        mtext(P(TX0 + C1 + C2 + (TW - C1 - C2) / 2, yc), c, 3.0)
    else:
        mtext(P(TX0 + C1 + (TW - C1) / 2, yc), c, 3.0)
line(P(TX0 + C1, TY0 - HH), P(TX0 + C1, yb), "图框细")
y_c2_top = TY0 - HH
y_c2_bot = TY0 - HH - RH * 13
for i, (a, b, c) in enumerate(rows):
    y1 = TY0 - HH - RH * i
    if b is not None:
        line(P(TX0 + C1 + C2, y1), P(TX0 + C1 + C2, y1 - RH), "图框细")

# ================================================================ 技术要求
reqs = [
    "1.内花键按JIS D2001(汽车用渐开线花键)设计、制造与检验,",
    "   齿面定心,齿面配合c,插齿加工。",
    "2.齿槽宽用圆棒测跨距M检验(圆棒%%c5.0,削边后4.2),",
    "   并用花键综合通规检验,通规应能自由通过。",
    "3.花键齿顶倒角C0.2,齿根圆角R0.5,齿面不得有毛刺、碰伤。",
    "4.未注倒角C1,未注圆角R3。",
    "5.热处理:整体调质,硬度HB277-331。",
    "6.链轮其余结构及要求见本图号第1张。",
]
text(P(TX0 + TW / 2, yb - 7.0), "技术要求", 5)
for i, s in enumerate(reqs):
    text(P(TX0 + 1.0, yb - 15.0 - i * 5.8), s, 3.0, align=TextEntityAlignment.MIDDLE_LEFT)

# ================================================================ 标题栏 (GB/T 10609.1)
BX, BY = 230.0, 10.0
pline([P(BX, BY), P(BX + 180, BY), P(BX + 180, BY + 56), P(BX, BY + 56)], "图框", closed=True)
# 左区: 更改栏 + 签字栏
for j in range(1, 8):
    line(P(BX, BY + 7 * j), P(BX + 80, BY + 7 * j), "图框细")
line(P(BX, BY + 28), P(BX + 80, BY + 28), "图框")
for x in (10, 20, 36, 52, 64):
    line(P(BX + x, BY + 28), P(BX + x, BY + 56), "图框细")
for x in (12, 24, 40, 52, 64):
    line(P(BX + x, BY), P(BX + x, BY + 28), "图框细")
line(P(BX + 80, BY), P(BX + 80, BY + 56), "图框")
for x, s in ((5, "标记"), (15, "处数"), (28, "分区"), (44, "更改文件号"), (58, "签名"), (72, "年.月.日")):
    text(P(BX + x, BY + 31.5), s, 2.5)
for j, (a, b) in enumerate((("设计", "标准化"), ("校对", ""), ("审核", ""), ("工艺", "批准"))):
    yy = BY + 24.5 - 7 * j
    text(P(BX + 6, yy), a, 2.5)
    if b:
        text(P(BX + 46, yy), b, 2.5)
# 中区
line(P(BX + 80, BY + 38), P(BX + 130, BY + 38), "图框")
line(P(BX + 80, BY + 31.5), P(BX + 130, BY + 31.5), "图框细")
line(P(BX + 80, BY + 18), P(BX + 130, BY + 18), "图框")
line(P(BX + 80, BY + 9), P(BX + 130, BY + 9), "图框细")
for x in (86.5, 93, 99.5):
    line(P(BX + x, BY + 18), P(BX + x, BY + 31.5), "图框细")
for x in (106, 118):
    line(P(BX + x, BY + 18), P(BX + x, BY + 38), "图框细")
line(P(BX + 105, BY + 9), P(BX + 105, BY + 18), "图框细")
text(P(BX + 105, BY + 47), "42CrMo", 5)
text(P(BX + 93, BY + 34.75), "阶段标记", 2.5)
text(P(BX + 112, BY + 34.75), "重量", 2.5)
text(P(BX + 124, BY + 34.75), "比例", 2.5)
text(P(BX + 83.25, BY + 24.75), "S", 3)
text(P(BX + 112, BY + 24.75), "119.565", 2.5)
text(P(BX + 124, BY + 24.75), "1:2", 3.5)
text(P(BX + 92.5, BY + 13.5), "共 2 张", 3)
text(P(BX + 117.5, BY + 13.5), "第 2 张", 3)
text(P(BX + 105, BY + 4.5), "JIS D2001 m2.5 z85", 2.8)
# 右区
line(P(BX + 130, BY + 38), P(BX + 180, BY + 38), "图框")
line(P(BX + 130, BY + 18), P(BX + 180, BY + 18), "图框")
text(P(BX + 155, BY + 31), "链 轮", 6)
text(P(BX + 155, BY + 23), "(内花键)", 4.5)
text(P(BX + 155, BY + 9), "2292-IH-000139", 5.5)


# ================================================================ 输出
def save_dxf():
    doc.saveas(OUT_BASE + ".dxf")


def render_preview():
    """用开源字体渲染预览 (DXF 本身保持仿宋)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from ezdxf.addons.drawing.config import (BackgroundPolicy, ColorPolicy,
                                             Configuration)

    doc.styles.get("HZ").dxf.font = "wqy-zenhei.ttc"
    try:
        fig = plt.figure(figsize=(W / 25.4, H / 25.4))
        ax = fig.add_axes((0, 0, 1, 1))
        ax.set_axis_off()
        cfg = Configuration(color_policy=ColorPolicy.BLACK,
                            background_policy=BackgroundPolicy.WHITE)
        Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(
            msp, finalize=True)
        ax.set_xlim(0, W * K)
        ax.set_ylim(0, H * K)
        ax.set_aspect("equal")
        fig.savefig(OUT_BASE + ".png", dpi=300, facecolor="white")
        fig.savefig(OUT_BASE + ".pdf", facecolor="white")
        plt.close(fig)
    finally:
        doc.styles.get("HZ").dxf.font = FONT_FILE


if __name__ == "__main__":
    save_dxf()
    if "--no-preview" not in sys.argv:
        render_preview()
    m_val, d_m = pin_measurement()
    print(f"saved {OUT_BASE}.dxf  (M={m_val:.3f}, sb={S_BASE:.3f}, db={D_BASE:.3f})")
