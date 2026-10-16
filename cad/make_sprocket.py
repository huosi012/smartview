"""
生成 链轮 2292-IH-000139 (A2, 1:3) —— 按原图照抄并并入内花键内容, DXF + 预览图.

在原图基础上并入的内花键内容: 参数表增加 基圆直径/齿形/基圆齿厚/齿面配合/加工方法/执行标准,
花键详图改为 B-B 局部剖视 5:1 (含量棒示意), 技术要求增加第 4~6 条.
执行标准为企业标准 Q/STB13.110.22 (20°压力角), 齿形参照 JIS D2001
(JIS D2001 规定齿数 6~40, z=85 超出其范围).

约定:
  * 模型空间 1:1 绘制主视图 (全剖) 与左视图, 图框按 K=3 放大;
  * B-B 局部剖视图纸比例 5:1, 在模型空间中按 5*K = 15 倍绘制;
  * 版面位置取自原图 (图框内 1px = 0.397mm).

运行:  python3 make_sprocket.py
输出:  2292-IH-000139_链轮.dxf / .png / .pdf, 以及轴测图 2292-IH-000139_轴测图.png
"""
import math
import os
import sys

from ezdxf.enums import MTextEntityAlignment, TextEntityAlignment

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sprocket_geom as sg  # noqa: E402
import spline_geom as spg  # noqa: E402
from cad_common import Sheet, add, bulge_of, rot, tol, wavy, wavy_arc  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_BASE = os.path.join(HERE, "2292-IH-000139_链轮")
ISO_NAME = "2292-IH-000139_轴测图.png"

K = 3.0
TXT = 3.5
W, H = 594, 420   # A2

sh = Sheet(K, TXT)
P, line, pline, circle, arc, text, mtext = (sh.P, sh.line, sh.pline, sh.circle, sh.arc,
                                            sh.text, sh.mtext)
arrow, leader_note, lin_dim = sh.arrow, sh.leader_note, sh.lin_dim
roughness, roughness_leader = sh.roughness, sh.roughness_leader
LIFT = (TXT / 2 + 0.8) * K


def px(x, y):
    """原图像素 -> 图纸坐标 (mm)."""
    return (25 + (x - 4.5) * 0.397, 10 + (1014 - y) * 0.397)


# ================================================================ 图框
pline([P(0, 0), P(W, 0), P(W, H), P(0, H)], "图框细", closed=True)
pline([P(25, 10), P(584, 10), P(584, 410), P(25, 410)], "图框", closed=True)
for a, b in (((W / 2, 0), (W / 2, 10)), ((W / 2, 410), (W / 2, H)),
             ((0, H / 2), (25, H / 2)), ((584, H / 2), (W, H / 2))):
    line(P(*a), P(*b), "图框")
pline([P(25, 396.3), P(80.8, 396.3), P(80.8, 410), P(25, 410)], "图框", closed=True)
text(P(52.9, 403.2), "2292-IH-000139", 5, rot_deg=180)

# ================================================================ 主视图 (全剖, 1:3)
SX0, SY0 = P(138.7, 230.3)


def S(x, y):
    return (SX0 + x, SY0 + y)


def SV(verts, sy=1):
    return [(SX0 + v[0], SY0 + sy * v[1], sy * (v[2] if len(v) > 2 else 0.0)) for v in verts]


L = 110.5
XR_L, XR_R = L - 19.0 - sg.RIM_W, L - 19.0          # 齿圈两侧面 40.83 / 91.5
XW_L, XW_R = XR_L + 3.0, L - 20.0                  # 辐板两侧面 43.83 / 90.5
R480 = 240.0
RM, RN = spg.R_MAJOR, spg.R_MINOR                  # 花键大/小径半径
FL = (XW_L - 20.0, 170.0)                          # 左 R20 圆心
FR = (XW_R + 20.0, 165.0)                          # 右 R20 圆心
C3L = (XR_L, R480 - 3.0)                           # 左 R3 圆心
C3R = (XW_R + 3.0, R480 - 3.0)                     # 右 R3 圆心
Y_R3R = C3R[1] + math.sqrt(9.0 - (XR_R - C3R[0]) ** 2)
RCS = sg.R_CHAMFER_START
CH_L = (XR_L + sg.RX, RCS)                         # 齿侧 R88.9 圆心
CH_R = (XR_R - sg.RX, RCS)
X_TIP_L, X_TIP_R = XR_L + sg.BA, XR_R - sg.BA
R_ROOT = sg.R_P - sg.R1                            # 剖切处齿槽底
HOLE_R, HOLE_RAD = 190.0, 32.0
Y_HB, Y_HT = HOLE_R - HOLE_RAD, HOLE_R + HOLE_RAD  # 孔壁 158 / 222


def x_on_circle(c, r, y, side):
    return c[0] + side * math.sqrt(r * r - (y - c[1]) ** 2)


