# -*- coding: utf-8 -*-
"""出图前重叠检查：文字与文字、文字与图线（含尺寸线）、文字与填充区域。

用法：python3 check_overlap.py [all|结施-01..结施-05]
输出各类重叠的数量及位置（图纸 mm 坐标），全部为 0 方可出图。
"""
import sys

from ezdxf import bbox
from shapely.geometry import box as sbox, LineString, Polygon
from shapely.strtree import STRtree
import build, combined as C
from cadlib import SHEET_SCALE as K

which = sys.argv[1] if len(sys.argv) > 1 else "all"
if which == "all":
    cad = build.build_sheet("结施-01", "汽车衡基础施工图", "见各图", C.sheet_all, size=C.SIZE)
else:
    build.register()
    num, title, scale, fn = [s for s in build.SHEETS if s[0] == which][0]
    cad = build.build_sheet(num, title, scale, fn)
msp = cad.msp

texts, lines, fills = [], [], []
def add_line_entity(e, src):
    t = e.dxftype()
    if t == "LINE":
        lines.append((LineString([(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]), src))
    elif t == "LWPOLYLINE":
        pts = [(p[0], p[1]) for p in e.get_points("xy")]
        if e.closed:
            pts.append(pts[0])
        if len(pts) > 1:
            lines.append((LineString(pts), src))
    elif t == "CIRCLE":
        c = e.dxf.center
        lines.append((sbox(c.x, c.y, c.x, c.y).buffer(e.dxf.radius).exterior, src))

for e in msp:
    t = e.dxftype()
    if t == "TEXT":
        texts.append((e.dxf.text, e, e.dxf.layer))
    elif t == "DIMENSION":
        for ve in e.virtual_entities():
            if ve.dxftype() == "TEXT":
                texts.append(("[尺寸]" + ve.dxf.text, ve, "DIM"))
            elif ve.dxftype() == "MTEXT":
                texts.append(("[尺寸]" + ve.plain_text(), ve, "DIM"))
            else:
                add_line_entity(ve, "S-DIM")
    elif t == "HATCH":
        if e.dxf.solid_fill:
            continue
        poly = None
        for path in e.paths:
            try:
                pts = [(v[0], v[1]) for v in path.vertices]
            except AttributeError:
                continue
            if len(pts) >= 3:
                q = Polygon(pts).buffer(0)
                poly = q if poly is None else poly.symmetric_difference(q)
        if poly is not None:
            fills.append((poly, e.dxf.layer + ":" + e.dxf.pattern_name))
    else:
        add_line_entity(e, e.dxf.layer)

tb = []
sh = 0.15 * K
for s, e, lyr in texts:
    if not s.replace("[尺寸]", "").strip():
        continue
    b = bbox.extents([e], fast=False)
    if not b.has_data:
        continue
    g = sbox(b.extmin.x + sh, b.extmin.y + sh, b.extmax.x - sh, b.extmax.y - sh)
    tb.append((s, g))

def P(g):
    c = g.bounds
    return f"({c[0]/K:.0f},{c[1]/K:.0f})"

out = {"文字-文字": [], "文字-图线": [], "文字-填充": []}
tree = STRtree([g for _, g in tb])
for i, (s, g) in enumerate(tb):
    for j in tree.query(g):
        if j > i and g.intersects(tb[j][1]) and g.intersection(tb[j][1]).area > 0.04 * min(g.area, tb[j][1].area):
            out["文字-文字"].append(f"{P(g)} '{s}' <-> '{tb[j][0]}'")
ltree = STRtree([l for l, _ in lines])
for s, g in tb:
    hit = [lines[k][1] for k in ltree.query(g) if lines[k][0].intersects(g)]
    if hit:
        out["文字-图线"].append(f"{P(g)} '{s}' x {sorted(set(hit))}")
ftree = STRtree([f for f, _ in fills])
for s, g in tb:
    hit = [fills[k][1] for k in ftree.query(g) if fills[k][0].intersection(g).area > 0.25 * g.area]
    if hit:
        out["文字-填充"].append(f"{P(g)} '{s}' in {sorted(set(hit))}")
for k, v in out.items():
    print(f"== {k}: {len(v)}")
    for x in v:
        print("  ", x)
sys.exit(1 if any(out.values()) else 0)
