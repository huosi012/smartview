# -*- coding: utf-8 -*-
"""结施-03 基础剖面图（1-1 纵剖面；2-2、3-3、4-4 横剖面）。"""
from geom import *  # noqa: F401,F403
from s02_plan import end_dims


def app_top(x):
    """引道板顶标高（左引道，X<=-320；右引道按对称取值）。"""
    if x > L / 2:
        x = L - x
    d = APP[0][1] - x
    return Z_TOP - Z_TOP * d / (APP[0][1] - APP[0][0])


def mirror_x(pts):
    return [(L - x, z) for x, z in reversed(pts)]


def mortar_plate(v, a, b, z_cap=Z_CAP, lo=None, hi=None):
    """传感器预埋板及水泥台（a, b 为板沿剖切方向的范围）。lo/hi 限制水泥台范围。"""
    m1, m2 = a - PAD, b + PAD
    if lo is not None:
        m1 = max(m1, lo)
    if hi is not None:
        m2 = min(m2, hi)
    pad = [(m1, z_cap), (m2, z_cap), (m2 - (0 if hi is not None and m2 == hi else 25), Z_PLATE_B),
           (m1 + (0 if lo is not None and m1 == lo else 25), Z_PLATE_B)]
    v.hatch(pad, "AR-SAND")
    v.pl(pad, "S-THIN", closed=True)
    pl = [(a, Z_PLATE_B), (b, Z_PLATE_B), (b, Z_PLATE), (a, Z_PLATE)]
    v.hatch(pl, "SOLID", "S-STEEL")
    v.pl(pl, "S-STEEL", closed=True)


def conc(v, loops):
    v.rc_hatch(loops)
    if loops and isinstance(loops[0][0], (int, float)):
        loops = [loops]
    for lp in loops:
        v.pl(lp, "S-CONC", closed=True)


def plain_conc(v, pts):
    v.hatch(pts, "AR-CONC")
    v.pl(pts, "S-THIN", closed=True)


def gravel(v, pts):
    v.hatch(pts, "ZJ-GRAVEL", rel=1.0)


def earth(v, pts):
    v.hatch(pts, "EARTH", "S-SOIL", angle=45)