bore = [  # 内孔 (由左端倒角起, 至右端面)
    (0.0, RN + 4.0, 0), (4.0, RN, 0), (96.5, RN, 0), (100.5, RN + 4.0, 0),
    (100.5, 111.0, 0), (L, 111.0, 0), (L, 145.0, 0),
]


def hub_left_tail(y_end):
    """左侧: 由 R20 圆角 (y_end 处) 到左端面."""
    p0 = (x_on_circle(FL, 20.0, y_end, 1), y_end)
    return [(p0[0], p0[1], bulge_of(FL, p0, (FL[0], 150.0))), (FL[0], 150.0, 0),
            (17.0, 150.0, 0), (10.0, 145.0, 0), (0.0, 145.0, 0)]


# 下半部 (剖切于齿中心): 完整齿形
tooth = bore[:-1] + [
    (L, 145.0, bulge_of(FR, (L, 145.0), (XW_R, 165.0))), (XW_R, 165.0, 0),
    (XW_R, C3R[1], bulge_of(C3R, (XW_R, C3R[1]), (XR_R, Y_R3R))), (XR_R, Y_R3R, 0),
    (XR_R, RCS, bulge_of(CH_R, (XR_R, RCS), (X_TIP_R, sg.R_A))), (X_TIP_R, sg.R_A, 0),
    (X_TIP_L, sg.R_A, bulge_of(CH_L, (X_TIP_L, sg.R_A), (XR_L, RCS))), (XR_L, RCS, 0),
    (XR_L, R480, bulge_of(C3L, (XR_L, R480), (XW_L, C3L[1]))), (XW_L, C3L[1], 0),
] + hub_left_tail(170.0)
# 上半部 (剖切于齿槽与 Ø64 孔): 孔下方区域 + 孔上方区域
y_fr = (x_on_circle(FR, 20.0, Y_HB, -1), Y_HB)
upper_a = bore[:-1] + [
    (L, 145.0, bulge_of(FR, (L, 145.0), y_fr)), (y_fr[0], Y_HB, 0),
] + hub_left_tail(Y_HB)
upper_b = [
    (XW_L + 5.0, Y_HT, 0), (XW_R - 5.0, Y_HT, bulge_of((XW_R - 5, Y_HT + 5), (XW_R - 5, Y_HT),
                                                      (XW_R, Y_HT + 5))),
    (XW_R, Y_HT + 5.0, 0),
    (XW_R, C3R[1], bulge_of(C3R, (XW_R, C3R[1]), (XR_R, Y_R3R))), (XR_R, Y_R3R, 0),
    (XR_R, R_ROOT, 0), (XR_L, R_ROOT, 0),
    (XR_L, R480, bulge_of(C3L, (XR_L, R480), (XW_L, C3L[1]))), (XW_L, C3L[1], 0),
    (XW_L, Y_HT + 5.0, bulge_of((XW_L + 5, Y_HT + 5), (XW_L, Y_HT + 5), (XW_L + 5, Y_HT))),
]
for reg, sy in ((upper_a, 1), (upper_b, 1), (tooth, -1)):
    v = SV(reg, sy)
    pline(v, "粗实线", closed=True)
    sh.hatch(v)

# 内花键大径线、孔内可见轮廓线
for sy in (1, -1):
    line(S(4.0 - (RM - RN), sy * RM), S(96.5 + (RM - RN), sy * RM), "粗实线")
for x, r in ((0.0, RN + 4.0), (4.0, RN), (96.5, RN), (100.5, 111.0), (L, 111.0)):
    line(S(x, -r), S(x, r), "粗实线")
# 辐板凹台在后半部的投影 (Ø480 台阶边)
for sy in (1, -1):
    y0 = FL[1] - math.sqrt(400.0 - (XR_L - FL[0]) ** 2)
    line(S(XR_L, sy * y0), S(XR_L, sy * C3L[1]), "粗实线")
    y0 = FR[1] - math.sqrt(400.0 - (XR_R - FR[0]) ** 2)
    line(S(XR_R, sy * y0), S(XR_R, sy * C3R[1]), "粗实线")
# Ø64 孔内可见线 (R5 倒圆边)
for x, y0, y1 in ((XW_L, 170.0, Y_HT + 5), (XW_L + 5, Y_HB, Y_HT), (XW_R - 5, Y_HB, Y_HT),
                  (XW_R, 165.0, Y_HT + 5)):
    line(S(x, y0), S(x, y1), "粗实线")
line(S(XW_L - 6, HOLE_R), S(XW_R + 6, HOLE_R), "中心线")

# 上半部: 剖切面后方相邻轮齿的投影 (含齿侧倒角)
proj = []
n = 60
for i in range(n + 1):
    a = XR_L + (XR_R - XR_L) * i / n
    r = sg.chamfer_r_limit(a, XR_L, XR_R)
    proj.append(S(a, r * math.cos(sg.flank_angle(r))))
pline([S(XR_L, R_ROOT)] + proj + [S(XR_R, R_ROOT)], "粗实线")

