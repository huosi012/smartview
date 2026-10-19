# -*- coding: utf-8 -*-
"""结施-04 基础配筋图及钢筋表。"""
import math

from geom import *  # noqa: F401,F403
from s02_plan import inner_outline, outer_outline

# ---------------- 钢筋表数据 ----------------
LA = 33          # la = 33d（C35, HRB400，取整）
LL = 46          # ll = 1.4la（同一区段搭接率≤50%）


def lap(d):
    return int(math.ceil(LL * d / 10.0) * 10)


def raft_x_len(d=14):
    one = (X_RIGHT - X_LEFT) - 2 * 40 + 2 * 15 * d
    nl = math.ceil(one / 9000.0) - 1
    return one + nl * lap(d)


Q1_LEN = 2 * (3825 + 4200 + 4200 + 3825) + 6 * (2 * 350 + 1200) + 4 * (350 + 1000)

# (编号, 构件, 简图类型, 简图参数, 直径, 间距说明, 单根长mm 或 None, 根数, 总长m 指定或 None)
BARS = [
    ("1", "底板上层X向", "U", (21000, 210), 14, "@200", raft_x_len(), 19, None),
    ("2", "底板下层X向", "U", (21000, 210), 14, "@200", raft_x_len(), 19, None),
    ("3", "底板上层Y向", "U", (3520, 210), 14, "@200", 3940, 106, None),
    ("4", "底板下层Y向", "U", (3520, 210), 14, "@200", 3940, 106, None),
    ("5", "ZL-1底筋", "U", (4620, 300), 20, "7根/梁", 5220, 21, None),
    ("6", "ZL-1顶筋", "U", (4620, 300), 20, "7根/梁", 5220, 21, None),
    ("7", "ZL-1腰筋", "I", (4620,), 14, "G4/梁", 4620, 12, None),
    ("8", "ZL-1外箍", "HOOP", (1110, 710), 10, "@150", 3878, 96, None),
    ("9", "ZL-1内箍", "HOOP", (390, 710), 10, "@150", 2438, 96, None),
    ("10", "ZL-2底筋", "U", (4620, 300), 20, "9根/梁", 5220, 18, None),
    ("11", "ZL-2顶筋", "U", (4620, 300), 20, "9根/梁", 5220, 18, None),
    ("12", "ZL-2腰筋", "I", (4620,), 14, "G4/梁", 4620, 8, None),
    ("13", "ZL-2外箍", "HOOP", (1510, 710), 10, "@150", 4678, 64, None),
    ("14", "ZL-2内箍", "HOOP", (400, 710), 10, "@150", 2458, 128, None),
    ("15", "Q1/Q3竖向筋", "UCAP", (720, 140, 150), 12, "@200双面", 1010, 500, None),
    ("16", "Q1/Q3水平筋", "I", (48900,), 12, "@200双面", None, 6, round(6 * Q1_LEN * 1.10 / 1000.0, 1)),
    ("17", "Q2竖向筋", "L2", (1200, 210, 210), 14, "@200双面", 1620, 96, None),
    ("18", "Q2水平筋", "U", (4640, 180), 12, "@200双面", 5000, 12, None),
    ("19", "Q2拉筋", "TIE", (440,), 8, "@400×400", 640, 48, None),
    ("20", "YB-1纵向筋", "U", (6100, 180), 12, "@150双层", 6460, 100, None),
    ("21", "YB-1横向筋", "U", (3520, 180), 12, "@150双层", 3880, 168, None),
    ("22", "集水坑洞边附加筋", "I", (1340,), 14, "2根/边", 1340, 16, None),
    ("23", "底板马凳筋", "CHAIR", (300, 250), 12, "@1000×1000", 850, 80, None),
]


def bar_rows():
    rows = []
    tot = {}
    for no, part, shp, prm, d, sp, L1, n, Lt in BARS:
        if Lt is None:
            Lt = round(L1 * n / 1000.0, 1)
        w = round(Lt * KG[d], 1)
        tot[d] = tot.get(d, 0.0) + w
        rows.append((no, part, shp, prm, d, sp, L1, n, Lt, w))
    return rows, tot