# ======================================================================
def long_section(v):
    """1-1 纵剖面（Y=+1300，向 +Y 方向投射）。局部坐标 x=X, y=Z。"""
    # 混凝土断面
    body = [(X_LEFT, Z_BEAM_B)]
    for i, (x1, x2, nm) in enumerate(BEAMS):
        if i == 0:
            body += [(x2, Z_BEAM_B), (x2, Z_RAFT_B)]
        elif i == len(BEAMS) - 1:
            body += [(x1, Z_RAFT_B), (x1, Z_BEAM_B), (x2, Z_BEAM_B)]
        else:
            body += [(x1, Z_RAFT_B), (x1, Z_BEAM_B), (x2, Z_BEAM_B), (x2, Z_RAFT_B)]
    body += [(X_RIGHT, Z_LEDGE), (X_LEDGE_R, Z_LEDGE), (X_LEDGE_R, Z_TOP), (L, Z_TOP),
             (L, Z_CAP), (0, Z_CAP), (0, Z_TOP), (X_LEDGE_L, Z_TOP), (X_LEDGE_L, Z_LEDGE),
             (X_LEFT, Z_LEDGE)]
    conc(v, body)
    # 传感器预埋板
    for (a, b) in PLATES_X:
        mortar_plate(v, a, b, lo=0, hi=L)
    # 护边角钢、限位板（示意）
    for xs, sg in ((0, -1), (L, 1)):
        v.pl([(xs + sg * 75, Z_TOP), (xs, Z_TOP), (xs, Z_TOP - 75)], "S-STEEL", width=0.35)
    # 引道板
    for x1, x2 in APP:
        pts = [(x1, app_top(x1) - APP_T), (x2, app_top(x2) - APP_T), (x2, app_top(x2)),
               (x1, app_top(x1))]
        conc(v, pts)
    # C15 垫层
    for x1, x2, nm in BEAMS:
        plain_conc(v, [(x1 - 100, Z_BEAM_B - T_CUSH), (x2 + 100, Z_BEAM_B - T_CUSH),
                       (x2 + 100, Z_BEAM_B), (x1 - 100, Z_BEAM_B)])
    for (a, b) in zip(BEAMS[:-1], BEAMS[1:]):
        plain_conc(v, [(a[1], Z_RAFT_B - T_CUSH), (b[0], Z_RAFT_B - T_CUSH),
                       (b[0], Z_RAFT_B), (a[1], Z_RAFT_B)])
    # 级配砂石
    zc = Z_BEAM_B - T_CUSH
    gravel(v, [(REPL_X[0], Z_REPL), (REPL_X[1], Z_REPL), (REPL_X[1], zc), (REPL_X[0], zc)])
    for (a, b) in zip(BEAMS[:-1], BEAMS[1:]):
        gravel(v, [(a[1], Z_BEAM_B), (a[1] + 100, Z_BEAM_B), (a[1] + 100, zc), (b[0] - 100, zc),
                   (b[0] - 100, Z_BEAM_B), (b[0], Z_BEAM_B), (b[0], Z_RAFT_B - T_CUSH),
                   (a[1], Z_RAFT_B - T_CUSH)])
    left_end = [(REPL_X[0], zc), (X_LEFT - 100, zc), (X_LEFT - 100, Z_BEAM_B), (X_LEFT, Z_BEAM_B),
                (X_LEFT, Z_LEDGE), (APP[0][1], Z_LEDGE),
                (REPL_X[0], app_top(REPL_X[0]) - APP_T)]
    gravel(v, left_end)
    gravel(v, mirror_x(left_end))
    app_l = [(APP_REPL[0][0], Z_APP_REPL), (REPL_X[0], Z_APP_REPL),
             (REPL_X[0], app_top(REPL_X[0]) - APP_T), (APP[0][0], app_top(APP[0][0]) - APP_T),
             (APP[0][0], 0), (APP_REPL[0][0], 0)]
    gravel(v, app_l)
    gravel(v, mirror_x(app_l))
    v.pl([(APP_REPL[0][0], 0), (APP_REPL[0][0], Z_APP_REPL), (REPL_X[0], Z_APP_REPL),
          (REPL_X[0], Z_REPL), (REPL_X[1], Z_REPL), (REPL_X[1], Z_APP_REPL),
          (APP_REPL[1][1], Z_APP_REPL), (APP_REPL[1][1], 0)], "S-HIDE2")
    # 原状土
    t = 300
    earth(v, [(REPL_X[0] - t, Z_REPL - t), (REPL_X[1] + t, Z_REPL - t), (REPL_X[1] + t, Z_APP_REPL - t),
              (APP_REPL[1][1] + t, Z_APP_REPL - t), (APP_REPL[1][1] + t, 0), (APP_REPL[1][1], 0),
              (APP_REPL[1][1], Z_APP_REPL), (REPL_X[1], Z_APP_REPL), (REPL_X[1], Z_REPL),
              (REPL_X[0], Z_REPL), (REPL_X[0], Z_APP_REPL), (APP_REPL[0][0], Z_APP_REPL),
              (APP_REPL[0][0], 0), (APP_REPL[0][0] - t, 0), (APP_REPL[0][0] - t, Z_APP_REPL - t),
              (REPL_X[0] - t, Z_APP_REPL - t)])
    # 地面线
    for xa, xb in ((APP_REPL[0][0] - 1500, APP[0][0]), (APP[1][1], APP_REPL[1][1] + 1500)):
        v.line((xa, 0), (xb, 0), "S-CONC")
    # 剖切面以远可见线：侧墙/检修口外墙顶，检修口边线
    v.line((0, Z_TOP), (L, Z_TOP), "S-THIN")
    for x in (800, 4625, 5425, 9625, 10425, 14625, 15425, 19250):
        v.line((x, Z_CAP), (x, Z_TOP), "S-THIN")
    # 秤台示意
    v.rect(25, -250, L - 25, Z_TOP - 8, "S-HIDE2")
    # 水位线、冻深线
    v.line((APP_REPL[0][0] - 300, Z_GW), (APP_REPL[1][1] + 1500, Z_GW), "S-WATER")
    v.line((APP_REPL[0][0] - 300, Z_FROST), (APP_REPL[1][1] + 1500, Z_FROST), "S-WATER")
    v.text(APP_REPL[0][0] - 200, Z_GW + 50, "抗浮设防水位134.500(绝对标高)", 2.5, "BL")
    v.text(APP_REPL[1][1] + 1400, Z_FROST + 80, "最大冻结深度线(2.80m)", 2.5, "BR")

    # 轴线
    for x, lb in zip(AX, AX_LABEL):
        v.line((x, 600), (x, -3700), "S-AXIS")
        v.line((x, -3700), (x, -4500), "S-THIN")
        v.axis_bubble(x, -4700, lb)
    # 尺寸
    end_dims(v, Z_REPL, -3600)
    xs2 = [X_LEFT] + [b for x1, x2, n in BEAMS for b in (x1, x2)][1:-1] + [X_RIGHT]
    v.chainh(xs2, Z_REPL, -4050, ext=3, avoid=AX)
    v.chainv([Z_REPL, Z_BEAM_B, Z_RAFT_B, Z_CAP, Z_TOP], X_LEFT, -8000, ext=3)
    v.chainv([Z_REPL, Z_APP_REPL, -250], APP_REPL[0][0], -8500, ext=3)
    v.dimv(Z_PLATE, Z_TOP, 0, 1600, "450※", ext=None)
    # 标高
    v.elev(2600, Z_TOP, "+0.050", "R")
    v.elev(2600, Z_CAP, "-0.450", "R")
    v.elev(AX[1] + 600, Z_PLATE, "-0.400", "R")
    v.elev(2600, Z_RAFT_B, "-0.750", "R", down=True)
    v.elev(AX[1] + 900, Z_BEAM_B, "-1.250", "R", down=True)
    v.elev(2600, Z_REPL, "-3.000", "R", down=True)
    v.elev(-7800, 0, "±0.000", "R")
    v.elev(-1500, Z_APP_REPL, "-1.500", "L", down=True)
    # 标注
    v.leader([(AX[2] + 300, -1000), (AX[2] + 1200, -1700)], "ZL-1(1200×800)", 2.8, "R")
    v.leader([(600, -1000), (1700, -1700)], "ZL-2(1600×800)", 2.8, "R")
    v.leader([(7300, -600), (7900, -1700)], "底板300厚", 2.8, "R")
    v.leader([(12500, -800), (13100, -1700)], "C15素混凝土垫层100厚", 2.8, "R")
    v.leader([(16500, -2300), (17100, -1700)], "级配砂石换填,压实系数≥0.97", 2.8, "R")
    v.leader([(-4000, -50), (-4600, 700)], "YB-1 引道板250厚,i=0.8%", 2.8, "L")
    v.leader([(L + 3000, -1000), (L + 3600, -1700)], "引道下换填(底-1.500)", 2.8, "R")
    v.leader([(AX[3], Z_PLATE), (AX[3] + 700, 700)], "M-1传感器预埋板(1:1水泥砂浆座浆)", 2.8, "R")
    v.leader([(6500, -250), (6000, 750)], "秤台(示意,以厂家为准)", 2.8, "L")
    v.text(-5300, -2600, "原状土", 2.8)
    v.index_mark(-1600, 900, "1", REF["detail"])
    v.line((-1350, 850), (-150, 50), "S-SYMB")