# 分度线、轴线
for sy in (1, -1):
    line(S(XR_L - 6, sy * sg.R_P), S(XR_R + 6, sy * sg.R_P), "中心线")
line(S(-10.0, 0), S(L + 10.0, 0), "中心线")
# B-B 剖切符号 (x = 60, 向右投射)
XB = 60.0
for sy in (1, -1):
    line(S(XB, sy * 352.0), S(XB, sy * 362.0), "粗实线")
    line(S(XB, sy * 362.0), S(XB + 12.0, sy * 362.0), "细实线")
    arrow(S(XB + 12.0, sy * 362.0), (1, 0), "粗实线")
    text(S(XB + 4.0, sy * 375.0), "B", 5)

# ---------------------------------------------------------------- 主视图尺寸
OD = [  # (x_base, p1, p2, 文字)
    (-310.8, (X_TIP_L, -sg.R_A), (X_TIP_L, sg.R_A), "%%c<>" + tol("0", "-0.3")),
    (-272.7, (XR_L, -sg.R_P), (XR_L, sg.R_P), "%%c652.88"),
    (-233.4, (XR_L, -sg.D_F / 2), (XR_L, sg.D_F / 2), "%%c<>" + tol("0", "-0.3")),
    (-195.3, (XR_L, -R480), (XR_L, R480), "%%c<>"),
    (-159.6, (17.0, -150.0), (17.0, 150.0), "%%c<>"),
    (-120.3, (0.0, -145.0), (0.0, 145.0), "%%c<>"),
    (-84.3, (4.0 - (RM - RN), -RM), (4.0 - (RM - RN), RM), "%%c<> H11(" + tol("+0.29", "0") + ")"),
    (-42.6, (4.0, -RN), (4.0, RN), "%%c<> H7(" + tol("+0.046", "0") + ")"),
    (151.8, (96.5, -RN), (96.5, RN), r"%%c<>\H0.6x;(分度圆)"),
    (187.5, (L, -111.0), (L, 111.0), "%%c<>"),
    (225.6, (L, -145.0), (L, 145.0), "%%c<>"),
    (261.6, (XR_R, -R480), (XR_R, R480), "%%c<>"),
]
for xb, p1, p2, s in OD:
    lin_dim(S(*p1), S(*p2), S(xb, 0), 90, s)

lin_dim(S(0, 145.0), S(L, 145.0), S(0, 484.8), 0, "<>" + r"\H0.7x;\S+0.1^ 0;")
lin_dim(S(XR_R, 303.0), S(L, 145.0), S(0, 368.0), 0, "<>±0.1", location=S(L + 17, 368.0 + LIFT))
lin_dim(S(0, 145.0), S(17.0, 150.0), S(0, 199.0), 0, "<>", location=S(-9, 199.0 + LIFT))
lin_dim(S(0, 145.0), S(10.0, 145.0), S(0, 171.5), 0, "<>", location=S(-9, 171.5 + LIFT))
lin_dim(S(XR_L, 230.0), S(XW_L, 230.0), S(0, 230.0), 0, "<>", location=S(XR_L - 9, 230.0 + LIFT))
lin_dim(S(XW_R, HOLE_R), S(L, 145.0), S(0, HOLE_R), 0, "<>", location=S(L + 9, HOLE_R + LIFT))
lin_dim(S(0.0, 81.0), S(4.0, 81.0), S(0, 81.0), 0, "C4", location=S(-9, 81.0 + LIFT))
lin_dim(S(96.5, 81.0), S(100.5, 81.0), S(0, 81.0), 0, "C4", location=S(86.0, 81.0 + LIFT))
lin_dim(S(100.5, 58.0), S(L, 58.0), S(0, 58.0), 0, "<>", location=S(L + 9, 58.0 + LIFT))
lin_dim(S(XR_L, -RCS), S(X_TIP_L, -sg.R_A), S(0, -370.2), 0, "<>",
        location=S(XR_L - 14, -370.2 + LIFT))
lin_dim(S(X_TIP_R, -sg.R_A), S(XR_R, -RCS), S(0, -370.2), 0, "<>",
        location=S(XR_R + 14, -370.2 + LIFT))
lin_dim(S(XR_L, -RCS), S(XR_R, -RCS), S(0, -411.9), 0, "<>±0.1",
        location=S(XR_R + 42, -411.9 + LIFT))

# 半径引线
def on_arc(c, r, ang_deg, sy=1):
    a = math.radians(ang_deg)
    return (c[0] + r * math.cos(a), sy * (c[1] + r * math.sin(a)))


