# -*- coding: utf-8 -*-
"""结施-05 预埋件及节点详图。"""
from geom import *  # noqa: F401,F403
from s03_sections import conc, gravel


def steel_fill(v, pts):
    v.hatch(pts, "SOLID", "S-STEEL")
    v.pl(pts, "S-STEEL", closed=True)


def angle_L(v, x, y, b, t, dx=1, dy=1):
    """角钢截面（肢背交点 x,y；dx/dy 为两肢方向）。"""
    pts = [(x, y), (x + dx * b, y), (x + dx * b, y + dy * t), (x + dx * t, y + dy * t),
           (x + dx * t, y + dy * b), (x, y + dy * b)]
    steel_fill(v, pts)


# ---------------- ① 端墙顶部节点 ----------------
def node_end_wall(v):
    body = [(X_LEFT, -800), (700, -800), (700, Z_CAP), (0, Z_CAP), (0, Z_TOP), (X_LEDGE_L, Z_TOP),
            (X_LEDGE_L, Z_LEDGE), (X_LEFT, Z_LEDGE)]
    v.rc_hatch(body)
    v.pl([(700, -800), (700, Z_CAP), (0, Z_CAP), (0, Z_TOP), (X_LEDGE_L, Z_TOP), (X_LEDGE_L, Z_LEDGE),
          (X_LEFT, Z_LEDGE), (X_LEFT, -800)], "S-CONC")
    v.break_line((X_LEFT - 50, -800), (750, -800))
    v.break_line((700, -850), (700, Z_CAP + 50))
    # 引道板
    x0 = -950
    slab = [(x0, Z_LEDGE - 3), (-320, Z_LEDGE), (-320, Z_TOP), (x0, Z_TOP - 5)]
    v.rc_hatch(slab)
    v.pl([slab[3], slab[2], slab[1], slab[0]], "S-CONC")
    v.break_line((x0, Z_LEDGE - 60), (x0, Z_TOP + 60))
    gravel(v, [(x0, Z_LEDGE - 3 - 300), (X_LEFT, Z_LEDGE - 300), (X_LEFT, Z_LEDGE), (x0, Z_LEDGE - 3)])
    # 缝
    v.hatch([(-320, Z_TOP - 30), (-300, Z_TOP - 30), (-300, Z_TOP), (-320, Z_TOP)], "SOLID", "S-STEEL")
    v.line((-500, Z_LEDGE + 3), (-320, Z_LEDGE + 3), "S-THIN")
    # 护边角钢 L75x75x7（肢背在墙角）
    steel_fill(v, [(0, Z_TOP), (-75, Z_TOP), (-75, Z_TOP - 7), (-7, Z_TOP - 7), (-7, Z_TOP - 75),
                   (0, Z_TOP - 75)])
    v.pl([(-12, Z_TOP - 12), (-153, Z_TOP - 153), (-153, Z_TOP - 203)], "S-STEEL", width=0.4)
    # 限位预埋板
    steel_fill(v, [(-16, Z_LIMIT_B), (0, Z_LIMIT_B), (0, Z_LIMIT_T), (-16, Z_LIMIT_T)])
    v.pl([(-16, -50), (-216, -50), (-216, -100)], "S-STEEL", width=0.4)
    # 焊缝符号
    v.pl([(-16, Z_LIMIT_T), (-26, Z_LIMIT_T + 10), (-16, Z_LIMIT_T + 10)], "S-STEEL")
    # 传感器预埋板（投影）及水泥台
    v.pl([(0, Z_CAP), (450, Z_CAP), (425, Z_PLATE_B), (0, Z_PLATE_B)], "S-THIN", closed=True)
    v.hatch([(0, Z_CAP), (450, Z_CAP), (425, Z_PLATE_B), (0, Z_PLATE_B)], "AR-SAND", rel=0.5)
    steel_fill(v, [(0, Z_PLATE_B), (400, Z_PLATE_B), (400, Z_PLATE), (0, Z_PLATE)])
    # 传感器中心线、秤台示意
    v.line((175, -620), (175, 420), "S-AXIS")
    v.pl([(700, Z_TOP), (25, Z_TOP), (25, -250), (700, -250)], "S-HIDE2")
    # 墙筋（示意）
    v.pl([(-37, -780), (-37, Z_TOP - 30), (X_LEDGE_L + 37, Z_TOP - 30), (X_LEDGE_L + 37, -500)], "S-REBAR")
    v.pl([(X_LEFT + 37, -780), (X_LEFT + 37, Z_LEDGE - 30), (X_LEDGE_L + 37, Z_LEDGE - 30)], "S-REBAR")
    v.line((700, Z_CAP - 72), (0, Z_CAP - 72), "S-REBAR")
    # 尺寸
    v.dimv(Z_PLATE, Z_TOP, 400, 520, "450(+2/0)※", ext=3)
    v.chainv([Z_LIMIT_B, Z_LIMIT_T, Z_TOP], -16, 80, ["150", "75"], ext=None)
    v.chainh([X_LEFT, -320, X_LEDGE_L, 0], Z_TOP, 220, ["180", "20", "300"], ext=3)
    v.dimh(0, 175, Z_TOP, 250, "175※", ext=3)
    v.dimv(Z_LEDGE, Z_TOP, X_LEFT, -700, "250", ext=3)
    # 标高
    v.elev(640, Z_TOP, "+0.050", "R")
    v.elev(640, Z_PLATE, "-0.400", "R")
    v.line((700, Z_CAP), (900, Z_CAP), "S-THIN")
    v.elev(820, Z_CAP, "-0.450", "R", down=True)
    v.elev(-760, Z_TOP, "+0.050(引道板端)", "L")
    # 标注
    v.leader([(-40, Z_TOP), (-120, 480)], "M-3 L75×75×7", h=2.6, side="L")
    v.leader([(-100, -45), (-650, -280)], "锚筋C16,L=250", h=2.6, side="L")
    v.leader([(-20, Z_LIMIT_T + 5), (-650, -420)], "焊接(有锚筋侧上边与角钢焊)", h=2.4, side="L")
    v.leader([(-8, -120), (-650, -560)], "M-2 -320×150×16", h=2.6, side="L")
    v.leader([(-420, Z_LEDGE + 3), (-650, -700)], "油毡滑动层", h=2.4, side="L")
    v.leader([(-310, Z_TOP - 15), (-600, 330)], "20缝,聚氨酯密封胶", h=2.4, side="L")
    v.leader([(260, Z_PLATE), (150, -150)], "M-1", h=2.6, side="L")
    v.leader([(225, Z_CAP + 10), (760, -680)], "1:1水泥砂浆座浆", h=2.4, side="R")
    v.text(175, 440, "传感器中心线", 2.4, "BC")
    v.text(690, 30, "秤台(厂家)", 2.4, "TR")