# ======================================================================
def cross_common(v, half=3500, ground_from=None):
    """横剖面公共部分：换填、原状土、地面线、水位/冻深线。"""
    v.pl([(-REPL_Y, 0), (-REPL_Y, Z_REPL), (REPL_Y, Z_REPL), (REPL_Y, 0)], "S-HIDE2")
    t = 300
    earth(v, [(-REPL_Y - t, Z_REPL - t), (REPL_Y + t, Z_REPL - t), (REPL_Y + t, 0), (REPL_Y, 0),
              (REPL_Y, Z_REPL), (-REPL_Y, Z_REPL), (-REPL_Y, 0), (-REPL_Y - t, 0)])
    gf = ground_from if ground_from is not None else Y_OUT
    for s in (1, -1):
        v.line((s * gf, 0), (s * (half + 200), 0), "S-CONC")
    v.line((-half - 200, Z_GW), (half + 200, Z_GW), "S-WATER")
    v.line((-half - 200, Z_FROST), (half + 200, Z_FROST), "S-WATER")
    v.text(-half - 150, Z_GW - 60, "抗浮设防水位", 2.2, "TL")
    v.text(-half - 150, Z_FROST + 60, "最大冻深线", 2.2, "BL")


def cross_gravel(v, foot):
    """foot：基础+垫层的外轮廓（自左下起，逆时针，覆盖至地面 0），返回换填区填充。"""
    pts = [(-REPL_Y, Z_REPL), (REPL_Y, Z_REPL), (REPL_Y, 0)] + foot + [(-REPL_Y, 0)]
    gravel(v, pts)