leader_note(S(*on_arc(FL, 20.0, -45, -1)), S(16.0, -182.0), "R20", side=-1)
leader_note(S(*on_arc(FR, 20.0, -135, -1)), S(L + 2.0, -182.0), "R20", side=1)
leader_note(S(*on_arc(C3L, 3.0, 45, -1)), S(24.0, -224.0), "R3", side=-1)
leader_note(S(*on_arc(C3R, 3.0, 120, -1)), S(L - 4.0, -224.0), "R3", side=1)
leader_note(S(*on_arc(CH_L, sg.RX, 157, -1)), S(16.0, -336.0), "R88.9", side=-1)
leader_note(S(*on_arc(CH_R, sg.RX, 23, -1)), S(L + 4.0, -336.0), "R88.9", side=1)
leader_note(S(*on_arc((XW_L + 5, Y_HT + 5), 5.0, 225)), S(30.0, 212.0), "R5", side=-1)
leader_note(S(*on_arc((XW_R - 5, Y_HT + 5), 5.0, 315)), S(L + 8.0, 251.0), "R5", side=1)

# 基准 A (花键分度圆)
sh.datum(S(151.8, -RN), (0, -1), "A")

# 形位公差
lf, rt = sh.gdt_frame(P(98.7, 360.0), [("PERP", 7), ("0.08", 12), ("A", 7)])
line(rt, S(0, (rt[1] - SY0)), "尺寸")
arrow(S(0, rt[1] - SY0), (1, 0))
lf, rt = sh.gdt_frame(P(186.0, 360.0), [("PERP", 7), ("0.08", 12), ("A", 7)])
line(lf, S(L, lf[1] - SY0), "尺寸")
arrow(S(L, lf[1] - SY0), (-1, 0))
lf, rt = sh.gdt_frame(P(29.2, 365.0), [("RUNOUT", 7), ("0.05", 12), ("A", 7)])
line(rt, (S(-233.4, 0)[0], rt[1]), "尺寸")
line((S(-233.4, 0)[0], rt[1]), S(-233.4, sg.D_F / 2), "尺寸")
arrow(S(-233.4, sg.D_F / 2), (0, -1))
lf, rt = sh.gdt_frame(P(110.0, 132.6), [("RUNOUT", 7), ("0.1", 10), ("A", 7)])
line(rt, (S(XR_L, 0)[0], rt[1]), "尺寸")
arrow((S(XR_L, 0)[0], rt[1]), (1, 0))
lf, rt = sh.gdt_frame(P(183.0, 132.6), [("RUNOUT", 7), ("0.1", 10), ("A", 7)])
line(lf, (S(XR_R, 0)[0], lf[1]), "尺寸")
arrow((S(XR_R, 0)[0], lf[1]), (-1, 0))

# 表面粗糙度
roughness(S(-48.6, sg.R_A), 90, "6.3")
roughness(S(-108.0, sg.R_P), 90, "3.2")
roughness(S(-155.7, sg.D_F / 2), 90, "3.2")
roughness(S(XR_L, 278.7), 180, "6.3")
roughness_leader(S(XR_R, 278.7), S(XR_R + 12, 292.0), "6.3")
roughness(S(0.0, 128.0), 180, "3.2")
roughness_leader(S(L, 128.0), S(L + 8.0, 136.0), "3.2")

# ================================================================ 左视图 (1:3)
CF = P(357.5, 230.3)


def F(x, y):
    return (CF[0] + x, CF[1] + y)


pline([(CF[0] + v[0], CF[1] + v[1], v[2]) for v in sg.full_profile()], "粗实线", closed=True)
pline([(CF[0] + v[0], CF[1] + v[1], v[2]) for v in spg.full_profile()], "粗实线", closed=True)
# 齿侧倒角切线圆 (仅画在齿上)
fa = sg.flank_angle(RCS)
for k in range(sg.Z):
    phi = math.degrees(math.pi / 2 + k * sg.PITCH_ANG)
    arc(CF, RCS, phi + math.degrees(fa), phi + 360.0 / sg.Z - math.degrees(fa), "细实线")
for r, layer in (((spg.D_MINOR + 8) / 2, "粗实线"), (145.0, "粗实线"), (150.0, "粗实线"),
                 (R480, "粗实线"), (R480 - 3, "细实线")):
    circle(CF, r, layer)
# R20 圆角切线圆 (在孔处断开)
HOLE_ANG = (90.0, 210.0, 330.0)
dlt = math.degrees(math.acos((170.0 ** 2 + HOLE_R ** 2 - 37.0 ** 2) / (2 * 170.0 * HOLE_R)))
for i, h in enumerate(HOLE_ANG):
    arc(CF, 170.0, h + dlt, HOLE_ANG[(i + 1) % 3] - dlt + (360 if i == 2 else 0), "细实线")
circle(CF, HOLE_R, "中心线")
for h in HOLE_ANG:
    c = F(HOLE_R * math.cos(math.radians(h)), HOLE_R * math.sin(math.radians(h)))
    circle(c, HOLE_RAD, "粗实线")
    circle(c, HOLE_RAD + 5, "细实线")
    u = (math.cos(math.radians(h)), math.sin(math.radians(h)))
    line((c[0] - u[0] * 46, c[1] - u[1] * 46), (c[0] + u[0] * 46, c[1] + u[1] * 46), "中心线")