# ---------------- 简图 ----------------
def sketch(p, x, y, w, shp, prm):
    """在钢筋表单元格内绘制钢筋简图（图纸坐标，x,y 为单元格左下角，w 宽，行高 SCHED_RH）。
    所有图线和文字限制在格内上下各留约 1mm 的范围内，避免压线。"""
    x1, x2 = x + 6, x + w - 6
    xm = (x1 + x2) / 2
    lw = "S-REBAR"
    th = 1.8
    if shp == "U":
        yb = y + 2.0
        p.pl([(x1, yb + 3.2), (x1, yb), (x2, yb), (x2, yb + 3.2)], lw)
        p.text(xm, yb + 0.5, str(prm[0]), th, "BC")
        p.text(x1 - 0.8, yb + 1.6, str(prm[1]), th, "MR")
    elif shp == "I":
        yb = y + 2.2
        p.line((x1, yb), (x2, yb), lw)
        p.text(xm, yb + 0.6, str(prm[0]) if prm[0] < 40000 else "通长", th, "BC")
    elif shp == "HOOP":
        xa, xb, ya, yt = x1 + 10, x2 - 10, y + 1.6, y + 5.8
        p.rect(xa, ya, xb, yt, lw)
        p.line((xa, yt), (xa + 2.2, yt - 1.8), lw)
        p.text(xm + 1.0, (ya + yt) / 2, str(prm[0]), th, "MC")
        p.text(xb + 1.0, (ya + yt) / 2, str(prm[1]), th, "ML")
    elif shp == "UCAP":
        ya, yt = y + 1.6, y + 5.8
        p.pl([(x1 + 4, ya), (x1 + 8, ya), (x1 + 8, yt), (x1 + 14, yt)], lw)
        p.text(x1 + 16, (ya + yt) / 2, f"{prm[0]}+{prm[1]}+{prm[2]}", th, "ML")
    elif shp == "L2":
        ya, yt = y + 1.6, y + 5.8
        p.pl([(x1 + 4, yt), (x1 + 8, yt), (x1 + 8, ya), (x1 + 12, ya)], lw)
        p.text(x1 + 14, (ya + yt) / 2, f"{prm[1]}+{prm[0]}+{prm[2]}", th, "ML")
    elif shp == "TIE":
        yb = y + 2.2
        p.pl([(x1 + 10, yb + 1.6), (x1 + 8, yb), (x2 - 8, yb), (x2 - 10, yb + 1.6)], lw)
        p.text(xm, yb + 0.6, str(prm[0]), th, "BC")
    elif shp == "CHAIR":
        ya, yt = y + 1.4, y + 5.8
        p.pl([(x1 + 6, ya), (x1 + 6, yt), (x2 - 6, yt), (x2 - 6, ya)], lw)
        p.text(xm, (ya + yt) / 2 - 0.3, f"{prm[1]}(高{prm[0]})", th, "MC")


SCHED_RH = 8.0


def draw_schedule(p, x, ytop):
    rows, tot = bar_rows()
    cols = [11, 30, 54, 13, 22, 20, 14, 18, 20]
    head = ["编号", "构件", "钢筋简图", "规格", "间距/根数", "单根长(mm)", "根数", "总长(m)", "重量(kg)"]
    rh = SCHED_RH
    W = sum(cols)
    p.text(x + W / 2, ytop + 6, "钢 筋 表", 4.5, "BC")
    data = [head]
    for no, part, shp, prm, d, sp, L1, n, Lt, w in rows:
        data.append([no, part, "", f"C{d}", sp, str(L1) if L1 else "—", str(n), f"{Lt:.1f}",
                     f"{w:.1f}"])
    yb = p.table(x, ytop, cols, data, row_h=rh, h=2.6)
    for i, r in enumerate(rows):
        yc = ytop - rh * (i + 1) - rh
        sketch(p, x + cols[0] + cols[1], yc, cols[2], r[2], r[3])
    # 合计
    ds = sorted(tot)
    hdr = ["规格"] + [f"C{d}" for d in ds] + ["合计"]
    vals = ["重量(kg)"] + [f"{tot[d]:.0f}" for d in ds] + [f"{sum(tot.values()):.0f}"]
    cw = [W - 18 * (len(ds) + 1)] + [18] * (len(ds) + 1)
    p.table(x, yb - 4, cw, [hdr, vals], row_h=rh, h=2.6)
    return yb - 4 - 2 * rh, tot