def section_22(v):
    """2-2 横剖面（③轴，X=10025）。局部 x=Y, y=Z。"""
    cross_common(v)
    sx1, sx2, sy1, sy2 = SUMP
    main = [(-Y_OUT, Z_BEAM_B), (Y_OUT, Z_BEAM_B), (Y_OUT, Z_PIPE), (sy2, Z_PIPE),
            (sy2, Z_SUMP), (sy1, Z_SUMP), (sy1, Z_CAP), (-sy1, Z_CAP), (-sy1, Z_SUMP),
            (-sy2, Z_SUMP), (-sy2, Z_PIPE), (-Y_OUT, Z_PIPE)]
    conc(v, main)
    zp2 = Z_PIPE + 160
    for s in (1, -1):
        up = [(sy2, zp2), (Y_OUT, zp2), (Y_OUT, Z_TOP), (Y_OPEN_OUT + REB, Z_TOP),
              (Y_OPEN_OUT + REB, Z_SEAT), (Y_OPEN_OUT, Z_SEAT), (Y_OPEN_OUT, Z_CAP), (sy2, Z_CAP)]
        conc(v, [(s * y, z) for y, z in up])
        # 排水管
        v.line((s * sy2, Z_PIPE), (s * 3700, Z_PIPE - 8), "S-THIN")
        v.line((s * sy2, zp2), (s * 3700, zp2 - 8), "S-THIN")
        # 盖板及加劲肋
        cov = [(s * B_HALF, Z_SEAT), (s * (Y_OPEN_OUT + REB), Z_SEAT),
               (s * (Y_OPEN_OUT + REB), Z_TOP), (s * B_HALF, Z_TOP)]
        v.hatch(cov, "SOLID", "S-STEEL")
        for yc in (1700, 1875, 2050):
            v.hatch([(s * (yc - 4), Z_SEAT - 60), (s * (yc + 4), Z_SEAT - 60), (s * (yc + 4), Z_SEAT),
                     (s * (yc - 4), Z_SEAT)], "SOLID", "S-STEEL")
        # 预埋板
        a, b = (1100, 1500) if s > 0 else (-1500, -1100)
        mortar_plate(v, a, b)
        # 剖切面以远：侧墙端面
        v.rect(s * B_HALF, Z_CAP, s * Y_WALL, Z_TOP, "S-THIN")
    plain_conc(v, [(-Y_OUT - 100, Z_BEAM_B - T_CUSH), (Y_OUT + 100, Z_BEAM_B - T_CUSH),
                   (Y_OUT + 100, Z_BEAM_B), (-Y_OUT - 100, Z_BEAM_B)])
    foot = [(Y_OUT + 100, Z_BEAM_B - T_CUSH), (Y_OUT + 100, Z_BEAM_B), (Y_OUT, Z_BEAM_B), (Y_OUT, 0),
            (-Y_OUT, 0), (-Y_OUT, Z_BEAM_B), (-Y_OUT - 100, Z_BEAM_B), (-Y_OUT - 100, Z_BEAM_B - T_CUSH)]
    foot = [(REPL_Y, 0), (Y_OUT, 0)] + [(Y_OUT, Z_BEAM_B), (Y_OUT + 100, Z_BEAM_B),
                                       (Y_OUT + 100, Z_BEAM_B - T_CUSH),
                                       (-Y_OUT - 100, Z_BEAM_B - T_CUSH), (-Y_OUT - 100, Z_BEAM_B),
                                       (-Y_OUT, Z_BEAM_B), (-Y_OUT, 0)]
    gravel(v, [(-REPL_Y, Z_REPL), (REPL_Y, Z_REPL)] + foot + [(-REPL_Y, 0)])
    v.rect(-1585, -250, 1585, Z_TOP - 8, "S-HIDE2")
    # 尺寸
    v.chainh([-Y_OUT, -Y_OPEN_OUT, -B_HALF, -1300, 1300, B_HALF, Y_OPEN_OUT, Y_OUT], Z_REPL, -3500,
             [None, None, None, "2600※", None, None, None], ext=3)
    v.chainh([-REPL_Y, -Y_OUT, Y_OUT, REPL_Y], Z_REPL, -3900, ext=3)
    v.chainv([Z_REPL, Z_BEAM_B - T_CUSH, Z_BEAM_B, Z_SUMP, Z_CAP, Z_TOP], REPL_Y, 3750, ext=3)
    v.dimv(Z_PLATE, Z_TOP, 1300, 900, "450※")
    # 标高
    v.elev(-2700, Z_TOP, "+0.050", "L")
    v.elev(-3100, 0, "±0.000", "L")
    v.elev(-600, Z_CAP, "-0.450", "R")
    v.elev(-1300, Z_PLATE, "-0.400", "L")
    v.elev(1840, Z_SUMP, "-0.850", "R")
    v.elev(-1000, Z_BEAM_B, "-1.250", "R", down=True)
    v.elev(-1000, Z_REPL, "-3.000", "R", down=True)
    # 标注
    v.leader([(2050, -520), (2750, -1700)], "JSK-1集水坑", 2.6, "R")
    v.leader([(3450, Z_PIPE + 80), (3450, -2300)], ["DN150排水管", "接室外雨水井"], 2.6, "L")
    v.leader([(-1900, Z_TOP - 5), (-2600, 600)], "GB-1盖板", 2.6, "L")
    v.leader([(0, -1000), (600, -1900)], "ZL-1", 2.6, "R")
    v.leader([(0, -1300), (-800, -2000)], "C15垫层", 2.6, "L")
    v.leader([(-2700, -2600), (-1700, -2500)], "级配砂石", 2.6, "R")
    v.leader([(1000, -150), (1600, 650)], "秤台(示意)", 2.6, "R")