# ---------------- ② 检修口平面及剖面 ----------------
def opening_plan(v):
    """局部坐标：x = X - X③，y = Y（+Y 侧）。"""
    walls = [
        [(-900, B_HALF), (-400, B_HALF), (-400, Y_WALL), (-900, Y_WALL)],
        [(400, B_HALF), (900, B_HALF), (900, Y_WALL), (400, Y_WALL)],
        [(-600, Y_WALL), (-400, Y_WALL), (-400, Y_OPEN_OUT), (-600, Y_OPEN_OUT)],
        [(400, Y_WALL), (600, Y_WALL), (600, Y_OPEN_OUT), (400, Y_OPEN_OUT)],
        [(-600, Y_OPEN_OUT), (600, Y_OPEN_OUT), (600, Y_OUT), (-600, Y_OUT)],
    ]
    outline = [(-900, Y_WALL), (-600, Y_WALL), (-600, Y_OUT), (600, Y_OUT), (600, Y_WALL), (900, Y_WALL)]
    v.rc_hatch([(-900, B_HALF), (-400, B_HALF), (-400, Y_OPEN_OUT), (400, Y_OPEN_OUT), (400, B_HALF),
                (900, B_HALF), (900, Y_WALL), (600, Y_WALL), (600, Y_OUT), (-600, Y_OUT), (-600, Y_WALL),
                (-900, Y_WALL)])
    v.pl(outline, "S-CONC")
    v.pl([(-900, B_HALF), (-400, B_HALF), (-400, Y_OPEN_OUT), (400, Y_OPEN_OUT), (400, B_HALF),
          (900, B_HALF)], "S-CONC")
    v.break_line((-900, B_HALF - 60), (-900, Y_WALL + 60))
    v.break_line((900, B_HALF - 60), (900, Y_WALL + 60))
    del walls
    # 凹槽及护口角钢
    v.pl([(-450, B_HALF), (-450, Y_OPEN_OUT + REB), (450, Y_OPEN_OUT + REB), (450, B_HALF)], "S-STEEL")
    v.pl([(-405, B_HALF), (-405, Y_OPEN_OUT - 5), (405, Y_OPEN_OUT - 5), (405, B_HALF)], "S-STEEL")
    # 墩梁边线、预埋板
    yb0 = B_HALF - 350                    # 断开处
    pt = PLATE_Y[1][1]
    for x in (-600, 600):
        v.line((x, yb0), (x, B_HALF), "S-HIDE")
    v.rect(-250, yb0, 250, pt + PAD, "S-HIDE")
    v.pl([(-200, yb0), (-200, pt), (200, pt), (200, yb0)], "S-STEEL")
    v.break_line((-900, yb0), (900, yb0))
    # 集水坑与沟
    sx1, sx2, sy1, sy2 = SUMP
    a, b = sx1 - AX[2], sx2 - AX[2]
    v.rect(a, sy1, b, sy2, "S-THIN")
    v.line((a, sy1), (b, sy2), "S-THIN")
    v.line((a, sy2), (b, sy1), "S-THIN")
    g0, g1, gj = GUT_Y[0], GUT_Y[1], B_HALF + GUT_W
    gm = (g0 + g1) / 2
    v.pl([(-900, g0), (-260, g0), (-260, g1), (a, g1)], "S-THIN")
    v.pl([(900, g0), (260, g0), (260, g1), (b, g1)], "S-THIN")
    v.pl([(-400, gj), (a, gj)], "S-THIN")
    v.pl([(400, gj), (b, gj)], "S-THIN")
    v.arrow((-800, gm), (-450, gm))
    v.arrow((800, gm), (450, gm))
    v.line((0, sy2), (0, Y_OUT + 350), "S-PIPE")
    v.rect(-450, B_HALF, 450, Y_OPEN_OUT + REB, "S-HIDE2")
    # 尺寸
    v.chainh([-600, -400, 400, 600], Y_OUT, Y_OUT + 300, ext=3)
    v.dimh(-450, 450, Y_OUT, Y_OUT + 550, "900(盖板)", ext=3)
    v.chainv([B_HALF, Y_OPEN_OUT, Y_OPEN_OUT + REB, Y_OUT], 600, 850, ["550", "50", "150"], ext=3)
    v.chainv([B_HALF, gj], -900, -1100, ["150"], ext=3)
    v.leader([(b, SUMP[2] + 200), (950, SUMP[2] + 250)], "JSK-1 400×400", h=2.4, side="R")
    v.leader([(-430, Y_OPEN_OUT + 30), (-800, Y_OUT + 150)], "M-4 L50×5", h=2.4, side="L")
    v.leader([(0, Y_OUT + 150), (300, Y_OUT + 450)], "DN150排水管", h=2.4, side="R")
    v.leader([(-330, B_HALF + 50), (-750, B_HALF + 400)], "排水沟", h=2.4, side="L")
    v.text(0, B_HALF - 250, "M-1", 2.4, "MC")