# ---------------- 底板配筋平面 ----------------
def raft_plan(v):
    v.rect(X_LEFT, -Y_WALL, X_RIGHT, Y_WALL, "S-CONC")
    v.pl(outer_outline(), "S-THIN", closed=True)
    v.pl(inner_outline(), "S-THIN", closed=True)
    for x1, x2, nm in BEAMS:
        v.rect(x1, -Y_OUT, x2, Y_OUT, "S-HIDE")
        v.text((x1 + x2) / 2, 0, nm, 3.0, "MC", rot=90)
    # 代表钢筋：X 向
    xa, xb = X_LEFT + 40, X_RIGHT - 40
    for y, top, lbl in ((-700, False, "② C14@200(下层)"), (700, True, "① C14@200(上层)")):
        hk = -210 if top else 210
        v.pl([(xa, y + hk), (xa, y), (xb, y), (xb, y + hk)], "S-REBAR")
        v.text(12500, y + (150 if not top else -150), lbl, 3.0, "BC" if not top else "TC")
    # 代表钢筋：Y 向
    ya, yb = -Y_WALL + 40, Y_WALL - 40
    for x, top, lbl in ((2500, False, "④ C14@200(下层)"), (3300, True, "③ C14@200(上层)")):
        hk = -210 if top else 210
        v.pl([(x + hk, ya), (x, ya), (x, yb), (x + hk, yb)], "S-REBAR")
        v.text(x + (-180 if not top else 180), 0, lbl, 3.0, "BC" if not top else "TC", rot=90)
    # 分布范围线
    for x in (7200, 7600):
        v.line((x, -Y_WALL + 40), (x, Y_WALL - 40), "S-THIN")
        for yy in (-Y_WALL + 40, Y_WALL - 40):
            v.line((x - 60, yy - 60), (x + 60, yy + 60), "S-THIN")
    # 集水坑
    for s in (1, -1):
        x1, x2, y1, y2 = SUMP
        v.rect(x1, s * y1, x2, s * y2, "S-THIN")
    v.leader([(SUMP[1], SUMP[3]), (AX[2] + 1300, 2900)], "洞边每侧附加2C14", h=2.8, side="R", marks=["22"])
    # 尺寸
    v.chainh([X_LEFT] + [b for x1, x2, n in BEAMS for b in (x1, x2)][1:-1] + [X_RIGHT], -Y_OUT, -3000,
             ext=3)
    v.dimh(X_LEFT, X_RIGHT, -Y_OUT, -3500, ext=3)
    v.chainv([-Y_OUT, -Y_WALL, Y_WALL, Y_OUT], X_LEFT, -1300, ext=3)


# ---------------- ZL-1 截面 ----------------
def stirrup(v, x1, z1, x2, z2, hook=True):
    v.rect(x1, z1, x2, z2, "S-REBAR")
    if hook:
        d = 60
        v.line((x1, z2), (x1 + d, z2 - d), "S-REBAR")
        v.line((x1 + 25, z2), (x1 + d + 25, z2 - d), "S-REBAR")


