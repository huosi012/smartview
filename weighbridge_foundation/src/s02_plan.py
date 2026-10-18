# -*- coding: utf-8 -*-
"""结施-02 基础平面布置图。"""
from geom import *  # noqa: F401,F403
import geom as G


def outer_outline(s=1):
    """基础顶面外轮廓（含检修口凸出部分）。"""
    pts = [(X_LEFT, -Y_OUT)]
    pts += [(1000, -Y_OUT), (1000, -Y_WALL)]
    for x1, x2 in BUMP_OUT[1:4]:
        pts += [(x1, -Y_WALL), (x1, -Y_OUT), (x2, -Y_OUT), (x2, -Y_WALL)]
    pts += [(19050, -Y_WALL), (19050, -Y_OUT), (X_RIGHT, -Y_OUT)]
    top = [(x, -y) for x, y in reversed(pts)]
    return pts + top


def inner_outline():
    """坑内及检修口净空轮廓。"""
    pts = [(0, -Y_OPEN_OUT), (800, -Y_OPEN_OUT), (800, -B_HALF)]
    for x1, x2 in OPEN[1:4]:
        pts += [(x1, -B_HALF), (x1, -Y_OPEN_OUT), (x2, -Y_OPEN_OUT), (x2, -B_HALF)]
    pts += [(19250, -B_HALF), (19250, -Y_OPEN_OUT), (L, -Y_OPEN_OUT)]
    top = [(x, -y) for x, y in reversed(pts)]
    return pts + top


def draw_plan_body(v, show_platform=True, show_site=True, show_beams=True, labels=True):
    """平面主体（真实坐标 X, Y）。"""
    # 墙体轮廓
    v.pl(outer_outline(), "S-CONC", closed=True)
    v.pl(inner_outline(), "S-CONC", closed=True)
    # 端墙搭板牛腿台阶线
    for xl in (X_LEDGE_L, X_LEDGE_R):
        v.line((xl, -APP_Y), (xl, APP_Y), "S-THIN")
    # 盖板凹槽线
    for x1, x2 in OPEN:
        for s in (1, -1):
            v.pl([(x1 - REB, s * B_HALF), (x1 - REB, s * (Y_OPEN_OUT + REB)),
                  (x2 + REB, s * (Y_OPEN_OUT + REB)), (x2 + REB, s * B_HALF)], "S-THIN")
    # 护边角钢 M-3（水平肢内边线）
    for xa, xb in ((-75, 0), (L, L + 75)):
        xe = xa if xa < 0 else xb
        v.line((xe, ANGLE_Y[0]), (xe, ANGLE_Y[1]), "S-STEEL")
    # 限位预埋板 M-2（埋于端墙内侧面）
    for xa, xb in ((-16, 0), (L, L + 16)):
        for y1, y2 in LIMIT_Y:
            v.hatch([(xa, y1), (xb, y1), (xb, y2), (xa, y2)], "SOLID", "S-STEEL")
    # 墩梁轮廓（虚线，位于坑底以下）
    if show_beams:
        for x1, x2, name in BEAMS:
            for xx in (x1, x2):
                if 0 < xx < L:
                    v.line((xx, -B_HALF), (xx, B_HALF), "S-HIDE")
    # 传感器预埋板 M-1 及水泥台
    for x1, x2 in PLATES_X:
        for y1, y2 in PLATE_Y:
            v.rect(x1, y1, x2, y2, "S-STEEL")
            xa = max(x1 - PAD, 0)
            xb = min(x2 + PAD, L)
            v.rect(xa, y1 - PAD, xb, y2 + PAD, "S-HIDE")
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            v.line((cx - 120, cy), (cx + 120, cy), "S-THIN")
            v.line((cx, cy - 120), (cx, cy + 120), "S-THIN")
    # 排水沟
    for s in (1, -1):
        for ln in gutter_lines(s):
            v.pl(ln, "S-THIN")
    # 集水坑
    for s in (1, -1):
        x1, x2, y1, y2 = SUMP
        v.rect(x1, s * y1, x2, s * y2, "S-THIN")
        v.line((x1, s * y1), (x2, s * y2), "S-THIN")
        v.line((x1, s * y2), (x2, s * y1), "S-THIN")
    # 坑底分水线（中线）
    v.line((0, 0), (L, 0), "S-HIDE")
    if show_platform:
        v.rect(25, -1585, L - 25, 1585, "S-HIDE2")
    if not show_site:
        return
    # 引道板
    for x1, x2 in APP:
        v.rect(x1, -APP_Y, x2, APP_Y, "S-CONC")
    # 换填范围
    v.rect(REPL_X[0], -REPL_Y, REPL_X[1], REPL_Y, "S-HIDE2")
    for (x1, x2) in APP_REPL:
        if x1 < 0:
            v.pl([(REPL_X[0], -APP_REPL_Y), (x1, -APP_REPL_Y), (x1, APP_REPL_Y),
                  (REPL_X[0], APP_REPL_Y)], "S-HIDE2")
        else:
            v.pl([(REPL_X[1], -APP_REPL_Y), (x2, -APP_REPL_Y), (x2, APP_REPL_Y),
                  (REPL_X[1], APP_REPL_Y)], "S-HIDE2")
    # 集水坑排水管 DN150
    for s in (1, -1):
        v.line((AX[2], s * SUMP[3]), (AX[2], s * 3550), "S-PIPE")
    # 电缆穿线管（②轴 -Y 侧检修口）
    cx, cy = AX[1] + 300, -1975
    v.circle((cx, cy), 40, "S-STEEL")
    v.pl([(cx, cy), (cx, -4300)], "S-PIPE")
    # 接地极及接地扁钢
    for xj, xw in ((-1200, X_LEFT), (L + 1200, X_RIGHT)):
        v.circle((xj, -4000), 120, "S-STEEL")
        v.line((xj - 120, -4000), (xj + 120, -4000), "S-STEEL")
        v.line((xj, -4120), (xj, -3880), "S-STEEL")
        xa = -60 if xw < 0 else L + 60
        v.pl([(xj, -4000), (xj, -2600), (xw, -2600), (xw, -1500), (xa, -1500)], "S-HIDE2")