def opening_section(v):
    """A-A 剖面：局部 x = Y，y = Z（取③轴，经集水坑中心）。"""
    sx1, sx2, sy1, sy2 = SUMP
    y0 = B_HALF - 350                     # 断开处
    ye = Y_OUT + 450                      # 视图外边
    low = [(y0, -1000), (Y_OUT, -1000), (Y_OUT, Z_PIPE), (sy2, Z_PIPE), (sy2, Z_SUMP), (sy1, Z_SUMP),
           (sy1, Z_CAP), (y0, Z_CAP)]
    up = [(sy2, Z_PIPE + 160), (Y_OUT, Z_PIPE + 160), (Y_OUT, Z_TOP), (Y_OPEN_OUT + REB, Z_TOP),
          (Y_OPEN_OUT + REB, Z_SEAT), (Y_OPEN_OUT, Z_SEAT), (Y_OPEN_OUT, Z_CAP), (sy2, Z_CAP)]
    v.rc_hatch(low)
    v.rc_hatch(up)
    v.pl(low[1:], "S-CONC")
    v.pl(up, "S-CONC", closed=True)
    v.break_line((y0, -1050), (y0, Z_CAP + 50))
    v.break_line((y0 - 50, -1000), (Y_OUT + 50, -1000))
    gravel(v, [(Y_OUT, -1000), (ye, -1000), (ye, 0), (Y_OUT, 0)])
    v.line((Y_OUT, 0), (ye, 0), "S-CONC")
    # 管
    v.line((sy2, Z_PIPE), (ye, Z_PIPE - 3), "S-THIN")
    v.line((sy2, Z_PIPE + 160), (ye, Z_PIPE + 157), "S-THIN")
    # 盖板与加劲肋
    steel_fill(v, [(B_HALF, Z_SEAT), (Y_OPEN_OUT + REB, Z_SEAT), (Y_OPEN_OUT + REB, Z_TOP), (B_HALF, Z_TOP)])
    for yc in COVER_RIBS:
        steel_fill(v, [(yc - 4, Z_SEAT - 60), (yc + 4, Z_SEAT - 60), (yc + 4, Z_SEAT), (yc - 4, Z_SEAT)])
    angle_L(v, Y_OPEN_OUT, Z_SEAT, 50, 5, dx=1, dy=-1)
    v.pl([(Y_OPEN_OUT + 25, Z_SEAT - 5), (Y_OPEN_OUT + 25, Z_SEAT - 150)], "S-STEEL", width=0.3)
    # 预埋板
    pt = PLATE_Y[1][1]
    v.pl([(y0, Z_CAP), (pt + PAD, Z_CAP), (pt + PAD - 25, Z_PLATE_B), (y0, Z_PLATE_B)], "S-THIN")
    steel_fill(v, [(y0, Z_PLATE_B), (pt, Z_PLATE_B), (pt, Z_PLATE), (y0, Z_PLATE)])
    v.line((PLAT_Y, Z_TOP), (PLAT_Y, -250), "S-HIDE2")
    # 尺寸
    v.chainv([Z_SUMP, Z_CAP, Z_TOP], Y_OUT, Y_OUT + 300, ["400", "500"], ext=3)
    v.chainh([B_HALF, sy1, sy2, Y_OPEN_OUT + REB, Y_OUT], Z_SUMP, -1250, ["100", "400", "100", "150"], ext=3)
    v.elev(B_HALF - 250, Z_TOP, "+0.050", "L")
    v.elev(Y_OUT + 350, 0, "±0.000", "L")
    v.elev(SUMP[2] + 150, Z_SUMP, "-0.850", "R")
    v.leader([(B_HALF + 200, Z_TOP - 5), (B_HALF + 100, 330)], "GB-1 δ10花纹钢板", h=2.4, side="L")
    v.leader([(COVER_RIBS[1], Z_SEAT - 40), (B_HALF, -230)], "加劲肋-60×8", h=2.4, side="L")
    v.leader([(Y_OPEN_OUT + 3, Z_SEAT - 30), (Y_OUT + 250, 250)], "M-4 L50×5", h=2.4, side="R")
    v.leader([(Y_OUT + 100, Z_PIPE + 80), (Y_OUT + 400, -950)], "DN150", h=2.4, side="R")
    v.text(PLAT_Y, -260, "秤台边", 2.2, "TC")