def zl1_section(v):
    zt, zb = Z_CAP, Z_BEAM_B
    body = [(-1000, Z_RAFT_B), (-600, Z_RAFT_B), (-600, zb), (600, zb), (600, Z_RAFT_B),
            (1000, Z_RAFT_B), (1000, zt), (-1000, zt)]
    v.pl(body, "S-CONC", closed=False)
    v.line((-1000, zt), (-1000, Z_RAFT_B), "S-THIN")
    v.break_line((1000, Z_RAFT_B - 60), (1000, zt + 60))
    v.break_line((-1000, Z_RAFT_B - 60), (-1000, zt + 60))
    v.line((-1000, zt), (1000, zt), "S-CONC")
    v.rect(-700, zb - T_CUSH, 700, zb, "S-THIN")
    v.hatch([(-700, zb - T_CUSH), (700, zb - T_CUSH), (700, zb), (-700, zb)], "AR-CONC")
    # 预埋板
    v.hatch([(-250, zt), (250, zt), (225, Z_PLATE_B), (-225, Z_PLATE_B)], "AR-SAND")
    v.pl([(-250, zt), (250, zt), (225, Z_PLATE_B), (-225, Z_PLATE_B)], "S-THIN", closed=True)
    v.hatch([(-200, Z_PLATE_B), (200, Z_PLATE_B), (200, Z_PLATE), (-200, Z_PLATE)], "SOLID", "S-STEEL")
    # 箍筋
    stirrup(v, -555, zb + 55, 555, zt - 35)
    stirrup(v, -195, zb + 55, 195, zt - 35, hook=False)
    # 纵筋
    for i in range(7):
        x = -535 + i * (1070 / 6)
        v.dot((x, zt - 55), 1.0, real_d=20)
        v.dot((x, zb + 75), 1.0, real_d=20)
    for x in (-535, 535):
        for z in (-750, -950):
            v.dot((x, z), 0.8, real_d=14)
    # 底板筋
    v.line((-1000, zt - 72), (1000, zt - 72), "S-REBAR")
    v.line((-1000, -679), (1000, -679), "S-REBAR")
    for x in (-900, -700, 700, 900):
        v.dot((x, zt - 51), 0.7, real_d=14)
        v.dot((x, -693), 0.7, real_d=14)
    # 尺寸
    v.chainh([-1000, -600, 600, 1000], zb, zb - 350, ["", "1200", ""], ext=3)
    v.chainv([zb, Z_RAFT_B, zt], 1000, 1250, ext=3)
    v.dimv(zb, zt, -600, -1250, ext=3)
    v.dimv(zb - T_CUSH, zb, -700, -1250, None, ext=3)
    # 标注
    v.leader([(0, zt - 55), (300, zt + 350)], "7C20", h=2.8, side="R", marks=['6'])
    v.leader([(250, zb + 75), (450, zb - 500)], "7C20", h=2.8, side="R", marks=['5'])
    v.leader([(535, -850), (1550, -700)], "G4C14", h=2.8, side="R", marks=['7'])
    v.leader([(-555, -900), (-1380, -1150)], "C10@150(4)", h=2.8, side="L", marks=["8", "9"])
    v.leader([(-800, zt - 72), (-1300, zt + 350)], "C14@200", h=2.8, side="L", marks=['1', '3'])
    v.leader([(-800, -686), (-1350, -950)], "C14@200", h=2.8, side="L", marks=['2', '4'])
    v.elev(800, zt, "-0.450", "R")
    v.elev(800, zb, "-1.250", "R", down=True)


# ---------------- ZL-1 立面 ----------------
def zl1_elev(v):
    zt, zb = Z_CAP, Z_BEAM_B
    body = [(-Y_OUT, zb), (Y_OUT, zb), (Y_OUT, Z_TOP), (Y_OPEN_OUT + REB, Z_TOP),
            (Y_OPEN_OUT + REB, Z_SEAT), (Y_OPEN_OUT, Z_SEAT), (Y_OPEN_OUT, zt),
            (-Y_OPEN_OUT, zt), (-Y_OPEN_OUT, Z_SEAT), (-Y_OPEN_OUT - REB, Z_SEAT),
            (-Y_OPEN_OUT - REB, Z_TOP), (-Y_OUT, Z_TOP)]
    v.pl(body, "S-CONC", closed=True)
    for s in (1, -1):
        a, b = sorted((s * 1100, s * 1500))
        v.hatch([(a, Z_PLATE_B), (b, Z_PLATE_B), (b, Z_PLATE), (a, Z_PLATE)], "SOLID", "S-STEEL")
        v.pl([(a - PAD, zt), (b + PAD, zt), (b + PAD - 25, Z_PLATE_B), (a - PAD + 25, Z_PLATE_B)],
             "S-THIN", closed=True)
    ya, yb = -Y_OUT + 40, Y_OUT - 40
    v.pl([(ya, zt - 55 - 300), (ya, zt - 55), (yb, zt - 55), (yb, zt - 55 - 300)], "S-REBAR")
    v.pl([(ya + 15, zb + 75 + 300), (ya + 15, zb + 75), (yb - 15, zb + 75), (yb - 15, zb + 75 + 300)],
         "S-REBAR")
    for z in (-750, -950):
        v.line((ya + 30, z), (yb - 30, z), "S-REBAR")
    y = -Y_OUT + 50
    while y <= Y_OUT - 50 + 1:
        v.line((y, zb + 55), (y, zt - 35), "S-THIN")
        y += 150
    for s in (1, -1):
        for yy in (2185, 2315):
            v.pl([(s * (yy - 160), zb + 75), (s * yy, zb + 75), (s * yy, Z_TOP - 30)], "S-REBAR")
        v.line((s * 2185, Z_TOP - 30), (s * 2315, Z_TOP - 30), "S-REBAR")
    v.chainh([-Y_OUT, -Y_OPEN_OUT, -1300, 1300, Y_OPEN_OUT, Y_OUT], zb, zb - 350,
             [None, None, "2600※", None, None], ext=3)
    v.dimh(-Y_OUT, Y_OUT, zb, zb - 700, ext=3)
    v.leader([(-1700, zt - 55), (-1900, 400)], "7C20(两端弯折15d)", h=2.6, side="L", marks=['6'])
    v.leader([(700, zb + 75), (2500, zb - 150)], "7C20(两端弯折15d)", h=2.6, side="R", marks=['5'])
    v.leader([(0, -860), (300, 400)], "C10@150(4)", h=2.6, side="R", marks=['8', '9'])
    v.leader([(Y_OUT - 35, -200), (Y_OUT + 500, 400)], "C12@200", h=2.6, side="R", marks=['15'])