line(F(-sg.R_A - 15, 0), F(sg.R_A + 15, 0), "中心线")
line(F(0, -sg.R_A - 15), F(0, sg.R_A + 130), "中心线")

# 3-Ø64均布
hc = F(0, HOLE_R)
a = math.radians(-115)
tip = (hc[0] + HOLE_RAD * math.cos(a), hc[1] + HOLE_RAD * math.sin(a))
knee = F(42.0, 258.0)
arrow(tip, (tip[0] - knee[0], tip[1] - knee[1]))
line(tip, knee, "尺寸")
leader_note(knee, knee, "3-%%c64均布", side=1, with_arrow=False)

# Ø380
a = math.radians(150)
p1 = F(HOLE_R * math.cos(a), HOLE_R * math.sin(a))
p2 = F(-HOLE_R * math.cos(a), -HOLE_R * math.sin(a))
line(p1, p2, "尺寸")
arrow(p1, (p1[0] - p2[0], p1[1] - p2[1]))
arrow(p2, (p2[0] - p1[0], p2[1] - p1[1]))
mid = ((p1[0] * 3 + p2[0] * 1) / 4, (p1[1] * 3 + p2[1] * 1) / 4)
mtext(add(mid, rot((0, 2.2 * K), math.radians(-30))), "%%c380", TXT, rot_deg=-30,
      attach=MTextEntityAlignment.MIDDLE_CENTER)

# 齿形尺寸 (顶部齿槽, O 为滚子中心)
O = F(0, sg.R_P)


def Fo(x, y):
    return (O[0] + x, O[1] + y)


c2x, c2y = sg.C2_OFF
c3x, c3y = sg.C3_OFF
line(Fo(-175, 0), Fo(175, 0), "细实线")
line(Fo(-c2x, c2y), Fo(-133, c2y), "细实线")
line(Fo(c2x, c2y), Fo(157, c2y), "细实线")
line(Fo(-c3x, c3y), Fo(-163, c3y), "细实线")
line(Fo(c3x, c3y), Fo(178, c3y), "细实线")
for sgn in (-1, 1):
    pa, pb = sorted([(sgn * c3x, c3y), (0, 120.5)])
    lin_dim(Fo(*pa), Fo(*pb), Fo(0, 120.5), 0, "<>")
    pa, pb = sorted([(sgn * c2x, c2y), (0, 92.2)])
    lin_dim(Fo(*pa), Fo(*pb), Fo(0, 92.2), 0, "<>",
            location=Fo(sgn * (c2x + 13), 92.2 + LIFT))
lin_dim(Fo(-127.6, 0), Fo(-127.6, c2y), Fo(-127.6, 0), 90, "<>",
        location=Fo(-127.6 - LIFT, 46.0))
lin_dim(Fo(151.0, 0), Fo(151.0, c2y), Fo(151.0, 0), 90, "<>",
        location=Fo(151.0 - LIFT, 46.0))
lin_dim(Fo(-158.7, 0), Fo(-158.7, c3y), Fo(-158.7, 0), 90, "<>",
        location=Fo(-158.7 - LIFT, 22.0))
lin_dim(Fo(173.0, 0), Fo(173.0, c3y), Fo(173.0, 0), 90, "<>",
        location=Fo(173.0 - LIFT, 22.0))
fl = sg.right_flank()
for sgn in (-1, 1):
    # R70.36: 引线过圆心 (-sgn*34.21, 26.35), 箭头指向对侧工作段圆弧
    c = Fo(-sgn * c2x, c2y)
    t = fl["t1"][0] * 0.25 + fl["t2"][0] * 0.75, fl["t1"][1] * 0.25 + fl["t2"][1] * 0.75
    tp = F(sgn * t[0], t[1])
    d = (c[0] - tp[0], c[1] - tp[1])
    ln = math.hypot(*d)
    knee = (c[0] + d[0] / ln * 45, c[1] + d[1] / ln * 45)
    arrow(tp, (tp[0] - c[0], tp[1] - c[1]))
    line(tp, knee, "尺寸")
    leader_note(knee, knee, "R70.36", side=-sgn, with_arrow=False)
    # R39.27: 引线过圆心 (sgn*69.52, -9.56)
    c = Fo(-sgn * c3x, c3y)
    t = ((fl["t3"][0] + fl["t4"][0]) / 2, (fl["t3"][1] + fl["t4"][1]) / 2)
    tp = F(-sgn * t[0], t[1])
    d = (c[0] - tp[0], c[1] - tp[1])
    ln = math.hypot(*d)
    end = (c[0] + d[0] / ln * 52, c[1] + d[1] / ln * 52)
    arrow(tp, (tp[0] - c[0], tp[1] - c[1]))
    line(tp, end, "尺寸")
    ang = math.degrees(math.atan2(d[1], d[0]))
    ang = ang + 180 if abs(ang) > 90 else ang
    mid = ((c[0] + end[0]) / 2, (c[1] + end[1]) / 2)
    mtext(add(mid, rot((0, 2.2 * K), math.radians(ang))), "R39.27", TXT, rot_deg=ang)