def gutter_cross(v):
    """排水沟过②(④)轴墩梁做法（平面），局部 x = X - X②，y = Y。"""
    v.rc_hatch([(-1000, B_HALF), (-400, B_HALF), (-400, Y_OPEN_OUT), (400, Y_OPEN_OUT), (400, B_HALF),
                (1000, B_HALF), (1000, Y_WALL), (600, Y_WALL), (600, Y_OUT), (-600, Y_OUT), (-600, Y_WALL),
                (-1000, Y_WALL)])
    v.pl([(-1000, Y_WALL), (-600, Y_WALL), (-600, Y_OUT), (600, Y_OUT), (600, Y_WALL), (1000, Y_WALL)],
         "S-CONC")
    v.pl([(-1000, B_HALF), (-400, B_HALF), (-400, Y_OPEN_OUT), (400, Y_OPEN_OUT), (400, B_HALF),
          (1000, B_HALF)], "S-CONC")
    yb0 = B_HALF - 350
    pt = PLATE_Y[1][1]
    g0, g1, gj = GUT_Y[0], GUT_Y[1], B_HALF + GUT_W
    for x in (-600, 600):
        v.line((x, yb0), (x, B_HALF), "S-HIDE")
    v.rect(-250, yb0, 250, pt + PAD, "S-HIDE")
    v.pl([(-200, yb0), (-200, pt), (200, pt), (200, yb0)], "S-STEEL")
    inner = [(-1000, g0), (-260, g0), (-260, g1), (260, g1), (260, g0), (1000, g0)]
    outer = [(-1000, g1), (-400, g1), (-400, gj), (400, gj), (400, g1), (1000, g1)]
    v.pl(inner, "S-REBAR")
    v.pl(outer, "S-REBAR")
    v.hatch(inner + list(reversed(outer)), "ANSI37", "S-HATCH", rel=0.5)
    v.arrow((-900, (g0 + g1) / 2), (-500, (g0 + g1) / 2))
    v.arrow((-150, (g1 + gj) / 2 + 5), (150, (g1 + gj) / 2 + 5))
    v.arrow((500, (g0 + g1) / 2), (900, (g0 + g1) / 2))
    v.break_line((-1000, yb0), (1000, yb0))
    v.chainh([-400, -260, 260, 400], Y_OUT, Y_OUT + 350, ["140", "520", "140"], ext=3)
    v.chainv([g0, g1, gj], 1000, 1250, ["150", "150"], ext=3)
    v.text(0, B_HALF - 250, "传感器水泥台", 2.4, "MC")
    v.text(-780, g0 - 20, "沟底i=0.5%", 2.2, "TC")
    v.text(0, B_HALF + 400, "检修口", 2.4, "MC")