# ---------------- ZL-2 + Q2 截面 ----------------
def zl2_section(v):
    zt, zb = Z_CAP, Z_BEAM_B
    body = [(1500, Z_RAFT_B), (1100, Z_RAFT_B), (1100, zb), (X_LEFT, zb), (X_LEFT, Z_LEDGE),
            (X_LEDGE_L, Z_LEDGE), (X_LEDGE_L, Z_TOP), (0, Z_TOP), (0, zt), (1500, zt)]
    v.pl(body, "S-CONC")
    v.break_line((1500, Z_RAFT_B - 60), (1500, zt + 60))
    v.rect(X_LEFT - 100, zb - T_CUSH, 1200, zb, "S-THIN")
    v.hatch([(X_LEFT - 100, zb - T_CUSH), (1200, zb - T_CUSH), (1200, zb), (X_LEFT - 100, zb)],
            "AR-CONC")
    # 引道板
    ap = [(-1500, Z_LEDGE - 3), (-320, Z_LEDGE), (-320, Z_TOP), (-1500, Z_TOP - 10)]
    v.pl([ap[3], ap[2], ap[1], ap[0]], "S-CONC")
    v.break_line((-1500, Z_LEDGE - 60), (-1500, Z_TOP + 60))
    v.line((-1500, Z_LEDGE + 35), (-360, Z_LEDGE + 35), "S-REBAR")
    v.line((-1500, Z_TOP - 40), (-360, Z_TOP - 35), "S-REBAR")
    v.text(-900, Z_TOP + 120, "YB-1", 2.6, "BC")
    # 预埋件
    v.pl([(-75, Z_TOP), (0, Z_TOP), (0, Z_TOP - 75)], "S-STEEL", width=0.5)
    v.pl([(-30, Z_TOP - 20), (-170, Z_TOP - 160), (-205, Z_TOP - 125)], "S-STEEL")
    v.hatch([(-16, Z_LIMIT_B), (0, Z_LIMIT_B), (0, Z_LIMIT_T), (-16, Z_LIMIT_T)], "SOLID", "S-STEEL")
    v.pl([(-16, -50), (-216, -50), (-216, -100)], "S-STEEL")
    v.hatch([(0, Z_PLATE_B), (400, Z_PLATE_B), (400, Z_PLATE), (0, Z_PLATE)], "SOLID", "S-STEEL")
    v.pl([(0, zt), (450, zt), (425, Z_PLATE_B), (0, Z_PLATE_B)], "S-THIN", closed=True)
    # 箍筋、纵筋
    stirrup(v, X_LEFT + 45, zb + 55, 1100 - 45, zt - 35)
    stirrup(v, -115, zb + 55, 295, zt - 35, hook=False)
    stirrup(v, 585, zb + 55, 985, zt - 35, hook=False)
    for i in range(9):
        x = X_LEFT + 65 + i * (1470 / 8)
        v.dot((x, zt - 55), 1.0, real_d=20)
        v.dot((x, zb + 75), 1.0, real_d=20)
    for x in (X_LEFT + 65, 1100 - 65):
        for z in (-750, -950):
            v.dot((x, z), 0.8, real_d=14)
    # 端墙钢筋
    xi = -37
    v.pl([(xi + 210, zb + 75), (xi, zb + 75), (xi, Z_TOP - 30), (X_LEDGE_L + 37, Z_TOP - 30),
          (X_LEDGE_L + 37, Z_TOP - 30 - 210)], "S-REBAR")
    xo = X_LEFT + 37
    v.pl([(xo + 210, zb + 75), (xo, zb + 75), (xo, Z_LEDGE - 30), (X_LEDGE_L + 37, Z_LEDGE - 30)],
         "S-REBAR")
    v.pl([(X_LEDGE_L + 37, -700), (X_LEDGE_L + 37, Z_TOP - 30)], "S-REBAR")
    for z in (-100, -300):
        v.dot((xi - 14, z), 0.8, real_d=12)
        if z > Z_LEDGE:
            v.dot((X_LEDGE_L + 51, z), 0.8, real_d=12)
        else:
            v.dot((xo + 14, z), 0.8, real_d=12)
    v.line((xo + 14, -300), (xi - 14, -300), "S-THIN")
    # 底板筋
    v.pl([(1500, zt - 72), (X_LEFT + 40, zt - 72), (X_LEFT + 40, zt - 72 - 210)], "S-REBAR")
    v.pl([(1500, -679), (X_LEFT + 55, -679), (X_LEFT + 55, -679 + 210)], "S-REBAR")
    # 尺寸
    v.chainh([X_LEFT, X_LEDGE_L, 0, 1100], zb, zb - 350, ext=3)
    v.dimh(X_LEFT, 1100, zb, zb - 700, ext=3)
    v.chainv([zb, Z_RAFT_B, zt, Z_PLATE, Z_TOP], 1500, 1800, [None, None, None, "450※"], ext=3)
    v.chainv([Z_LEDGE, Z_TOP], X_LEFT, -1700, ext=3)
    # 标注
    v.leader([(300, zt - 55), (700, 450)], "9C20", h=2.6, side="R", marks=['11'])
    v.leader([(600, zb + 75), (900, zb - 300)], "9C20", h=2.6, side="R", marks=['10'])
    v.leader([(1035, -850), (2100, -700)], "G4C14", h=2.6, side="R", marks=['12'])
    v.leader([(X_LEFT + 45, -1000), (-1200, -1150)], "C10@150(6)", h=2.6, side="L", marks=['13', '14'])
    v.leader([(xi, -250), (-900, -600)], "C14@200(双面)", h=2.6, side="L", marks=['17'])
    v.leader([(xi - 14, -100), (-1100, 450)], "C12@200(双面)", h=2.6, side="L", marks=['18'])
    v.leader([(-200, -300), (-1000, -850)], "C8@400×400", h=2.6, side="L", marks=['19'])
    v.leader([(-40, Z_TOP), (300, 500)], "M-3", 2.6, "R")
    v.leader([(-8, -100), (250, 650)], "M-2", 2.6, "R")
    v.leader([(200, Z_PLATE), (900, 150)], "M-1", 2.6, "R")