a = math.radians(-112)
tp = Fo(sg.R1 * math.cos(a), sg.R1 * math.sin(a))
knee = Fo(-12.0, -62.0)
arrow(tp, (tp[0] - knee[0], tp[1] - knee[1]))
line(tp, knee, "尺寸")
leader_note(knee, knee, "R27.3", side=-1, with_arrow=False)

# ================================================================ B-B 局部剖视 (5:1)
SD = 5.0 * K
DREF = (0.0, spg.R_MINOR)
DO = P(255.0, 46.0)
W_ANG = 1.5 * spg.PITCH_ANG            # 窗口半角 (止于齿中部)
th_s, th_e = math.pi / 2 - W_ANG, math.pi / 2 + W_ANG
R_OUT = spg.R_MAJOR + 3.5
hp = spg.half_space_profile()
pitch = spg.PITCH_ANG


def D(p):
    return ((p[0] - DREF[0]) * SD + DO[0], (p[1] - DREF[1]) * SD + DO[1])


def polar(r, a):
    return (r * math.cos(a), r * math.sin(a))


wp = [(*D(v[:2]), v[2]) for v in spg.window_profile([-1, 0, 1], th_s, th_e)]
pline(wp, "粗实线")
amp = 0.8 * K
side_r = wavy(D(polar(spg.R_MINOR, th_e)), D(polar(R_OUT, th_e)), amp, 1.0)
top = [D(p) for p in wavy_arc((0, 0), R_OUT, th_e, th_s, amp / SD, 3.0)]
side_l = wavy(D(polar(R_OUT, th_s)), D(polar(spg.R_MINOR, th_s)), amp, 1.0)
pline(side_r + top[1:] + side_l[1:], "波浪线")
region = [list(v) for v in wp]
region[-1][2] = 0.0
region += [(*p, 0) for p in side_r[1:]] + [(*p, 0) for p in top[1:]] + \
          [(*p, 0) for p in side_l[1:-1]]
sh.hatch(region)

# 量棒 (双点画线示意)
m_val, d_m = spg.pin_measurement()
pc = D((0.0, d_m / 2))
circle(pc, spg.PIN_D / 2 * SD, "双点画线")
line((pc[0] - 4 * K, pc[1]), (pc[0] + 4 * K, pc[1]), "中心线")
line((pc[0], pc[1] - 4 * K), (pc[0], pc[1] + 4 * K), "中心线")
leader_note((pc[0], pc[1] - spg.PIN_D / 2 * SD), (pc[0], pc[1] - 27 * K),
            "量棒%%c5.0(参考)", side=1, with_arrow=False, h=3.0)

# Ø212.5 H7 小径 (齿顶), 粗糙度 6.3
a_tooth = math.pi / 2 + pitch / 2
p_tip = D(polar(spg.R_MINOR, a_tooth))
p_low = D(polar(spg.R_MINOR - 4.0, a_tooth))
arrow(p_tip, (p_tip[0] - p_low[0], p_tip[1] - p_low[1]))
line(p_tip, p_low, "尺寸")
line(p_low, (p_low[0] - 50 * K, p_low[1]), "尺寸")
mtext((p_low[0] - 21 * K, p_low[1] + 0.8 * K), "%%c212.5 H7(" + tol("+0.046", "0") + ")",
      TXT, attach=MTextEntityAlignment.BOTTOM_CENTER)
roughness((p_low[0] - 45 * K, p_low[1]), 90, "6.3", h=3.0)

# Ø218.25 H11 大径 (槽底), 粗糙度 6.3
a_sp = math.pi / 2 - pitch
p_root = D(polar(spg.R_MAJOR, a_sp))
p_low2 = D(polar(spg.R_MINOR - 4.0, a_sp))
arrow(p_root, (p_root[0] - p_low2[0], p_root[1] - p_low2[1]))
line(p_root, p_low2, "尺寸")
line(p_low2, (p_low2[0] + 56 * K, p_low2[1]), "尺寸")
mtext((p_low2[0] + 23 * K, p_low2[1] + 0.8 * K), "%%c218.25 H11(" + tol("+0.29", "0") + ")",
      TXT, attach=MTextEntityAlignment.BOTTOM_CENTER)
roughness((p_low2[0] + 51 * K, p_low2[1]), 90, "6.3", h=3.0)

# 齿根圆角 R0.5、齿顶倒角 C0.2
phi1 = math.pi / 2 + pitch
p_fil = D(add(rot(hp["fillet_center"], phi1), rot((0.5 * math.cos(0.9), 0.5 * math.sin(0.9)), phi1)))
leader_note(p_fil, add(p_fil, (-22 * K, 18 * K)), "R0.5", side=-1)
p_ch = D(polar((spg.R_MINOR + hp["chamfer_r"]) / 2,
               phi1 + (hp["tip_theta"] + spg.psi(spg.R_MINOR)) / 2))