def section_33(v):
    """3-3 横剖面（跨中，X=7525）。"""
    cross_common(v, ground_from=Y_WALL)
    zg = z_gutter(7525)
    zf = z_floor(GUT_Y[0])
    body = [(-Y_WALL, Z_RAFT_B), (Y_WALL, Z_RAFT_B), (Y_WALL, Z_TOP), (B_HALF, Z_TOP),
            (B_HALF, zg), (GUT_Y[0], zg), (GUT_Y[0], zf), (0, Z_CAP), (-GUT_Y[0], zf),
            (-GUT_Y[0], zg), (-B_HALF, zg), (-B_HALF, Z_TOP), (-Y_WALL, Z_TOP)]
    conc(v, body)
    plain_conc(v, [(-Y_WALL - 100, Z_RAFT_B - T_CUSH), (Y_WALL + 100, Z_RAFT_B - T_CUSH),
                   (Y_WALL + 100, Z_RAFT_B), (-Y_WALL - 100, Z_RAFT_B)])
    foot = [(REPL_Y, 0), (Y_WALL, 0), (Y_WALL, Z_RAFT_B), (Y_WALL + 100, Z_RAFT_B),
            (Y_WALL + 100, Z_RAFT_B - T_CUSH), (-Y_WALL - 100, Z_RAFT_B - T_CUSH),
            (-Y_WALL - 100, Z_RAFT_B), (-Y_WALL, Z_RAFT_B), (-Y_WALL, 0)]
    gravel(v, [(-REPL_Y, Z_REPL), (REPL_Y, Z_REPL)] + foot + [(-REPL_Y, 0)])
    # 以远可见：③轴传感器水泥台
    for s in (1, -1):
        a, b = sorted((s * 1100, s * 1500))
        v.rect(a - PAD, Z_CAP, b + PAD, Z_PLATE, "S-THIN")
    v.rect(-1585, -250, 1585, Z_TOP - 8, "S-HIDE2")
    # 坡度
    v.slope_mark(-750, -380, "i=1%", 14, ang=0, rev=True)
    v.slope_mark(750, -380, "i=1%", 14, ang=0)
    # 尺寸
    v.chainh([-Y_WALL, -B_HALF, -GUT_Y[0], GUT_Y[0], B_HALF, Y_WALL], Z_REPL, -3500, ext=3)
    v.chainh([-REPL_Y, -Y_WALL, Y_WALL, REPL_Y], Z_REPL, -3900, ext=3)
    v.chainv([Z_REPL, Z_RAFT_B - T_CUSH, Z_RAFT_B, Z_CAP, Z_TOP], REPL_Y, 3750, ext=3)
    # 标高
    v.elev(-2500, Z_TOP, "+0.050", "L")
    v.elev(-2900, 0, "±0.000", "L")
    v.elev(0, Z_CAP, "-0.450", "R")
    v.leader([(1525, zg), (2500, -1100)], "沟底标高随坡度变化", 2.6, "R")
    v.elev(-1000, Z_RAFT_B, "-0.750", "R", down=True)
    v.elev(-1000, Z_REPL, "-3.000", "R", down=True)
    # 标注
    v.leader([(-1700, -100), (-2500, 650)], "侧墙Q1(200厚)", 2.6, "L")
    v.leader([(1525, zg + 10), (2300, 650)], "排水沟150宽", 2.6, "R")
    v.leader([(500, -650), (900, -1700)], "底板300厚", 2.6, "R")
    v.leader([(-500, -800), (-1100, -1700)], "C15垫层", 2.6, "L")
    v.leader([(-2700, -2600), (-1700, -2500)], "级配砂石", 2.6, "R")