# ---------------- Q1 截面 ----------------
def q1_section(v):
    zg = z_gutter(5000)
    zf = z_floor(GUT_Y[0])
    zf9 = z_floor(900)
    body = [(900, zf9), (GUT_Y[0], zf), (GUT_Y[0], zg), (B_HALF, zg), (B_HALF, Z_TOP),
            (Y_WALL, Z_TOP), (Y_WALL, Z_RAFT_B), (900, Z_RAFT_B)]
    v.pl(body, "S-CONC")
    v.break_line((900, Z_RAFT_B - 60), (900, zf9 + 60))
    v.rect(900, Z_RAFT_B - T_CUSH, Y_WALL + 100, Z_RAFT_B, "S-THIN")
    v.hatch([(900, Z_RAFT_B - T_CUSH), (Y_WALL + 100, Z_RAFT_B - T_CUSH), (Y_WALL + 100, Z_RAFT_B),
             (900, Z_RAFT_B)], "AR-CONC")
    # 底板筋（排水沟处上层筋下弯）
    zt1 = -487
    zt2 = zg - 37
    v.pl([(900, zt1), (1380, zt1), (1450, zt2), (Y_WALL - 40, zt2), (Y_WALL - 40, zt2 - 180)], "S-REBAR")
    v.pl([(900, -693), (Y_WALL - 40, -693), (Y_WALL - 40, -693 + 210)], "S-REBAR")
    for y in (1000, 1200, 1400):
        v.dot((y, zt1 - 14), 0.7, real_d=14)
        v.dot((y, -679), 0.7, real_d=14)
    v.dot((1600, zt2 - 14), 0.7, real_d=14)
    v.dot((1600, -679), 0.7, real_d=14)
    # 墙筋
    yi, yo = B_HALF + 36, Y_WALL - 36
    v.pl([(yi - 150, -700), (yi, -700), (yi, Z_TOP - 30), (yo, Z_TOP - 30), (yo, -700), (yo - 150, -700)],
         "S-REBAR")
    for z in (-100, -300):
        v.dot((yi + 12, z), 0.8, real_d=12)
        v.dot((yo - 12, z), 0.8, real_d=12)
    v.dot((yi + 12, Z_TOP - 60), 0.8, real_d=12)
    v.dot((yo - 12, Z_TOP - 60), 0.8, real_d=12)
    # 尺寸
    v.chainh([GUT_Y[0], B_HALF, Y_WALL], Z_RAFT_B, Z_RAFT_B - 300, ext=3)
    v.chainv([Z_RAFT_B, Z_CAP, Z_TOP], Y_WALL, Y_WALL + 250, ext=3)
    # 标注
    v.leader([(yi, -200), (1100, 200)], "C12@200(双面)", h=2.6, side="L", marks=['15'])
    v.leader([(yo - 12, -300), (2400, 250)], "C12@200(双面)", h=2.6, side="R", marks=['16'])
    v.leader([(1650, zt2), (2400, -1000)], "排水沟处上层筋下弯", 2.6, "R")