leader_note(p_ch, add(p_ch, (-14 * K, -5 * K)), "C0.2", side=-1)

# 齿面粗糙度 3.2
rr = (hp["chamfer_r"] + hp["fillet_r"]) / 2
pf = polar(rr, a_sp - spg.psi(rr))
pf2 = polar(rr + 0.01, a_sp - spg.psi(rr + 0.01))
roughness(D(pf), math.degrees(math.atan2(pf2[1] - pf[1], pf2[0] - pf[0])) + 90, "3.2", h=3.0)

text(P(150.0, 86.0), "B-B", 5)
line(P(143.0, 82.5), P(157.0, 82.5), "细实线")
text(P(150.0, 78.5), "5:1", 5)

# ================================================================ 其余粗糙度
text(P(468.0, 384.0), "其余", 3.5, align=TextEntityAlignment.MIDDLE_RIGHT)
roughness(P(473.5, 382.5), 90, "12.5")

# ================================================================ 参数表


def rows_y(top, heights):
    ys = [top]
    for hh in heights:
        ys.append(ys[-1] - hh)
    return ys


x1 = [490.1, 509.9, 542.1, 584.0]
y1 = rows_y(410.2, [10] + [7] * 7 + [9, 9] + [7] * 7)
cells1 = [
    (0, 1, 0, 3, "渐开线花键孔参数表"),
    (1, 2, 0, 1, "模数"), (1, 2, 1, 2, "m"), (1, 2, 2, 3, "2.5"),
    (2, 3, 0, 1, "齿数"), (2, 3, 1, 2, "Z"), (2, 3, 2, 3, "85"),
    (3, 4, 0, 1, "压力角"), (3, 4, 1, 2, "α"), (3, 4, 2, 3, "20°"),
    (4, 5, 0, 1, "分度圆直径"), (4, 5, 1, 2, "do"), (4, 5, 2, 3, "%%c212.5"),
    (5, 6, 0, 1, "基圆直径"), (5, 6, 1, 2, "db"), (5, 6, 2, 3, "%%c199.685"),
    (6, 7, 0, 1, "齿形"), (6, 7, 1, 3, "短齿"),
    (7, 8, 0, 1, "变位系数"), (7, 8, 1, 2, "X"), (7, 8, 2, 3, "+0.8"),
    (8, 10, 0, 1, "齿厚"),
    (8, 9, 1, 2, "圆棒(球)测跨距M"), (8, 9, 2, 3, "207.63(" + tol("+0.075", "-0.1") + ")"),
    (9, 10, 1, 2, "圆棒(球)直径"), (9, 10, 2, 3, "5.0(4.2削边后)"),
    (10, 11, 0, 1, "基圆齿厚"), (10, 11, 1, 2, "sb"), (10, 11, 2, 3, "8.034"),
    (11, 12, 0, 1, "齿面配合"), (11, 12, 1, 3, "c"),
    (12, 13, 0, 1, "加工方法"), (12, 13, 1, 3, "插齿"),
    (13, 14, 0, 1, "定心方式"), (13, 14, 1, 3, "齿面定心"),
    (14, 15, 0, 1, "执行标准"), (14, 15, 1, 3, "Q/STB13.110.22 (齿形参照JIS D2001)"),
    (15, 17, 0, 1, "相配件图号"), (15, 16, 1, 3, "2292-IH-000080"), (16, 17, 1, 3, "2292-IH-000142"),
]
sh.table(x1, y1, cells1, h=lambda r, c: 3.5 if r == 0 else (2.6 if c == 1 and r in (8, 9) else 3.0))
y2 = rows_y(y1[-1] - 8.0, [10] + [7] * 6)
cells2 = [
    (0, 1, 0, 3, "链轮参数表"),
    (1, 2, 0, 1, "齿数"), (1, 2, 1, 2, "Z"), (1, 2, 2, 3, "23"),
    (2, 3, 0, 1, "节距"), (2, 3, 1, 2, "P"), (2, 3, 2, 3, "88.9"),
    (3, 4, 0, 1, "滚子外径"), (3, 4, 1, 2, "d1"), (3, 4, 2, 3, "%%c53.98"),
    (4, 5, 0, 1, "量棒测量距"), (4, 5, 1, 2, "MR"), (4, 5, 2, 3, "705.33" + tol("0", "-0.3")),
    (5, 6, 0, 1, "量棒直径"), (5, 6, 1, 2, "dR"), (5, 6, 2, 3, "%%c53.98" + tol("+0.01", "0")),
    (6, 7, 0, 1, "齿形"), (6, 7, 1, 3, "按GB/T1243-2006"),
]
sh.table(x1, y2, cells2, h=lambda r, c: 3.5 if r == 0 else 3.0)