def section_44(v):
    """4-4 横剖面（①轴附近 X=200，向 -X 投射，示端墙内侧立面）。"""
    cross_common(v)
    body = [(-Y_OUT, Z_BEAM_B), (Y_OUT, Z_BEAM_B), (Y_OUT, Z_TOP), (Y_OPEN_OUT + REB, Z_TOP),
            (Y_OPEN_OUT + REB, Z_SEAT), (Y_OPEN_OUT, Z_SEAT), (Y_OPEN_OUT, Z_CAP),
            (-Y_OPEN_OUT, Z_CAP), (-Y_OPEN_OUT, Z_SEAT), (-Y_OPEN_OUT - REB, Z_SEAT),
            (-Y_OPEN_OUT - REB, Z_TOP), (-Y_OUT, Z_TOP)]
    conc(v, body)
    plain_conc(v, [(-Y_OUT - 100, Z_BEAM_B - T_CUSH), (Y_OUT + 100, Z_BEAM_B - T_CUSH),
                   (Y_OUT + 100, Z_BEAM_B), (-Y_OUT - 100, Z_BEAM_B)])
    foot = [(REPL_Y, 0), (Y_OUT, 0), (Y_OUT, Z_BEAM_B), (Y_OUT + 100, Z_BEAM_B),
            (Y_OUT + 100, Z_BEAM_B - T_CUSH), (-Y_OUT - 100, Z_BEAM_B - T_CUSH),
            (-Y_OUT - 100, Z_BEAM_B), (-Y_OUT, Z_BEAM_B), (-Y_OUT, 0)]
    gravel(v, [(-REPL_Y, Z_REPL), (REPL_Y, Z_REPL)] + foot + [(-REPL_Y, 0)])
    for s in (1, -1):
        a, b = (1100, 1500) if s > 0 else (-1500, -1100)
        mortar_plate(v, a, b)
        cov = [(s * B_HALF, Z_SEAT), (s * (Y_OPEN_OUT + REB), Z_SEAT),
               (s * (Y_OPEN_OUT + REB), Z_TOP), (s * B_HALF, Z_TOP)]
        v.hatch(cov, "SOLID", "S-STEEL")
        for yc in (1700, 1875, 2050):
            v.hatch([(s * (yc - 4), Z_SEAT - 60), (s * (yc + 4), Z_SEAT - 60), (s * (yc + 4), Z_SEAT),
                     (s * (yc - 4), Z_SEAT)], "SOLID", "S-STEEL")
    # 端墙内侧立面（以远可见）
    v.pl([(-Y_OPEN_OUT, Z_SEAT), (-B_HALF, Z_SEAT), (-B_HALF, Z_TOP), (B_HALF, Z_TOP),
          (B_HALF, Z_SEAT), (Y_OPEN_OUT, Z_SEAT)], "S-THIN")
    v.line((ANGLE_Y[0], Z_TOP - 75), (ANGLE_Y[1], Z_TOP - 75), "S-STEEL")
    for y1, y2 in LIMIT_Y:
        v.rect(y1, Z_LIMIT_B, y2, Z_LIMIT_T, "S-STEEL")
        v.hatch([(y1, Z_LIMIT_B), (y2, Z_LIMIT_B), (y2, Z_LIMIT_T), (y1, Z_LIMIT_T)], "ANSI37",
                "S-STEEL", rel=0.4)
    # 尺寸
    v.chainh([-Y_OUT, -Y_OPEN_OUT, -B_HALF, B_HALF, Y_OPEN_OUT, Y_OUT], Z_REPL, -3500, ext=3)
    v.chainh([-1660, -1340, 1340, 1660], Z_TOP, 400, [None, "2680", None], ext=3)
    v.dimh(-1500, 1500, Z_TOP, 750, "3000※(限位板中心距)", ext=3)
    v.dimh(-1300, 1300, Z_TOP, 1100, "2600※(传感器中心距)", ext=3)
    v.chainv([Z_REPL, Z_BEAM_B - T_CUSH, Z_BEAM_B, Z_CAP, Z_TOP], REPL_Y, 3750, ext=3)
    # 标高
    v.elev(-2700, Z_TOP, "+0.050", "L")
    v.elev(-3100, 0, "±0.000", "L")
    v.elev(-300, Z_CAP, "-0.450", "R")
    v.elev(-1300, Z_PLATE, "-0.400", "L")
    v.elev(-1000, Z_BEAM_B, "-1.250", "R", down=True)
    v.elev(-1000, Z_REPL, "-3.000", "R", down=True)
    # 标注
    v.leader([(1500, -100), (2600, -700)], "M-2限位预埋板", 2.6, "R")
    v.leader([(-800, Z_TOP - 40), (-1700, -800)], "M-3护边角钢", 2.6, "L")
    v.leader([(0, -1000), (600, -1900)], "ZL-2", 2.6, "R")
    v.leader([(-1300, Z_PLATE_B), (-2000, -1250)], "M-1", 2.6, "L")
    v.leader([(-2700, -2600), (-1700, -2500)], "级配砂石", 2.6, "R")