def yb1_plan(v):
    """引道板配筋平面（局部坐标：x 沿行车方向 0~6180，y 横向 ±1800）。"""
    Lb, Bh = APP[0][1] - APP[0][0], APP_Y
    v.rect(0, -Bh, Lb, Bh, "S-CONC")
    v.pl([(40, 600 + 180), (40, 600), (Lb - 40, 600), (Lb - 40, 600 + 180)], "S-REBAR")
    v.pl([(1500 - 180, -Bh + 40), (1500, -Bh + 40), (1500, Bh - 40), (1500 - 180, Bh - 40)], "S-REBAR")
    v.text(Lb / 2, 650, "C12@150(上下层)", 2.6, "BC")
    v.text(1450, 0, "C12@150(上下层)", 2.6, "BC", rot=90)
    v.leader([(Lb / 2 - 600, 600), (Lb / 2 - 900, 1300)], "纵向筋", h=2.4, side="L", marks=["20"])
    v.leader([(1500, -900), (2300, -1300)], "横向筋", h=2.4, side="R", marks=["21"])
    v.text(Lb - 150, 0, "端墙侧", 2.4, "MC", rot=90)
    v.dimh(0, Lb, -Bh, -Bh - 400, ext=3)
    v.dimv(-Bh, Bh, 0, -400, ext=3)