# ================================================================ 技术要求
text(P(445.2, 118.0), "技术要求", 5)
for i, s_ in enumerate([
    "1.零件毛坯锻造;",
    "2.未注倒角C1,未注圆角R3;",
    "3.热处理:整体调质,硬度HB277-331,链轮齿部硬度HRC52-60,淬硬层深度3mm-5mm。[B]",
    "4.内花键按Q/STB13.110.22(20°压力角渐开线花键)设计、制造与检验,齿形参照JIS D2001",
    "   (x=+0.8),齿面定心,齿面配合c,插齿加工;",
    "5.花键齿槽宽用圆棒测跨距M检验(圆棒%%c5.0,削边后4.2),并用花键综合通规检验,",
    "   通规应能自由通过;",
    "6.花键齿顶倒角C0.2,齿根圆角R0.5,齿面不得有毛刺、碰伤。",
]):
    text(P(398.3, 110.0 - i * 6.0), s_, 3.5, align=TextEntityAlignment.MIDDLE_LEFT, width=0.8)

# ================================================================ 标题栏 (原图格式, 180×45)
BX = 404.0
pline([P(BX, 10), P(584, 10), P(584, 55), P(BX, 55)], "图框", closed=True)
for xx in (464.0, 524.0):
    line(P(xx, 10), P(xx, 55), "图框")
for j in range(1, 9):
    line(P(BX, 10 + 5 * j), P(464, 10 + 5 * j), "图框细" if j != 4 else "图框")
for xx in (411.0, 418.0, 438.0, 454.0):
    line(P(xx, 30), P(xx, 55), "图框细")
for xx in (418.0, 434.5, 449.0):
    line(P(xx, 10), P(xx, 30), "图框细")
for xx, s in ((407.5, "标记"), (414.5, "处数"), (428.0, "更改文件号"), (446.0, "签字"), (459.0, "日期")):
    text(P(xx, 32.5), s, 2.2)
for j, (a, b) in enumerate((("设计", "工艺审查"), ("绘图", "标准审查"), ("校对", "审定"),
                            ("主管设计", "日期"))):
    yy = 27.5 - 5 * j
    text(P(411.0, yy), a, 2.2)
    text(P(441.75, yy), b, 2.2)
line(P(464, 35), P(524, 35), "图框")
line(P(464, 23.2), P(524, 23.2), "图框细")
for xx in (479.1, 494.3, 509.5):
    line(P(xx, 23.2), P(xx, 35), "图框细")
line(P(479.1, 10), P(479.1, 23.2), "图框细")
line(P(499.3, 10), P(499.3, 23.2), "图框细")
text(P(494.0, 45.0), "链轮", 7)
mtext(P(471.5, 29.1), r"表面\P处理", 2.8)
mtext(P(501.9, 29.1), r"重要度\P分 级", 2.8)
text(P(471.5, 16.6), "材料", 3.5)
text(P(511.6, 16.6), "42CrMo", 5)
line(P(524, 40), P(584, 40), "图框")
line(P(524, 35), P(584, 35), "图框细")
line(P(524, 29), P(584, 29), "图框细")
line(P(524, 23.2), P(584, 23.2), "图框细")
for xx in (539.0, 554.0, 573.0):
    line(P(xx, 23.2), P(xx, 40), "图框细")
text(P(554.0, 47.5), "2292-IH-000139", 7)
for xx, s in ((531.5, "阶段标记"), (546.5, "版本号"), (563.5, "重  量"), (578.5, "比例")):
    text(P(xx, 37.5), s, 2.2)
for xx, s, hh in ((531.5, "S", 2.8), (546.5, "A.4", 2.8), (563.5, "119.565", 3.0),
                  (578.5, "1:3", 3.5)):
    text(P(xx, 32.0), s, hh)
for xx, s in ((531.5, "共"), (546.5, "张"), (563.5, "第"), (578.5, "张")):
    text(P(xx, 26.1), s, 2.8)

# ================================================================ 输出
if __name__ == "__main__":
    from PIL import Image

    iso_path = os.path.join(HERE, ISO_NAME)
    if "--no-iso" not in sys.argv or not os.path.exists(iso_path):
        import iso_render
        iso_render.render(iso_path)
    # 轴测图: 置于原图位置 (497..559, 139..210), 保持长宽比
    iw, ih = Image.open(iso_path).size
    bw, bh = 62.0, 71.0
    sc = min(bw / iw, bh / ih)
    sh.image(ISO_NAME, P(497.0 + (bw - iw * sc) / 2, 139.0 + (bh - ih * sc) / 2),
             (iw * sc * K, ih * sc * K), (iw, ih))
    sh.save(OUT_BASE + ".dxf")
    if "--no-preview" not in sys.argv:
        sh.render_preview(OUT_BASE, W, H, dpi=220)
    print(f"saved {OUT_BASE}.dxf")