# ---------------- 预埋件 ----------------
def m1(v):
    v.rect(0, 0, 400, 400, "S-STEEL")
    v.line((200, -40), (200, 440), "S-AXIS")
    v.line((-40, 200), (440, 200), "S-AXIS")
    v.dimh(0, 400, 0, -120, ext=3)
    v.dimv(0, 400, 400, 520, ext=3)
    steel_fill(v, [(600, 0), (620, 0), (620, 400), (600, 400)])
    v.dimh(600, 620, 400, 500, "20", ext=None)
    v.text(300, 100, "-400×400×20", 2.4, "MC")
    v.text(700, 200, "板面要平", 2.6, "ML")


def m2(v):
    v.rect(0, 0, 320, 150, "S-STEEL")
    for x in (60, 260):
        v.circle((x, 125), 8, "S-STEEL")
    v.line((160, -30), (160, 180), "S-AXIS")
    v.chainh([0, 60, 260, 320], 0, -80, ["60", "200", "60"], ext=3)
    v.chainv([0, 125, 150], 320, 400, ["125", "25"], ext=3)
    # 侧视
    ox = 520
    steel_fill(v, [(ox, 0), (ox + 16, 0), (ox + 16, 150), (ox, 150)])
    v.pl([(ox + 16, 125), (ox + 216, 125), (ox + 216, 75)], "S-STEEL", width=0.4)
    v.dimh(ox + 16, ox + 216, 125, 230, "200", ext=None)
    v.dimv(75, 125, ox + 216, ox + 300, "50", ext=None)
    v.dimh(ox, ox + 16, 0, -80, "16", ext=3)
    v.leader([(ox + 120, 125), (ox + 160, 30)], "锚筋2C16", h=2.4, side="R")


