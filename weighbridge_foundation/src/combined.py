# -*- coding: utf-8 -*-
"""全部内容合并为一张 A0 加长图（2080×841）。"""
from ezdxf import bbox

import geom as G
import s01_notes as S1
import s02_plan as S2
import s03_sections as S3
import s04_rebar as S4
import s05_details as S5
from cadlib import CAD, SHEET_SCALE, View, cjk_width

SIZE = (2080.0, 841.0)

# 合并后图内互相引用改为图名
REF_REPLACE = [
    ("(见结施-02、03)", "(见基础平面布置图及剖面图)"),
    ("见结施-04钢筋表", "见钢筋表"),
    ("见结施-05", "见预埋件材料表"),
]

_EXT_CACHE = {}


def extents(fn, k):
    """视图 fn 在比例 1:k 下的图纸范围 (x1, y1, x2, y2)，相对视图原点。"""
    key = (fn, k)
    if key not in _EXT_CACHE:
        cad = CAD(font="NotoSansCJK-Regular.ttc")
        v = cad.sheet(0, 0).view(0, 0, k)
        fn(v)
        e = bbox.extents(cad.msp, fast=False)
        _EXT_CACHE[key] = (e.extmin.x / SHEET_SCALE, e.extmin.y / SHEET_SCALE,
                           e.extmax.x / SHEET_SCALE, e.extmax.y / SHEET_SCALE)
    return _EXT_CACHE[key]


def title_width(num, name, scale, h):
    w = cjk_width(name) * h
    if scale:
        w += 4 + cjk_width(scale) * h * 0.7
    if num is not None:
        w += 15
    return w


def place(sh, fn, k, left, top, name=None, num=None, scale=None, th=5.0, width=None):
    """把视图 fn 放在左上角 (left, top)；标题居中写在视图下方。返回视图底部 y（含标题）。"""
    x1, y1, x2, y2 = extents(fn, k)
    w = x2 - x1
    off = 0.0 if width is None else (width - w) / 2
    v = sh.view(left + off - x1, top - y2, k)
    fn(v)
    bottom = top - (y2 - y1)
    if name:
        span = w if width is None else width
        tw = title_width(num, name, scale or f"1:{k}", th)
        ty = bottom - th - 7
        sh.paper.detail_title(left + (span - tw) / 2, ty, num, name, scale or f"1:{k}", h=th)
        bottom = ty - 4
    return bottom


def row(sh, items, left, top, gap=18.0):
    """横向排列一行视图，items: (fn, k, name, num, scale)。返回该行最低处 y。"""
    x = left
    lowest = top
    for fn, k, name, num, scale in items:
        x1, y1, x2, y2 = extents(fn, k)
        w = max(x2 - x1, title_width(num, name, scale or f"1:{k}", 5.0) if name else 0)
        b = place(sh, fn, k, x, top, name, num, scale, width=w)
        lowest = min(lowest, b)
        x += w + gap
    return lowest


def column_header(p, x, y, s, h=7.0):
    p.text(x, y, s, h, "BL")
    w = cjk_width(s) * h
    p.pl([(x, y - 1.5), (x + w, y - 1.5)], "S-SYMB", width=0.7)


def fix_refs(s):
    for a, b in REF_REPLACE:
        s = s.replace(a, b)
    return s


def sheet_all(sh):
    old = G.REF["detail"]
    G.REF["detail"] = "—"   # 详图在本图内
    try:
        _sheet_all(sh)
    finally:
        G.REF["detail"] = old