def plan_axes(v, y_bub=5300, y_bub_b=6200, x_bub_l=-8700, x_bub_r=28700, ext=4500):
    for x, lb in zip(AX, AX_LABEL):
        v.line((x, -ext), (x, ext), "S-AXIS")
        for s, yb in ((1, y_bub), (-1, y_bub_b)):
            v.line((x, s * ext), (x, s * (yb - 200)), "S-THIN")
            v.axis_bubble(x, s * yb, lb)
    for y, lb in zip(AY, AY_LABEL):
        v.line((-7300, y), (27350, y), "S-AXIS")
        v.line((-7300, y), (x_bub_l + 200, y), "S-THIN")
        v.line((27350, y), (x_bub_r - 200, y), "S-THIN")
        v.axis_bubble(x_bub_l, y, lb)
        v.axis_bubble(x_bub_r, y, lb)


def sheet_plan(sh):
    v = sh.view(215, 440, 50)
    draw_plan_body(v, show_platform=False)
    plan_axes(v)
    p = sh.paper

    # ---------- 尺寸 ----------
    # 下方：第一道（端墙、传感器轴线），第二道（护边角钢间距、引道），第三道（总长）
    xs = [X_LEFT, 0, AX[0], AX[1], AX[2], AX[3], AX[4], L, X_RIGHT]
    v.chainh(xs, -Y_OUT, -4500, [None, "175※", "4850※", "5000※", "5000※", "4850※", "175※", None],
             ext=3)
    v.dimh(0, L, -Y_OUT, -5000, "20050※(两护边角钢间距)", ext=3, tx=7000)
    v.dimh(APP[0][0], APP[0][1], -APP_Y, -5000, ext=3)
    v.dimh(APP[1][0], APP[1][1], -APP_Y, -5000, ext=3)
    v.dimh(X_LEFT, X_RIGHT, -Y_OUT, -5500, ext=3, tx=7000)
    # 上方：检修口定位、墩梁/凸出部分定位
    xs2 = [X_LEFT]
    for x1, x2 in OPEN:
        xs2 += [x1, x2]
    xs2 = sorted(set(xs2 + [X_RIGHT]))
    v.chainh(xs2, Y_OUT, 4400, ext=3)
    xs3 = [X_LEFT, 1000, 4425, 5625, 9425, 10625, 14425, 15625, 19050, X_RIGHT]
    v.chainh(xs3, Y_OUT, 3900, ext=3)
    # 左侧：横向
    ys1 = [-Y_OUT, -Y_OPEN_OUT, -B_HALF, -1300, 1300, B_HALF, Y_OPEN_OUT, Y_OUT]
    v.chainv(ys1, X_LEFT, -7700, [None, None, None, "2600※", None, None, None], ext=3)
    v.chainv([-Y_WALL, -B_HALF, B_HALF, Y_WALL], X_LEFT, -8200, ext=3)
    # 右侧：换填范围
    v.chainv([-REPL_Y, -Y_OUT, Y_OUT, REPL_Y], REPL_X[1], 27800, ext=3)

    # ---------- 标注 ----------
    for x1, x2 in APP:
        xm = (x1 + x2) / 2
        v.text(xm, 1250, "混凝土引道板 YB-1", 3.0)
        d = -1 if x1 < 0 else 1
        v.arrow((xm - d * 1600, -500), (xm + d * 1600, -500))
        v.text(xm, -850, "i=0.8%", 2.5)
        v.text(xm, -2050, "引道下换填(底-1.500)", 2.5)
    # 坑底横坡及沟底纵坡
    v.text(2650, 300, "坑底-0.450(中线)", 2.5)
    for xm in ((AX[0] + AX[1]) / 2, (AX[1] + AX[2]) / 2, (AX[2] + AX[3]) / 2, (AX[3] + AX[4]) / 2):
        v.arrow((xm - 1200, 250), (xm - 1200, 1100))
        v.arrow((xm - 1200, -250), (xm - 1200, -1100))
        v.text(xm - 850, 700, "i=1%", 2.2, "ML", rot=90)
    for xm, d in (((AX[1] + AX[2]) / 2 + 800, 1), ((AX[2] + AX[3]) / 2 + 800, -1)):
        for s in (1, -1):
            v.arrow((xm - d * 700, s * 1250), (xm + d * 700, s * 1250))
            v.text(xm, s * 1020, "沟底i=0.5%", 2.2)
    # 引出标注
    v.leader([(AX[2] - 1500, 1525), (AX[2] - 2300, 2950)], "排水沟 宽150，起点深40", 2.8, "L")
    v.leader([(SUMP[0] + 100, SUMP[2] + 250), (AX[2] - 700, 2950)], "JSK-1 集水坑", 2.8, "L")
    v.leader([(AX[2], 3250), (AX[2] + 700, 2950)], "DN150排水管 i≥0.5% 接室外雨水井", 2.8, "R")
    v.leader([(AX[1] + 300, -3300), (AX[1] - 1100, -3700)], "φ40 PVC穿线管至秤房", 2.8, "L")
    v.leader([(PLATES_X[1][0] + 100, -1200), (AX[1] - 1500, -900)], "M-1", 2.8, "L")
    v.leader([(-8, 1500), (-1100, 2950)], "M-2 限位预埋板", 2.8, "L")
    v.leader([(-40, 700), (-1500, 2400)], "M-3 护边角钢", 2.8, "L")
    v.leader([(-400, -800), (-1500, -1300)], "端墙Q2", 2.8, "L")
    v.leader([(1100, -900), (2200, -650)], "ZL-2", 2.8, "R")
    v.leader([(AX[3] + 600, -900), (AX[3] + 1700, -650)], "ZL-1", 2.8, "R")
    v.leader([(AX[3] + 350, 1900), (AX[3] + 1300, 2950)], "检修口 GB-1", 2.8, "R")
    v.leader([(AX[2] - 2800, 1700), (AX[2] - 3400, 2400)], "侧墙Q1", 2.8, "L")
    v.text(13200, -3150, "级配砂石换填范围线(底标高-3.000，宽出基础外边线不小于1000)", 2.5)
    v.leader([(-1200, -4000), (-2400, -3700)], "JD-1 接地极", 2.8, "L")
    v.leader([(L + 1200, -4000), (L + 2400, -3700)], "JD-1 接地极", 2.8, "R")
    # 标高
    v.elev(2600, -1550, "-0.466(墙边)", "R")
    v.elev(-1000, 2050, "±0.000", "L")
    v.elev(2800, 2250, "+0.050", "R")
    # 剖切符号
    v.section_mark((-7000, 1300), (27050, 1300), "1", (0, 1))
    v.section_mark((AX[2], -3700), (AX[2], 3700), "2", (1, 0))
    v.section_mark((7525, -3700), (7525, 3700), "3", (1, 0))
    v.section_mark((200, -3700), (200, 3700), "4", (-1, 0))
    # 索引
    v.index_mark(-2600, 300, "1", "结施-05")
    v.line((-2600 + 250, 300), (-300, 50), "S-SYMB")
    v.index_mark(AX[1] + 1500, -2900, "2", "结施-05")
    v.line((AX[1] + 1250, -2800), (AX[1] + 400, -2100), "S-SYMB")

    p.detail_title(330, 300, None, "基础平面布置图", "1:50", h=7.0)

    # ---------- 说明 ----------
    notes = [
        "说明：",
        "1. 本图尺寸以mm计，标高以m计。±0.000为汽车衡周围地面设计标高，其绝对标高由总图确定，",
        "   且不宜低于135.000(1985国家高程基准)，以使坑底高于抗浮设防水位134.500。",
        "2. 图中带“※”的尺寸为厂家控制尺寸，施工放线前须与汽车衡厂家核对确认，有误及时整改。",
        "3. 基础为整体钢筋混凝土结构(底板+墩梁ZL+侧墙Q1+端墙Q2)，混凝土C35 P6 F250，配筋见结施-04。",
        "4. 基础底至-3.000范围原状土全部挖除，换填非冻胀性级配砂石，范围见本图及结施-03。",
        "5. 检修口共10处(盖板GB-1，用户自备)；③轴两侧检修口内设集水坑JSK-1，经DN150排水管排出。",
        "6. 排水沟沿侧墙内侧布置，宽150，起点深40，沟底纵坡0.5%，过②、④轴时经检修口内绕开",
        "   传感器水泥台，坡向③轴集水坑；排水沟详图见结施-05。",
        "7. 端部传感器预埋板紧贴端墙内侧放置，传感器中心距端墙内侧175※；秤台轮廓为示意。",
        "8. 接地极JD-1位置可根据现场调整，接地电阻不大于4Ω。",
    ]
    p.text_lines(40, 280, notes, 3.0, 1.75)

    # ---------- 图例 ----------
    lx, ly = 420, 282
    p.text(lx, ly, "图例：", 3.2, "TL")
    items = [
        ("S-CONC", "line", "钢筋混凝土墙体/引道板轮廓"),
        ("S-HIDE", "line", "墩梁边线/水泥台(坑底以下或不可见)"),
        ("S-HIDE2", "line", "换填范围线/秤台轮廓线(示意)"),
        ("S-PIPE", "line", "排水管/穿线管"),
        ("S-AXIS", "line", "定位轴线(传感器中心线)"),
        ("S-STEEL", "box", "传感器预埋板 M-1"),
        ("S-THIN", "sump", "集水坑 JSK-1"),
        ("S-STEEL", "jd", "接地极 JD-1"),
    ]
    yy = ly - 9
    for lyr, kind, s in items:
        if kind == "line":
            p.line((lx + 2, yy), (lx + 22, yy), lyr)
        elif kind == "box":
            p.rect(lx + 8, yy - 3, lx + 16, yy + 3, lyr)
        elif kind == "sump":
            p.rect(lx + 8, yy - 3, lx + 16, yy + 3, lyr)
            p.line((lx + 8, yy - 3), (lx + 16, yy + 3), lyr)
            p.line((lx + 8, yy + 3), (lx + 16, yy - 3), lyr)
        else:
            p.circle_p((lx + 12, yy), 2.4, lyr)
            p.line((lx + 9.6, yy), (lx + 14.4, yy), lyr)
            p.line((lx + 12, yy - 2.4), (lx + 12, yy + 2.4), lyr)
        p.text(lx + 27, yy, s, 2.8, "ML")
        yy -= 8.5

    # ---------- 预埋件及设备统计表 ----------
    rows = [
        ["编号", "名称", "规格", "数量", "备注"],
        ["M-1", "传感器预埋板", "-400×400×20 Q235B", "10块", "1:1水泥砂浆座浆"],
        ["M-2", "限位预埋板", "-320×150×16 Q235B", "4块", "锚筋2C16"],
        ["M-3", "护边角钢", "L75×75×7 L=3200", "2根", "锚筋9C16"],
        ["M-4", "检修口护口角钢", "L50×5", "10套", "锚筋C10"],
        ["GB-1", "检修口盖板", "900×600", "10块", "用户自备"],
        ["JSK-1", "集水坑", "400×400×400", "2个", "③轴两侧"],
        ["—", "排水管", "DN150 UPVC", "2根", "接室外雨水井"],
        ["—", "电缆穿线管", "φ40 PVC", "1根", "至秤房"],
        ["JD-1", "接地极", "L50×5 L=2300", "2根", "热镀锌"],
    ]
    p.text(640, 282, "预埋件及设备统计表", 3.5, "TL")
    p.table(612, 274, [18, 32, 48, 16, 38], rows, row_h=6.6, h=2.6)