def m3(v_el, v_sec):
    Lg = ANGLE_Y[1] - ANGLE_Y[0]
    e = 150                                   # 端部锚筋距角钢端
    sp = (Lg - 2 * e) / 8                     # 9根锚筋均布
    v_el.rect(0, 0, Lg, 75, "S-STEEL")
    v_el.line((0, 7), (Lg, 7), "S-STEEL")
    xs = [e + sp * i for i in range(9)]
    for x in xs:
        v_el.line((x, 0), (x, -120), "S-STEEL")
    v_el.chainh([0] + xs + [Lg], 0, -260, [str(e)] + [f"{sp:g}"] * 8 + [str(e)], ext=3)
    v_el.dimh(0, Lg, 0, -420, f"{Lg}", ext=3)
    v_el.text(Lg / 2, 120, "锚筋9C16,L=250，与角钢双面焊", 2.4, "BC")
    # 截面
    angle_L(v_sec, 0, 0, 75, 7, dx=-1, dy=-1)
    v_sec.pl([(-10, -10), (-151, -151), (-151, -201)], "S-STEEL", width=0.5)
    v_sec.dimh(-75, 0, 0, 40, "75", ext=None)
    v_sec.dimv(-75, 0, 0, 40, "75", ext=None)
    v_sec.text(-160, -60, "200", 2.2, "MR")
    v_sec.text(-170, -185, "50", 2.2, "MR")
    v_sec.text(-40, -230, "L75×75×7", 2.4, "TC")


def m4(v):
    """检修口护口角钢框（Π形，平面）。"""
    v.pl([(-450, 0), (-450, 600), (450, 600), (450, 0)], "S-STEEL", width=0.5)
    v.pl([(-400, 0), (-400, 550), (400, 550), (400, 0)], "S-STEEL")
    for x, y in ((-425, 150), (-425, 450), (425, 150), (425, 450), (-300, 575), (-100, 575), (100, 575),
                 (300, 575)):
        v.circle((x, y), 10, "S-STEEL")
    v.dimh(-450, 450, 600, 700, ext=3)
    v.dimv(0, 600, -450, -550, ext=3)
    v.text(0, 250, "L50×5框(三面)", 2.4, "MC")
    v.text(0, 170, "锚筋C10,L=150,@300", 2.2, "MC")
    v.text(0, -60, "开口侧(坑内)", 2.2, "TC")


def gb1(v):
    v.rect(0, 0, 900, 600, "S-STEEL")
    for y in (100, 275, 450):
        v.rect(55, y - 4, 845, y + 4, "S-HIDE")
    for x in (250, 650):
        v.circle((x, 520), 15, "S-STEEL")
    v.dimh(0, 900, 0, -100, ext=3)
    v.dimv(0, 600, 900, 1000, ext=3)
    v.chainv([0, 100, 275, 450, 600], 0, -120, ["100", "175", "175", "150"], ext=3)
    v.text(450, 360, "δ10花纹钢板", 2.4, "MC")
    v.text(450, 190, "加劲肋-60×8,L=790(3道)", 2.2, "MC")
    v.text(450, 560, "φ30提手孔2个", 2.2, "MC")
    v.text(450, -200, "坑内侧(无支承边)", 2.2, "TC")