def sheet_sections(sh):
    p = sh.paper
    v1 = sh.view(215, 535, 50)
    long_section(v1)
    p.detail_title(330, 438, None, "1-1 剖面", "1:50", h=6.0)

    y0 = 380
    for cx, fn, nm in ((165, section_22, "2-2 剖面"), (425, section_33, "3-3 剖面"),
                       (685, section_44, "4-4 剖面(端墙内侧立面)")):
        v = sh.view(cx, y0, 30)
        fn(v)
        p.detail_title(cx - 45, 232, None, nm, "1:30", h=5.5)

    notes = [
        "说明：",
        "1. 剖面位置见结施-02；标高以m计，尺寸以mm计；±0.000为汽车衡周围地面设计标高。",
        "2. 基础底以下至-3.000(最大冻结深度2.80m以下)原状土全部挖除，换填非冻胀性级配砂石，分层(≤300)振动压实，",
        "   压实系数≥0.97；换填底面每边宽出基础外边线不小于1000，基坑边坡及降水方案由施工单位另行设计。",
        "3. 开挖至-3.000后须通知勘察、设计、监理单位验槽；如遇杂填土或软弱土，应继续挖除至原状土并以级配砂石回填。",
        "4. 传感器预埋板顶面至护边角钢顶面450(+2/0)※；所有传感器预埋板顶面高差≤2mm。",
        "5. 坑底横坡1%(中间高两侧低)坡向排水沟；排水沟沟底纵坡0.5%坡向③轴集水坑，沟底标高随坡度变化。",
        "6. 秤台轮廓、限位装置以厂家图纸为准；抗浮设防水位134.500为绝对标高(按±0.000=135.000示意)。",
    ]
    p.text_lines(40, 205, notes, 3.0, 1.75)