def _sheet_all(sh):
    p = sh.paper
    top = 818.0

    # ======== A 列：平面、剖面（x 35~805）========
    xa = 35.0
    b = place(sh, S2.plan_view, 50, xa, top, "基础平面布置图", th=6.5)
    b = place(sh, S3.long_section, 50, xa, b - 12, "1-1 剖面", th=6.0)
    b = row(sh, [(S3.section_22, 30, "2-2 剖面", None, None),
                 (S3.section_33, 30, "3-3 剖面", None, None),
                 (S3.section_44, 30, "4-4 剖面(端墙内侧立面)", None, None)], xa, b - 12, gap=8)
    yb_a = b - 12
    place(sh, S4.raft_plan, 50, xa, yb_a, "底板配筋平面图", th=5.5)
    S2.plan_legend(p, 500, yb_a)
    S2.plan_table(p, 652, yb_a - 10)

    # ======== B 列：配筋（x 822~1255）========
    xb = 822.0
    b = row(sh, [(S4.zl1_elev, 30, "ZL-1 立面配筋图", None, None),
                 (S4.zl1_section, 20, "ZL-1 截面", None, None)], xb, top, gap=22)
    b = row(sh, [(S4.zl2_section, 20, "ZL-2及端墙Q2 截面", None, None),
                 (S4.q1_section, 20, "侧墙Q1截面(Q3同)", None, None)], xb, b - 30, gap=30)
    b = row(sh, [(S4.yb1_plan, 50, "YB-1 引道板配筋平面", None, None),
                 (S4.yb1_section, 20, "YB-1 与端墙搭接", None, None)], xb, b - 30, gap=30)
    yb_s, _ = S4.draw_schedule(p, xb, b - 40)
    p.text_lines(xb + 216, b - 40, S4.REBAR_NOTES, 3.0, 1.7)

    # ======== C 列：节点及预埋件（x 1270~1760）========
    xc = 1270.0
    b = row(sh, [(S5.node_end_wall, 10, "端墙顶部节点", 1, None),
                 (S5.opening_plan, 15, "检修口平面(③轴)", 2, None),
                 (S5.opening_section, 15, "A-A 剖面", None, None)], xc, top, gap=16)
    b = row(sh, [(S5.gutter_cross, 20, "排水沟过②④轴做法", 3, None),
                 (S5.grounding, 30, "接地做法", 4, None),
                 (S5.conduit, 20, "电缆穿线管做法", 5, None),
                 (S5.gb1, 10, "GB-1 检修口盖板", None, None)], xc, b - 40, gap=16)
    b = row(sh, [(S5.m1, 10, "M-1 传感器预埋板(10块)", None, None),
                 (S5.m2, 5, "M-2 限位预埋板(4块)", None, None),
                 (S5.m4, 10, "M-4 护口角钢(10套)", None, None)], xc, b - 40, gap=20)
    # M-3：立面 1:20 + 截面 1:5
    top_m3 = b - 40
    x1, y1, x2, y2 = extents(lambda v: S5.m3(v, v), 20)
    v_el = sh.view(xc - x1, top_m3 - 12, 20)
    v_sec = View(sh, xc - x1 + 215, top_m3 - 12 + 20, 5)
    S5.m3(v_el, v_sec)
    p.detail_title(xc + 60, top_m3 - 62, None, "M-3 护边角钢(2根)", "1:20、1:5", h=5.0)
    S5.parts_table(p, xc + 330, top_m3 - 8)
    y = p.text_lines(xc, top_m3 - 90, S5.DETAIL_NOTES, 3.0, 1.7)

    c35, yb, cush, steel = S1.quantities()
    rows = [["项目", "规格", "单位", "数量", "备注"],
            ["基础混凝土", "C35 P6 F250", "m³", f"{c35:.1f}", "底板、墩梁、墙"],
            ["引道板混凝土", "C35 F250", "m³", f"{yb:.1f}", "2块"],
            ["垫层混凝土", "C15", "m³", f"{cush:.1f}", ""],
            ["级配砂石换填", "λc≥0.97", "m³", "约440", "压实方，含引道下"],
            ["钢筋", "HRB400", "t", f"{steel:.2f}", "见钢筋表"],
            ["预埋件及盖板钢材", "Q235B", "t", "1.00", "见预埋件材料表"]]
    y -= 14
    p.text(xc + 110, y, "主要工程量(参考，以实际为准)", 4.0, "TC")
    p.table(xc, y - 7, [44, 40, 20, 30, 86], rows, row_h=6.6, h=3.0)

    # ======== D 列：结构设计总说明（x 1775~2068）========
    xd = 1775.0
    column_header(p, xd, top - 6, "结构设计总说明", h=7.0)
    secs = [(t, [fix_refs(s) for s in items]) for t, items in S1.COL1 + S1.COL2 + S1.COL3]
    S1.write_col(p, xd, top - 20, secs, 70, h=4.0, gap=1.62)