def grounding(v):
    """④ 接地做法（立面，局部 x = X，y = Z）。"""
    v.rc_hatch([(-500, -1250), (0, -1250), (0, Z_TOP), (-500, Z_TOP)])
    v.pl([(0, -1250), (-500, -1250), (-500, Z_TOP), (0, Z_TOP)], "S-CONC")
    v.break_line((0, -1300), (0, Z_TOP + 50))
    v.line((-2200, 0), (-500, 0), "S-CONC")
    gravel(v, [(-2200, -1250), (-500, -1250), (-500, 0), (-2200, 0)])
    v.break_line((-2200, -1300), (-500, -1300))
    # 接地极
    xe = -1700
    v.rect(xe - 25, -3000, xe + 25, -700, "S-STEEL")
    v.line((xe - 25, -3000), (xe, -3080), "S-STEEL")
    v.line((xe + 25, -3000), (xe, -3080), "S-STEEL")
    v.pl([(xe, -700), (-560, -700), (-560, Z_TOP - 60), (-80, Z_TOP - 60)], "S-STEEL", width=0.5)
    v.dimv(-3000, -700, xe, xe - 400, "2300", ext=3)
    v.dimv(-700, 0, xe, xe - 400, "700", ext=3)
    v.elev(-2000, 0, "±0.000", "L")
    v.leader([(xe, -2200), (xe + 450, -2500)], "JD-1 L50×5,L=2300(热镀锌)", h=2.4, side="R")
    v.leader([(-1100, -700), (-1300, 300)], "-40×4镀锌扁钢", h=2.4, side="L")
    v.leader([(-300, Z_TOP - 60), (200, 300)], "与护边角钢锚筋焊接", h=2.4, side="R")


def conduit(v):
    """⑤ 电缆穿线管做法（②轴-Y侧检修口，局部 x = -Y，y = Z）。"""
    y0 = B_HALF - 350
    ye = Y_OUT + 650
    v.rc_hatch([(y0, -1250), (Y_OUT, -1250), (Y_OUT, Z_TOP), (Y_OPEN_OUT + REB, Z_TOP),
                (Y_OPEN_OUT + REB, Z_SEAT), (Y_OPEN_OUT, Z_SEAT), (Y_OPEN_OUT, Z_CAP), (y0, Z_CAP)])
    v.pl([(y0, Z_CAP), (Y_OPEN_OUT, Z_CAP), (Y_OPEN_OUT, Z_SEAT), (Y_OPEN_OUT + REB, Z_SEAT),
          (Y_OPEN_OUT + REB, Z_TOP), (Y_OUT, Z_TOP), (Y_OUT, -1250), (y0, -1250)], "S-CONC")
    v.break_line((y0, -1300), (y0, Z_CAP + 50))
    gravel(v, [(Y_OUT, -1250), (ye, -1250), (ye, 0), (Y_OUT, 0)])
    v.line((Y_OUT, 0), (ye, 0), "S-CONC")
    x0 = Y_OPEN_OUT - 175
    v.pl([(x0, -410), (x0, -800), (x0 + 120, -920), (ye, -940)], "S-PIPE")
    v.pl([(x0 + 40, -410), (x0 + 40, -790), (x0 + 130, -880), (ye, -900)], "S-PIPE")
    v.leader([(x0 + 20, -410), (B_HALF, -150)], "管口高出混凝土面40", h=2.4, side="L")
    v.leader([(Y_OUT + 350, -920), (Y_OUT + 250, -1350)], "φ40 PVC管至秤房(管内预穿铁丝)", h=2.4, side="L")
    v.elev(B_HALF - 150, Z_CAP, "-0.450", "R")


def parts_table(p, x, ytop):
    rows = [
        ["编号", "名称", "规格", "单件重(kg)", "数量", "总重(kg)"],
        ["M-1", "传感器预埋板", "-400×400×20", "25.1", "10", "251.2"],
        ["M-2", "限位预埋板", "-320×150×16+2C16", "6.8", "4", "27.3"],
        ["M-3", "护边角钢", "L75×75×7,L=3500+9C16", "31.5", "2", "63.0"],
        ["M-4", "护口角钢框", "L50×5,L=2100+8C10", "8.7", "10", "86.6"],
        ["GB-1", "检修口盖板", "δ10花纹板+3-60×8", "53.0", "10", "530.0"],
        ["JD-1", "接地极", "L50×5,L=2300", "8.7", "2", "17.3"],
        ["—", "接地扁钢", "-40×4,约12m", "—", "—", "15.1"],
    ]
    p.text(x + 76, ytop + 8, "预埋件材料表", 3.5, "TC")
    return p.table(x, ytop, [16, 30, 52, 20, 14, 20], rows, row_h=6.4, h=2.5)