def yb1_section(v):
    """引道板与端墙搭接处剖面（局部：x=X，0 为端墙内侧面；y=Z）。"""
    x0 = -1700
    top0 = Z_TOP - Z_TOP * (APP[0][1] - x0) / (APP[0][1] - APP[0][0])
    slab = [(x0, top0 - APP_T), (-320, Z_LEDGE), (-320, Z_TOP), (x0, top0)]
    v.pl([slab[3], slab[2], slab[1], slab[0]], "S-CONC")
    v.break_line((x0, top0 - APP_T - 60), (x0, top0 + 60))
    v.pl([(X_LEFT, -450), (X_LEFT, Z_LEDGE), (X_LEDGE_L, Z_LEDGE), (X_LEDGE_L, Z_TOP), (0, Z_TOP),
          (0, -450)], "S-CONC")
    v.break_line((X_LEFT - 60, -450), (60, -450))
    v.hatch([(x0, top0 - APP_T - 300), (X_LEFT, Z_LEDGE - 300), (X_LEFT, Z_LEDGE), (x0, top0 - APP_T)],
            "ZJ-GRAVEL")
    v.line((x0, top0 - APP_T - 300), (X_LEFT, Z_LEDGE - 300), "S-THIN")
    v.pl([(x0, top0 - 36), (-360, Z_TOP - 36), (-360, Z_TOP - 36 - 150)], "S-REBAR")
    v.pl([(x0, top0 - APP_T + 36), (-360, Z_LEDGE + 36), (-360, Z_LEDGE + 36 + 150)], "S-REBAR")
    for x in (-1600, -1450, -1300, -1150, -1000, -850, -700, -550, -400):
        tt = Z_TOP - Z_TOP * (APP[0][1] - x) / (APP[0][1] - APP[0][0])
        v.dot((x, tt - 48), 0.6, real_d=12)
        v.dot((x, tt - APP_T + 48), 0.6, real_d=12)
    v.chainh([X_LEFT, -320, X_LEDGE_L, 0], Z_LEDGE, Z_LEDGE - 450, ["180", "20", "300"], ext=3)
    v.dimv(Z_LEDGE, Z_TOP, -320, -1950 + 0, "250", ext=3)
    v.leader([(-310, Z_TOP - 10), (300, 300)], "20宽缝,聚氨酯密封胶", h=2.4, side="R")
    v.leader([(-420, Z_LEDGE + 2), (-650, -900)], "油毡滑动层一道", h=2.4, side="L")
    v.leader([(-1200, Z_LEDGE - 200), (-1600, -650)], "300厚级配砂石基层", h=2.4, side="L")


REBAR_NOTES = [
    "配筋说明：",
    "1. 图中“C”表示HRB400钢筋；混凝土C35 P6 F250。",
    "2. 保护层(最外层钢筋)：底板及墩梁底面50，底板顶面30，",
    "   墩梁侧面40，墙30，引道板30。",
    "3. la=33d，ll=46d(同一连接区段搭接率≤50%)；",
    "   接头应相互错开，宜设在受力较小处。",
    "4. 底板钢筋在墩梁内贯通；墩梁纵筋两端弯折15d。",
    "5. 墙竖向筋伸至底板(墩梁)底部钢筋处并弯折。",
    "6. 排水沟处底板及墩梁上层钢筋局部下弯(坡度≤1:6)，",
    "   沟底保护层不小于30。",
    "7. ③轴集水坑处洞边每侧附加2C14，伸过洞边la。",
    "8. 钢筋表长度为下料参考，以现场放样为准。",
]


def sheet_rebar(sh):
    p = sh.paper
    v = sh.view(80, 520, 50)
    raft_plan(v)
    p.detail_title(200, 434, None, "底板配筋平面图", "1:50", h=6.0)

    v2 = sh.view(130, 372, 30)
    zl1_elev(v2)
    p.detail_title(60, 292, None, "ZL-1 立面配筋图", "1:30", h=5.0)

    v3 = sh.view(340, 395, 20)
    zl1_section(v3)
    p.detail_title(318, 296, None, "ZL-1 截面", "1:20", h=5.0)

    v4 = sh.view(115, 215, 20)
    zl2_section(v4)
    p.detail_title(75, 98, None, "ZL-2及端墙Q2 截面", "1:20", h=5.0)

    v5 = sh.view(300, 230, 20)
    q1_section(v5)
    p.detail_title(318, 150, None, "侧墙Q1截面(Q3同)", "1:20", h=5.0)

    v6 = sh.view(458, 255, 50)
    yb1_plan(v6)
    v7 = sh.view(482, 150, 20)
    yb1_section(v7)
    p.detail_title(440, 98, None, "YB-1 引道板配筋", "1:50、1:20", h=5.0)

    yb, tot = draw_schedule(p, 622, 572)

    p.text_lines(622, yb - 6, REBAR_NOTES, 2.8, 1.65)