DETAIL_NOTES = [
    "说明：",
    "1. 钢板、角钢采用Q235B，锚筋HRB400；焊条：Q235之间E43型，HRB400与Q235之间E50型。",
    "2. 锚筋与锚板T形焊(穿孔塞焊或角焊)，焊脚≥0.6d且≥6mm；锚筋与角钢双面焊，焊缝长≥5d。",
    "3. 护边角钢上平面水平且在同一平面内，两角钢间距(纵向、对角线)误差≤5mm；限位预埋板紧贴模板，",
    "   有锚筋一侧上边与护边角钢焊接，另一侧不焊。",
    "4. 传感器预埋板在基础混凝土达到设计强度后安装：墩顶凿毛、清理湿润，铺1:1水泥砂浆，放板后用手锤",
    "   敲击调平，保证板底砂浆密实无空隙；板中心(纵、横、对角线)误差≤10mm，板顶高差≤2mm。",
    "5. 外露钢构件除锈Sa2.5，涂环氧富锌底漆2道+面漆2道；传感器预埋板上表面不涂漆，清理后涂防锈油。",
    "6. 检修口盖板用户自备，上平面与秤面平齐；检修口为非行车部位，严禁车辆碾压。",
    "7. 接地电阻≤4Ω，实测不满足时增设接地极；秤房内另设接地桩及接线螺钉(≤4Ω)。",
    "8. 护边角钢长3500(厂家)，比坑内净宽3400长100，两端各伸入端部检修口50，端部4块检修口盖板在该处",
    "   切角50×50；限位预埋板中心距3300※，外侧约110位于端部检修口内的端墙面上。",
]


def sheet_details(sh):
    p = sh.paper
    v1 = sh.view(130, 505, 10)
    node_end_wall(v1)
    p.detail_title(45, 405, 1, "端墙顶部节点", "1:10", h=5.0)

    v2 = sh.view(320, 352, 15)
    opening_plan(v2)
    p.detail_title(262, 412, 2, "检修口平面(③轴)", "1:15", h=5.0)

    v3 = sh.view(330, 505, 15)
    opening_section(v3)
    p.detail_title(420, 412, None, "A-A 剖面", "1:15", h=5.0)

    v4 = sh.view(650, 392, 20)
    gutter_cross(v4)
    p.detail_title(590, 412, 3, "排水沟过②④轴做法", "1:20", h=5.0)

    # 预埋件
    v5 = sh.view(45, 320, 10)
    m1(v5)
    p.detail_title(45, 288, None, "M-1 传感器预埋板(10块)", "1:10", h=4.2)
    v6 = sh.view(165, 330, 5)
    m2(v6)
    p.detail_title(165, 288, None, "M-2 限位预埋板(4块)", "1:5", h=4.2)
    v7 = sh.view(345, 335, 20)
    v7s = sh.view(560, 345, 5)
    m3(v7, v7s)
    p.detail_title(345, 288, None, "M-3 护边角钢(2根)", "1:20、1:5", h=4.2)
    v8 = sh.view(700, 310, 10)
    m4(v8)
    p.detail_title(650, 288, None, "M-4 检修口护口角钢(10套)", "1:10", h=4.2)

    v9 = sh.view(45, 175, 10)
    gb1(v9)
    p.detail_title(45, 145, None, "GB-1 检修口盖板(10块)", "1:10", h=4.2)
    v10 = sh.view(255, 225, 30)
    grounding(v10)
    p.detail_title(185, 108, 4, "接地做法", "1:30", h=4.5)
    v11 = sh.view(280, 212, 20)
    conduit(v11)
    p.detail_title(345, 126, 5, "电缆穿线管做法", "1:20", h=4.5)

    parts_table(p, 470, 240)
    p.text_lines(470, 182, DETAIL_NOTES, 2.6, 1.6)
