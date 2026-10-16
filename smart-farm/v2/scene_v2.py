"""v2: 智慧农业科普展厅 — the client's own layout (whole tiled terrace, kerb to red wall).

Built from the client's markings in the chat record:
  * leans on the red wall, kerb end aligned with the raised-platform kerb, street side up to the parapet
  * single-pitch roof: high on the corridor side, low on the street side
  * sliding glass on the street side, corridor stainless railing sealed with glass
  * door cut into the corridor parapet near the red wall
  * glass-fronted seed-germination window along the kerb
  * designed red-wall feature wall, outdoor signage

Two kinds of output:
  * --mode montage : renders only the new work over the client's site photos (calibrated cameras,
                     existing walls are holdouts), then composites onto the photo
  * --mode 3d      : full 3D scene for interior / aerial / plan views

    python scene_v2.py --mode montage --shots p_platform,p_corr_across --samples 96
    python scene_v2.py --mode 3d --shots interior_in,interior_wall,aerial,plan --res 1920x1280 --samples 96

Coordinates: x along the terrace from the kerb (0) to the red wall (17.8); y from the corridor
parapet (0) to the street parapet (8.5); z up from the terrace tiles.
"""
import argparse
import json
import math
import os
import random
import sys
import time

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import scene as S  # v1 helpers: materials, mesh builder, plants, text  # noqa: E402
from scene import M, MB, collection, instance, link, plane_uv, rosette_mesh, text  # noqa: E402

TEX2 = os.path.join(HERE, "tex")
CAL = json.load(open(os.path.join(HERE, "calib.json")))
L, W, K = 17.8, 8.5, 0.9
Z_HI, Z_LO = 3.35, 2.6                   # roof height at corridor side (under the corridor beam) / street side
ALC = 2.4                                # louver section at the corridor end; its end is in line with the red wall
PIER = L - ALC                           # last corridor pier (terrace-side photo), louvers run from here to L
COLS = [-3.0, 7.0, 12.0, PIER]           # corridor columns (x), located from the corridor photos
DOOR = (PIER - 1.85, PIER - 0.35)        # door in the last bay, right next to the louver section
PW = 6.0                                 # raised platform width (estimate); another terrace lies beyond it
XS = -PW - 14.0                          # how far the existing site is modelled towards the other terrace
GATE = (-PW - 1.9, -PW - 0.3)            # existing sliding gate + stainless arch onto the other terrace
HC = 0.35                                # corridor parapet top above the terrace (photos: 0.2-0.45)
STATION = (-PW / 2, W / 2)               # weather / environment monitoring station, middle of the raised platform
STATION_ROT = 45.0                       # screen turned so one face looks at the hall + corridor, the other back
BEAM = 3.45                              # underside of the corridor edge beam
PHASE1_X = 11.8                          # phase 1 = x 11.8..17.8 (6.0 x 8.5 = 51 m2)
POSTS_X = [0.12, 4.45, 8.9, 13.35, 17.65]
RAFTERS = [0.06 + i * (L - 0.12) / 8 for i in range(9)]          # main rafters ~2.2 m
BARS = [0.06 + i * (L - 0.12) / 16 for i in range(17)]            # aluminium glazing bars ~1.1 m
MODE = "3d"


def roof_z(y):
    return Z_HI - (Z_HI - Z_LO) * y / W


def holdout(ob):
    if ob is not None and MODE == "montage":
        ob.is_holdout = True
    return ob


# ---------------------------------------------------------------- extra materials
def make_materials_v2():
    def simple(name, color, rough=0.5, metal=0.0, spec=0.5):
        m, nb, b = S.new_mat(name)
        S.set_bsdf(b, color, rough, metal, spec)
        M[name] = m
        return m, nb, b

    m = M["glass_roof"]
    for node in m.node_tree.nodes:
        if node.bl_idname == "ShaderNodeMath" and node.operation == "MULTIPLY":
            node.inputs[1].default_value = 0.22
        if node.bl_idname == "ShaderNodeBsdfTransparent":
            node.inputs["Color"].default_value = (0.93, 0.95, 0.95, 1)
    m, nb, b = S.new_mat("floor_v2")
    p = nb.world_pos()
    n1 = nb.noise(p, 40, 3)
    n2 = nb.noise(p, 1.5, 3)
    c = nb.ramp(n1, [(0.35, (0.50, 0.50, 0.48)), (0.65, (0.60, 0.60, 0.57))])
    c = nb.mix_rgb(nb.math("MULTIPLY", n2, 0.25), c, (0.45, 0.45, 0.43))
    nb.l(c, b.inputs["Base Color"])
    S.set_bsdf(b, rough=0.45, spec=0.5)
    M["floor_v2"] = m
    simple("path_green", (0.10, 0.30, 0.18), 0.5)
    simple("sign_green", (0.025, 0.11, 0.07), 0.4, 0.2)
    simple("seat_a", (0.75, 0.42, 0.10), 0.5)
    simple("seat_b", (0.05, 0.30, 0.20), 0.5)
    simple("seat_c", (0.80, 0.78, 0.72), 0.5)
    simple("fish_water", (0.10, 0.30, 0.35), 0.05, 0.0, 0.8)
    simple("fish", (0.85, 0.35, 0.08), 0.4)
    simple("wood_slat", (0.32, 0.19, 0.10), 0.6)
    m, nb, b = S.new_mat("letters_white")
    S.set_bsdf(b, (0.92, 0.92, 0.9), 0.35)
    b.inputs["Emission Color"].default_value = (1.0, 0.95, 0.85, 1)
    b.inputs["Emission Strength"].default_value = 6.0 if S.NIGHT else 0.0
    M["letters_white"] = m
    for name, path, emit in (("timeline", "wall_timeline.jpg", 0.0), ("totem", "totem.jpg", 0.4),
                             ("fascia", "fascia.jpg", 2.5 if S.NIGHT else 0.25),
                             ("germ_face", "germ_face.jpg", 0.0), ("station_led", "station_led.png", 3.0)):
        m, nb, b = S.new_mat(name)
        t = nb.n("ShaderNodeTexImage")
        t.image = bpy.data.images.load(os.path.join(TEX2, path))
        nb.l(t.outputs["Color"], b.inputs["Base Color"])
        S.set_bsdf(b, rough=0.5)
        if emit:
            nb.l(t.outputs["Color"], b.inputs["Emission Color"])
            b.inputs["Emission Strength"].default_value = emit
        M[name] = m
    for i in range(6):
        m, nb, b = S.new_mat(f"photo{i}")
        t = nb.n("ShaderNodeTexImage")
        t.image = bpy.data.images.load(os.path.join(TEX2, f"photo{i}.jpg"))
        nb.l(t.outputs["Color"], b.inputs["Base Color"])
        S.set_bsdf(b, rough=0.3)
        M[f"photo{i}"] = m


# ---------------------------------------------------------------- existing site (holdouts in montage)
def build_existing():
    coll = collection("existing")
    tiles, white, red, caps, rails, conc, floor_c = MB(), MB(), MB(), MB(), MB(), MB(), MB()
    # corridor parapet with the new door gap, coping and railing
    cf = HC - 0.65                                   # corridor floor level
    for a, b in ((XS, GATE[0]), (GATE[1], DOOR[0]), (DOOR[1], PIER - 0.25)):
        tiles.box(a, b, -0.25, 0.0, cf - 0.3, HC - 0.05)
        caps.box(a, b, -0.28, 0.03, HC - 0.05, HC)
        x = a + 0.3
        while x < b - 0.1:
            rails.tube((x, -0.12, HC), (x, -0.12, HC + 0.38), 0.02, 8)
            x += 1.25
        rails.tube((a + 0.05, -0.12, HC + 0.4), (b - 0.05, -0.12, HC + 0.4), 0.026, 12)
    for cx in COLS:
        white.box(cx - 0.25, cx + 0.25, -0.55, 0.0, cf, BEAM)
    # corridor floor, ceiling beam and slab, inner wall
    floor_c.box(XS, L, -2.9, -0.25, cf - 0.2, cf)
    white.box(XS, L + 0.25, -0.55, 0.0, BEAM, BEAM + 0.5)
    white.box(XS, L + 0.25, -2.9, -0.25, BEAM + 0.35, BEAM + 0.5)
    white.box(XS, L + 0.25, -3.15, -2.9, cf, BEAM + 0.35)
    # upper floors: red-band parapets like the photos
    for k in (1, 2):
        z = BEAM + 0.5 + (k - 1) * 3.4
        red.box(XS, PIER, -0.3, 0.0, z, z + 0.95)
        caps.box(XS, PIER, -0.33, 0.03, z + 0.95, z + 1.02)
        white.box(XS, L + 0.25, -0.55, 0.0, z + 2.85, z + 3.4)
        white.box(XS, L + 0.25, -3.15, -2.9, z, z + 3.4)
        white.box(XS, L + 0.25, -2.9, -0.3, z + 3.25, z + 3.4)
    white.box(XS, L + 0.25, -9.0, -3.15, 0.0, 10.55)
    # grey slogan cladding above the louver section (terrace-side photo)
    caps.box(PIER + 0.25, L, -0.12, 0.0, BEAM + 0.5, 10.55)
    # street parapet with piers
    tiles.box(XS, L, W, W + 0.25, 0.0, 1.35)
    caps.box(XS, L, W - 0.02, W + 0.27, 1.35, 1.4)
    x = XS + 0.5
    while x < L and MODE == "3d":
        white.box(x, x + 0.3, W, W + 0.25, 1.4, 1.75)
        x += 3.0
    # red block: its face is the hall's end wall; on the corridor side it stands ~1 m behind the end louvers
    red.box(L, L + 7.0, 0.0, W + 3.0, 0.0, 9.8)
    red.box(L + 1.2, L + 7.0, -9.0, 0.0, 0.0, 9.8)
    for z in (2.85, 5.95, 7.85):
        caps.box(L - 0.02, L + 7.0, 0.0, W + 3.0, z, z + 0.16)
        caps.box(L + 1.18, L + 7.0, -9.0, 0.0, z, z + 0.16)
    white.box(L - 0.22, L, 0.8, W, 0.0, 0.8)
    red.box(L, L + 0.25, 0.0, 0.8, 0.0, BEAM + 0.5)            # red frame at the louver/red-wall corner
    # louver section at the corridor end: solid sill + horizontal fins, side (facing the hall) and end
    louv = MB()
    for (x0, x1, y0, y1) in ((PIER + 0.25, L, -0.25, 0.0), (L, L + 0.25, -2.9, -0.25)):
        tiles.box(x0, x1, y0, y1, cf - 0.3, cf + 0.85)
        caps.box(x0, x1, y0 - 0.02, y1 + 0.02, cf + 0.85, cf + 0.9)
        z = cf + 1.2
        while z < BEAM - 0.1:
            louv.box(x0, x1, y0, y1, z, z + 0.09)
            z += 0.42
    for (x0, y0, y1) in ((PIER + 0.25, -0.25, 0.0), ((PIER + 0.25 + L) / 2 - 0.08, -0.25, 0.0), (L - 0.16, -0.25, 0.0)):
        red.box(x0, x0 + 0.16, y0, y1, cf + 0.9, BEAM)
    red.box(L, L + 0.25, -1.65, -1.5, cf + 0.9, BEAM)
    # raised platform beyond the kerb, the other terrace beyond it, existing steps and gate
    conc.box(-PW, 0.0, -0.25, W + 0.25, 0.0, K)
    conc.box(XS, L + 7.0, -9.0, W + 3.0, -0.3, -0.001)
    steps = MB()
    for k, (h, d) in enumerate(((0.3, 0.9), (0.6, 0.6), (0.9, 0.3))):
        steps.box(-PW - d, -PW, 1.6, 2.8, 0.0, h - 0.02)
    gate = MB()
    gate.box(GATE[0], GATE[1], -0.15, -0.1, cf + 0.05, HC + 0.35)
    for k in range(9):
        gx = GATE[0] + 0.1 + k * (GATE[1] - GATE[0] - 0.2) / 8
        gate.box(gx - 0.012, gx + 0.012, -0.14, -0.11, cf + 0.05, HC + 0.35)
    ra = (GATE[1] - GATE[0]) / 2
    gc = (GATE[0] + GATE[1]) / 2
    for r in (ra, ra - 0.12):
        pts = [(gc + r * math.cos(math.pi * t / 16), -0.12, HC + 1.4 + r * math.sin(math.pi * t / 16)) for t in range(17)]
        for a, b in zip(pts, pts[1:]):
            gate.tube(a, b, 0.018, 8)
        gate.tube((gc - r, -0.12, HC), (gc - r, -0.12, HC + 1.4), 0.018, 8)
        gate.tube((gc + r, -0.12, HC), (gc + r, -0.12, HC + 1.4), 0.018, 8)
    objs = [tiles.build("parapet_tiles", "wall_tile", coll=coll), white.build("white_walls", "paint_white", coll=coll),
            red.build("red_walls", "paint_red", coll=coll), caps.build("caps", "cap_stone", coll=coll),
            rails.build("rails", "steel", smooth=True, coll=coll), conc.build("platform", "concrete", coll=coll),
            floor_c.build("corridor_floor", "floor_tile", coll=coll), louv.build("louver_fins", "paint_white", coll=coll),
            steps.build("old_steps", "wood_slat", coll=coll), gate.build("old_gate", "steel", coll=coll)]
    # bulletin boards on the street parapet (existing, kept)
    for i, cx in enumerate((3.0, 9.5)):
        objs.append(plane_uv(f"board{i}", (cx, W - 0.01, 0.85), (2.8, 0.9), (math.radians(90), 0, 0),
                             f"board{1 + i}", coll))
    for ob in objs:
        holdout(ob)
    if MODE == "3d":
        build_context()
        cf = HC - 0.65
        for x in (9.5, 14.0, 16.6):
            ld = bpy.data.lights.new("corr", "AREA")
            ld.size = 0.4
            ld.energy = 120
            ld.color = (1.0, 0.95, 0.88)
            lo = bpy.data.objects.new("corr_light", ld)
            lo.location = (x, -1.5, BEAM + 0.3)
            link(lo, coll)


def build_context():
    ctx = collection("context")
    g = MB()
    g.box(-600, 600, -600, 600, -9.2, -9.0)
    g.build("ground", "ground", coll=ctx)
    rnd = random.Random(4)
    placed = []
    for i in range(70):
        for _ in range(60):
            ang = rnd.uniform(-math.pi, math.pi)
            dist = rnd.uniform(55, 280)
            cx, cy = 9 + dist * math.cos(ang), 4 + dist * math.sin(ang)
            if -30 < cx < 50 and -40 < cy < 0:
                continue
            if all((cx - px) ** 2 + (cy - py) ** 2 > 30 ** 2 for px, py in placed):
                break
        placed.append((cx, cy))
        tall = dist > 100 and rnd.random() < 0.55
        h = rnd.uniform(40, 85) if tall else rnd.uniform(16, 26)
        w = rnd.uniform(15, 24) if tall else rnd.uniform(24, 42)
        tb = MB()
        tb.box(-w / 2, w / 2, -7, 7, -9.0, h - 9.0)
        ob = tb.build(f"tower{i}", f"tower{rnd.randrange(5)}", coll=ctx)
        ob.location = (cx, cy, 0)
        ob.rotation_euler = (0, 0, math.atan2(cy - 4, cx - 9) + math.pi / 2)
    tr = MB()
    for (tx, ty) in [(-12, 16), (26, 15), (30, 4)]:
        tr.tube((tx, ty, -9), (tx, ty, -2), 0.25, 8)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=3.2, location=(tx, ty, -0.5))
        ob = bpy.context.active_object
        ob.data.materials.append(M["tree_canopy"])
        md = ob.modifiers.new("d", "DISPLACE")
        t = bpy.data.textures.new("c", "CLOUDS")
        t.noise_scale = 1.0
        md.texture = t
        md.strength = 1.2
        for c in ob.users_collection:
            c.objects.unlink(ob)
        ctx.objects.link(ob)
    tr.build("trunks", "bark", coll=ctx)


# ---------------------------------------------------------------- the hall: structure and envelope
def build_shell():
    coll = collection("hall")
    roof_coll = collection("hall_roof")
    fr, rf = MB(), MB()
    S_ = 0.08
    # posts on three lines; beams along x
    for x in POSTS_X:
        for y in (0.12, W - 0.12):
            fr.box(x - S_ / 2, x + S_ / 2, y - S_ / 2, y + S_ / 2, 0.0, roof_z(y))
        if 0.5 < x < L - 0.5:
            fr.box(x - S_ / 2, x + S_ / 2, W / 2 - S_ / 2, W / 2 + S_ / 2, 0.0, roof_z(W / 2))
    for y in (0.12, W / 2, W - 0.12):
        z = roof_z(y)
        fr.box(0.0, L - 0.02, y - 0.05, y + 0.05, z - 0.16, z)
    # rafters + purlins (roof plane)
    for x in RAFTERS:
        rf.beam((x, -0.02, roof_z(-0.02) + 0.04), (x, W + 0.15, roof_z(W + 0.15) + 0.04), 0.05, 0.07)
    bars = MB()
    for x in BARS:
        bars.beam((x, -0.02, roof_z(-0.02) + 0.095), (x, W + 0.15, roof_z(W + 0.15) + 0.095), 0.03, 0.02)
    bars.build("glazing_bars", "steel_brushed", coll=roof_coll)
    # roof covering (clear PC) + flashing at the red wall and the corridor beam
    rg = MB()
    rg.poly([(0.0, -0.02, roof_z(-0.02) + 0.11), (L, -0.02, roof_z(-0.02) + 0.11),
             (L, W + 0.18, roof_z(W + 0.18) + 0.11), (0.0, W + 0.18, roof_z(W + 0.18) + 0.11)])
    rg.build("roof_pc", "glass_roof", coll=roof_coll)
    fl = MB()
    fl.beam((L - 0.04, -0.02, roof_z(-0.02) + 0.18), (L - 0.04, W + 0.18, roof_z(W + 0.18) + 0.18), 0.08, 0.16)
    fl.beam((0.0, -0.02, roof_z(-0.02) + 0.16), (0.0, W + 0.18, roof_z(W + 0.18) + 0.16), 0.08, 0.12)
    fl.box(0.0, L, W + 0.12, W + 0.3, Z_LO - 0.12, Z_LO + 0.04)            # gutter over street parapet
    fl.build("flashing_gutter", "frame", coll=roof_coll, bevel=0.004)
    # roof vents near the high side, slightly open
    for xc in (3.0, 8.9, 14.8):
        vb = MB()
        vg = MB()
        y0, y1 = 0.35, 1.35
        lift = 0.18
        pts = [(xc - 0.6, y0, roof_z(y0) + 0.13 + lift), (xc + 0.6, y0, roof_z(y0) + 0.13 + lift),
               (xc + 0.6, y1, roof_z(y1) + 0.13), (xc - 0.6, y1, roof_z(y1) + 0.13)]
        vg.poly(pts)
        for a, b in zip(pts, pts[1:] + pts[:1]):
            vb.beam(a, b, 0.04, 0.04)
        vb.build("vent_frame", "frame", coll=roof_coll)
        vg.build("vent_glass", "glass_roof", coll=roof_coll)
    fr.build("frame", "frame", coll=coll, bevel=0.005)
    rf.build("roof_frame", "frame", coll=roof_coll, bevel=0.004)

    gl, gf = MB(), MB()
    # corridor side: glass sealing the railing, coping to roof (door bay left open for the door)
    yg = 0.04
    segs = [(0.0, DOOR[0] - 0.05), (DOOR[1] + 0.05, PIER - 0.25)]
    for a, b in segs:
        gl.poly([(a, yg, HC), (b, yg, HC), (b, yg, roof_z(yg)), (a, yg, roof_z(yg))])
        gf.box(a, b, yg - 0.03, yg + 0.03, HC, HC + 0.05)
        gf.box(a, b, yg - 0.03, yg + 0.03, 2.3, 2.35)
    for x in BARS:
        if not (DOOR[0] - 0.1 < x < DOOR[1] + 0.1) and x < PIER - 0.25:
            gf.box(x - 0.025, x + 0.025, yg - 0.03, yg + 0.03, HC, roof_z(yg))
    # louver section: glass on the hall side (client: seal the louvers, LED strips + potted plants)
    yl = 0.12
    gl.poly([(PIER + 0.25, yl, 0.0), (L - 0.02, yl, 0.0), (L - 0.02, yl, roof_z(yl)), (PIER + 0.25, yl, roof_z(yl))])
    for x in (PIER + 0.25, (PIER + 0.25 + L) / 2, L - 0.05):
        gf.box(x - 0.025, x + 0.025, yl - 0.03, yl + 0.03, 0.0, roof_z(yl))
    for z in (0.0, 2.35):
        gf.box(PIER + 0.25, L - 0.02, yl - 0.03, yl + 0.03, z, z + 0.05)
    # threshold step from the corridor up into the hall
    stp = MB()
    stp.box(DOOR[0], DOOR[1], -0.3, 0.3, HC - 0.65, 0.0)
    stp.build("door_step", "floor_v2", coll=coll)
    # door (glass, double leaf) + transom
    gf.box(DOOR[0] - 0.05, DOOR[0], -0.2, 0.06, HC - 0.65, roof_z(0))
    gf.box(DOOR[1], DOOR[1] + 0.05, -0.2, 0.06, HC - 0.65, roof_z(0))
    gf.box(DOOR[0], DOOR[1], -0.2, 0.06, 2.35, 2.42)
    mid = (DOOR[0] + DOOR[1]) / 2
    for a, b in ((DOOR[0], mid - 0.01), (mid + 0.01, DOOR[1])):
        gf.box(a, b, -0.1, -0.06, 0.0, 0.08)
        gf.box(a, a + 0.04, -0.1, -0.06, 0.0, 2.35)
        gf.box(b - 0.04, b, -0.1, -0.06, 0.0, 2.35)
        gl.poly([(a + 0.04, -0.08, 0.08), (b - 0.04, -0.08, 0.08), (b - 0.04, -0.08, 2.33), (a + 0.04, -0.08, 2.33)])
    gl.poly([(DOOR[0], -0.07, 2.42), (DOOR[1], -0.07, 2.42), (DOOR[1], -0.07, roof_z(0)), (DOOR[0], -0.07, roof_z(0))])
    hd = MB()
    for x in (mid - 0.12, mid + 0.12):
        hd.tube((x, -0.13, 0.9), (x, -0.13, 1.6), 0.014, 10)
    hd.build("door_handles", "steel", smooth=True, coll=coll)
    # street side: sliding windows above the parapet (two tracks, a few panes slid open)
    ys = W - 0.06
    for i in range(16):
        a, b = BARS[i] + 0.03, BARS[i + 1] - 0.03
        yy = ys - (0.05 if i % 2 else 0.0)
        off = 0.0
        if i in (2, 5, 9):
            off = (b - a) * 0.45
        a2, b2 = a + off, b + off * 0.0 if i % 2 else b
        zt = roof_z(yy) - 0.02
        gl.poly([(a2, yy, 1.42), (b2, yy, 1.42), (b2, yy, zt), (a2, yy, zt)])
        for (p, q, r, s) in ((a2, a2 + 0.04, 1.4, zt), (b2 - 0.04, b2, 1.4, zt), (a2, b2, 1.4, 1.45), (a2, b2, zt - 0.05, zt)):
            gf.box(p, q, yy - 0.02, yy + 0.02, r, s)
    gf.box(0.0, L, ys - 0.1, ys + 0.03, 1.36, 1.42)
    # kerb end wall: glass from the platform top to the roof
    xe = 0.03
    gl.poly([(xe, 0.0, K), (xe, W, K), (xe, W, roof_z(W)), (xe, 0.0, roof_z(0))])
    for y in [0.0 + i * W / 6 for i in range(7)]:
        gf.box(xe - 0.03, xe + 0.03, y - 0.03, y + 0.03, K, roof_z(y))
    gf.box(xe - 0.04, xe + 0.04, 0.0, W, K, K + 0.08)
    gf.box(xe - 0.03, xe + 0.03, 0.0, W, 2.2, 2.25)
    gl.build("glazing", "glass", coll=coll)
    gf.build("glazing_frames", "frame", coll=coll, bevel=0.003)

    # new floor inside the hall
    fl = MB()
    fl.box(0.42, L - 0.22, 0.0, W, 0.0, 0.03)
    fl.build("floor_v2", "floor_v2", coll=coll)
    pth = MB()
    pth.box(0.45, 13.3, 1.55, 1.6, 0.03, 0.032)
    pth.box(0.45, 13.3, 6.95, 7.0, 0.03, 0.032)
    pth.build("route_lines", "path_green", coll=coll)
    return roof_coll


# ---------------------------------------------------------------- signage
def build_signage():
    coll = collection("signage")
    sg = MB()
    x0, x1 = DOOR[0] - 0.65, PIER - 0.3                # between the column at 12.0 and the last pier
    fh = (x1 - x0) / 6.0
    sg.box(x0, x1, -0.36, -0.22, 3.1 - fh - 0.04, 3.1)
    sg.build("fascia", "sign_green", coll=coll, bevel=0.01)
    plane_uv("fascia_face", ((x0 + x1) / 2, -0.362, 3.08 - fh / 2), (x1 - x0, fh), (math.radians(90), 0, 0), "fascia", coll)
    # totem in the corridor beside the door
    tb = MB()
    tx = DOOR[0] - 0.6
    tb.box(tx - 0.3, tx + 0.3, -0.75, -0.65, HC - 0.65, HC - 0.6)
    tb.build("totem_base", "frame", coll=coll)
    plane_uv("totem", (tx, -0.76, HC - 0.6 + 0.9), (0.6, 1.8), (math.radians(90), 0, 0), "totem", coll)
    bk = MB()
    bk.box(tx - 0.3, tx + 0.3, -0.74, -0.68, HC - 0.6, HC - 0.6 + 1.8)
    bk.build("totem_back", "sign_green", coll=coll)
    # big letters on the red wall above the roof (face -x, toward the platform)
    text("智慧农业科普展厅", S.CJK_FONT, 0.85, (L - 0.06, 4.7, 9.0), (math.radians(90), 0, math.radians(-90)),
         "letters_white", 0.05, coll=coll, spacing=1.06)


# ---------------------------------------------------------------- interior
def plant_meshes():
    P = {}
    P["lettuce"] = [rosette_mesh(f"v2let{i}", i, n=18, L=(0.06, 0.15), W=0.62, tilt=(80, 12), droop=0.9, cup=0.3,
                                 ruffle=0.012, rfreq=7) for i in range(3)]
    P["red"] = [rosette_mesh(f"v2red{i}", 20 + i, n=18, L=(0.06, 0.15), W=0.5, tilt=(80, 15), droop=0.8, cup=0.25,
                             ruffle=0.016, rfreq=9) for i in range(2)]
    P["bok"] = [rosette_mesh(f"v2bok{i}", 40 + i, n=11, L=(0.12, 0.2), W=0.42, tilt=(85, 55), droop=0.5, cup=0.4,
                             spoon=True) for i in range(2)]
    P["straw"] = [rosette_mesh(f"v2st{i}", 60 + i, n=11, L=(0.08, 0.13), W=0.85, tilt=(65, 25), droop=0.9, cup=0.2,
                               berries=7, flowers=3) for i in range(2)]
    P["small"] = [rosette_mesh(f"v2sm{i}", 90 + i, n=12, L=(0.05, 0.11), W=0.6, tilt=(80, 20), droop=0.9, cup=0.3,
                               ruffle=0.01) for i in range(3)]
    P["sprout"] = [rosette_mesh(f"v2sp{i}", 99 + i, n=2 + i, L=(0.02 + 0.01 * i, 0.03 + 0.012 * i), W=0.8,
                                tilt=(55, 40), droop=0.2, cup=0.25) for i in range(4)]
    P["fern"] = [rosette_mesh(f"v2fern{i}", 120 + i, n=22, L=(0.15, 0.3), W=0.35, tilt=(60, 5), droop=1.6, cup=0.1,
                              ruffle=0.01, rfreq=12) for i in range(2)]
    for k in ("lettuce", "small", "sprout", "fern"):
        for me in P[k]:
            me.materials.append(M["leaf_lettuce" if k != "fern" else "leaf_basil"])
    for me in P["red"]:
        me.materials.append(M["leaf_red"])
    for me in P["bok"]:
        me.materials.append(M["leaf_bokchoy"])
    for me in P["straw"]:
        for m in ("leaf_dark", "berry", "flower_white"):
            me.materials.append(M[m])
    return P


def build_interior(P):
    coll = collection("interior")
    rnd = random.Random(3)

    # 1. seed-germination window along the kerb (glass front, same height as the kerb)
    gw, gwf, soil = MB(), MB(), MB()
    xg = 0.42
    gw.poly([(xg, 0.4, 0.05), (xg, W - 0.4, 0.05), (xg, W - 0.4, K - 0.03), (xg, 0.4, K - 0.03)])
    gwf.box(0.0, xg + 0.03, 0.35, W - 0.35, K - 0.03, K + 0.02)          # top lip
    gwf.box(0.0, xg + 0.03, 0.35, W - 0.35, 0.0, 0.05)
    for k in range(7):
        y = 0.4 + k * (W - 0.8) / 6
        gwf.box(0.0, xg + 0.02, y - 0.025, y + 0.025, 0.0, K)
    gwf.build("germ_frame", "frame", coll=coll, bevel=0.003)
    gw.build("germ_glass", "glass", coll=coll)
    plane_uv("germ_face", (xg - 0.03, W / 2, (0.05 + K - 0.03) / 2), (W - 0.8, K - 0.08),
             (math.radians(90), 0, math.radians(90)), "germ_face", coll)
    led = MB()
    led.box(xg - 0.02, xg + 0.03, 0.4, W - 0.4, K - 0.06, K - 0.04)
    led.build("germ_led", "led_warm", coll=coll)
    stages = [None, P["sprout"][0], P["sprout"][1], P["sprout"][2], P["sprout"][3], P["small"][0]]
    for k in range(6):
        y0 = 0.4 + k * (W - 0.8) / 6
        me = stages[k]
        if me is None:
            continue
        for j in range(5):
            instance(me, "gs", (rnd.uniform(0.08, 0.32), y0 + 0.15 + j * 0.24, K + 0.02), (0, 0, rnd.uniform(0, 6)),
                     rnd.uniform(1.0, 1.4) * (1.6 if k == 5 else 1.0), coll)
    soil.box(0.0, xg - 0.04, 0.4, W - 0.4, K - 0.06, K + 0.015)
    soil.build("germ_soil_top", "soil", coll=coll)
    for k, lab in enumerate(["第1天 种子", "第3天 萌发", "第5天 生根", "第7天 出苗", "第15天 长叶", "第30天 收获"]):
        y = 0.4 + (k + 0.5) * (W - 0.8) / 6
        text(lab, S.CJK_FONT, 0.06, (xg + 0.035, y, K - 0.0), (math.radians(90), 0, math.radians(90)), "letters_white",
             0.003, coll=coll)

    # 2. vertical hydroponic racks along the corridor glass (visible from the corridor)
    rk, ch, ledb = MB(), MB(), MB()
    for (a, b) in [(1.2, 3.6), (3.9, 6.3), (6.6, 9.0), (9.3, 11.7)]:
        for x in (a, b - 0.04):
            for y in (0.35, 0.91):
                rk.box(x, x + 0.04, y, y + 0.04, 0.03, 1.95)
        for t in range(4):
            z = 0.45 + t * 0.42
            ch.box(a, b, 0.4, 0.9, z, z + 0.07)
            ledb.box(a + 0.1, b - 0.1, 0.6, 0.7, z + 0.37, z + 0.38)
            x = a + 0.15
            while x < b - 0.1:
                for yy in (0.52, 0.78):
                    instance(rnd.choice(P["lettuce"] + P["red"] + P["small"]), "rp", (x, yy, z + 0.07),
                             (0, 0, rnd.uniform(0, 6)), rnd.uniform(0.55, 0.75), coll)
                x += 0.26
    rk.build("rack_frames", "steel_brushed", coll=coll)
    ch.build("rack_channels", "pvc_white", coll=coll, bevel=0.008)
    ledb.build("rack_leds", "led_purple", coll=coll)

    # 3. class planting beds along the street side (8 grades / classes)
    beds, sl = MB(), MB()
    crops = ["lettuce", "straw", "bok", "red", "lettuce", "bok", "straw", "red"]
    for k in range(8):
        a = 1.0 + k * 1.65
        b = a + 1.4
        y0, y1 = 7.35, 8.25
        beds.box(a, b, y0, y1, 0.03, 0.72)
        sl.box(a + 0.05, b - 0.05, y0 + 0.05, y1 - 0.05, 0.72, 0.73)
        for i in range(4):
            for j in range(3):
                instance(rnd.choice(P[crops[k]]), "bp", (a + 0.2 + i * 0.33, y0 + 0.17 + j * 0.28, 0.73),
                         (0, 0, rnd.uniform(0, 6)), rnd.uniform(1.0, 1.25), coll)
        text(f"{['一','二','三','四','五','六','一','二'][k]}年级{(k // 6) + 1 if k >= 6 else 1}班", S.CJK_FONT, 0.07,
             ((a + b) / 2, y0 - 0.005, 0.5), (math.radians(90), 0, 0), "letters_white", 0.003, coll=coll)
    beds.build("class_beds", "wpc_dark_x", coll=coll, bevel=0.006)
    sl.build("bed_soil", "soil", coll=coll)

    # 4. aeroponic towers + aquaponics in the middle
    tw, tb, pk = MB(), MB(), MB()
    for (x, y) in [(2.2, 3.1), (3.2, 3.1), (2.2, 5.4), (3.2, 5.4), (12.75, 3.0), (12.75, 5.5)]:
        tb.tube((x, y, 0.03), (x, y, 0.4), 0.28, 24)
        tw.tube((x, y, 0.4), (x, y, 2.0), 0.11, 20)
        for ring in range(7):
            z = 0.62 + ring * 0.2
            for k in range(5):
                az = k * 2 * math.pi / 5 + (ring % 2) * math.pi / 5
                ox, oy = math.cos(az), math.sin(az)
                p1 = (x + ox * 0.17, y + oy * 0.17, z + 0.07)
                pk.tube((x + ox * 0.08, y + oy * 0.08, z), p1, 0.035, 8)
                instance(rnd.choice(P["small"] + P["red"]), "tp", p1, (0, math.radians(50), az),
                         rnd.uniform(0.7, 0.95), coll)
    tw.build("towers", "pvc_white", smooth=True, coll=coll)
    tb.build("tower_tanks", "frame_dark", smooth=True, coll=coll)
    pk.build("tower_pockets", "pvc_white", smooth=True, coll=coll)
    aq, aqw, aqg = MB(), MB(), MB()
    ax0, ax1, ay0, ay1 = 5.2, 7.0, 3.85, 4.65
    aq.box(ax0, ax1, ay0, ay1, 0.03, 0.08)
    for (p, q, r, s) in ((ax0, ax1, ay0, ay0 + 0.03), (ax0, ax1, ay1 - 0.03, ay1)):
        aq.box(p, q, r, s, 0.08, 0.12)
        aq.box(p, q, r, s, 0.68, 0.72)
    aqg.poly([(ax0, ay0, 0.12), (ax1, ay0, 0.12), (ax1, ay0, 0.68), (ax0, ay0, 0.68)])
    aqg.poly([(ax0, ay1, 0.12), (ax1, ay1, 0.12), (ax1, ay1, 0.68), (ax0, ay1, 0.68)])
    aqg.poly([(ax0, ay0, 0.12), (ax0, ay1, 0.12), (ax0, ay1, 0.68), (ax0, ay0, 0.68)])
    aqg.poly([(ax1, ay0, 0.12), (ax1, ay1, 0.12), (ax1, ay1, 0.68), (ax1, ay0, 0.68)])
    aqw.box(ax0 + 0.03, ax1 - 0.03, ay0 + 0.03, ay1 - 0.03, 0.12, 0.6)
    for (x, y) in ((ax0 + 0.03, ay0 + 0.03), (ax1 - 0.06, ay0 + 0.03), (ax0 + 0.03, ay1 - 0.06), (ax1 - 0.06, ay1 - 0.06)):
        aq.box(x, x + 0.03, y, y + 0.03, 0.72, 1.2)
    aq.box(ax0, ax1, ay0, ay1, 1.2, 1.32)
    aq.build("aqua_frame", "frame", coll=coll, bevel=0.003)
    aqg.build("aqua_glass", "glass", coll=coll)
    aqw.build("aqua_water", "fish_water", coll=coll)
    fs = MB()
    for k in range(9):
        fx, fy, fz = rnd.uniform(ax0 + 0.2, ax1 - 0.2), rnd.uniform(ay0 + 0.15, ay1 - 0.15), rnd.uniform(0.2, 0.5)
        fs.box(fx - 0.06, fx + 0.06, fy - 0.015, fy + 0.015, fz - 0.025, fz + 0.025)
    fs.build("fish", "fish", coll=coll)
    for i in range(6):
        for j in range(2):
            instance(rnd.choice(P["lettuce"] + P["bok"]), "ap", (ax0 + 0.18 + i * 0.29, ay0 + 0.22 + j * 0.36, 1.32),
                     (0, 0, rnd.uniform(0, 6)), 1.0, coll)

    # 5. study workbenches with stools
    wb, st = MB(), MB()
    for (y0, y1) in ((2.6, 3.5), (5.0, 5.9)):
        wb.box(9.6, 11.6, y0, y1, 0.74, 0.78)
        for x in (9.7, 11.46):
            wb.box(x, x + 0.04, y0 + 0.05, y1 - 0.05, 0.03, 0.74)
        for x in (9.95, 10.6, 11.25):
            for y in (y0 - 0.32, y1 + 0.32):
                st.tube((x, y, 0.03), (x, y, 0.45), 0.17, 18)
    wb.build("workbench", "wpc_x", coll=coll, bevel=0.004)
    st.build("stools_wb", "seat_c", smooth=True, coll=coll)

    # 6. lecture zone facing the red-wall screen (20 seats)
    seat_mats = ["seat_a", "seat_b", "seat_c"]
    seats = {m: MB() for m in seat_mats}
    for i, x in enumerate((14.0, 14.75, 15.5, 16.25)):
        for j, y in enumerate((2.75, 3.55, 4.35, 5.15, 5.95)):
            seats[seat_mats[(i + j) % 3]].tube((x, y, 0.03), (x, y, 0.42), 0.18, 20)
    for m, mb in seats.items():
        mb.build(f"seats_{m}", m, smooth=True, coll=coll)

    # 7. red-wall feature wall (inside): slats, timeline, screen, photo wall, living wall
    xw = L - 0.24
    fw = MB()
    y = 0.3
    while y < 8.2:
        fw.box(xw - 0.05, xw, y, y + 0.06, 0.82, 2.62)
        y += 0.1
    fw.build("wall_slats", "wood_slat", coll=coll)
    plane_uv("timeline", (xw - 0.07, 4.25, 1.2), (3.2, 0.69), (math.radians(90), 0, math.radians(-90)), "timeline", coll)
    sc = MB()
    sc.box(xw - 0.1, xw - 0.06, 3.38, 5.12, 1.6, 2.6)
    sc.build("screen_bezel", "black", coll=coll)
    plane_uv("screen_v2", (xw - 0.105, 4.25, 2.1), (1.66, 0.93), (math.radians(90), 0, math.radians(-90)), "screen", coll)
    for i, (yc, zc) in enumerate([(1.3, 2.05), (2.3, 2.05), (1.3, 1.35), (2.3, 1.35), (6.2, 2.05), (7.2, 2.05)]):
        pf = MB()
        pf.box(xw - 0.09, xw - 0.06, yc - 0.43, yc + 0.43, zc - 0.31, zc + 0.31)
        pf.build("photo_frame", "black", coll=coll)
        plane_uv(f"photo{i}", (xw - 0.095, yc, zc), (0.8, 0.57), (math.radians(90), 0, math.radians(-90)), f"photo{i}", coll)
    # living-wall panels at both ends and one in the lower right
    lw = MB()
    for (ya, yb, za, zb) in ((0.3, 0.75, 0.82, 2.6), (7.75, 8.2, 0.82, 2.55), (5.75, 7.65, 0.85, 1.6)):
        lw.box(xw - 0.1, xw - 0.05, ya, yb, za, zb)
        yy = ya + 0.08
        while yy < yb - 0.05:
            zz = za + 0.1
            while zz < zb - 0.05:
                instance(rnd.choice(P["fern"] + P["small"]), "lw", (xw - 0.11, yy, zz),
                         (0, math.radians(-90 + rnd.uniform(-15, 15)), rnd.uniform(-0.3, 0.3)), rnd.uniform(0.5, 0.8), coll)
                zz += 0.22
            yy += 0.2
    lw.build("living_wall_back", "soil", coll=coll)

    # 8. seedling rack near the entrance + fertigation cabinet in the red-wall corner
    sd, sdl, trays = MB(), MB(), MB()
    for x in (12.0, 13.16):
        for y in (0.35, 0.8):
            sd.box(x, x + 0.04, y, y + 0.04, 0.03, 1.85)
    for z in (0.45, 0.95, 1.45):
        sd.box(12.0, 13.2, 0.35, 0.84, z, z + 0.02)
        trays.box(12.05, 13.15, 0.4, 0.8, z + 0.02, z + 0.06)
        sdl.box(12.1, 13.1, 0.55, 0.62, z + 0.43, z + 0.44)
        for a in range(9):
            for b in range(3):
                instance(P["sprout"][rnd.randrange(4)], "sd", (12.12 + a * 0.12, 0.47 + b * 0.13, z + 0.06),
                         (0, 0, rnd.uniform(0, 6)), 1.2, coll)
    sd.build("seed_rack", "steel_brushed", coll=coll)
    sdl.build("seed_leds", "led_purple", coll=coll)
    trays.build("seed_trays", "black", coll=coll)
    fc = MB()
    fc.box(16.9, 17.5, 7.45, 8.25, 0.03, 1.6)
    fc.build("fertigation", "white_plastic", coll=coll, bevel=0.01)
    tk = MB()
    tk.tube((16.4, 7.85, 0.03), (16.4, 7.85, 0.95), 0.25, 24)
    tk.build("tank", "tank_blue", smooth=True, coll=coll)
    pn = MB()
    pn.box(16.895, 16.9, 7.65, 8.05, 1.05, 1.35)
    pn.build("fert_panel", "black_gloss", coll=coll)

    # 9. overhead grow lights + misting line
    ov, le, mi = MB(), MB(), MB()
    for y in (0.65, 7.8):
        for k in range(8):
            a = 1.1 + k * 1.55
            z = roof_z(y) - 0.45
            ov.box(a, a + 1.2, y - 0.04, y + 0.04, z, z + 0.05)
            le.box(a + 0.02, a + 1.18, y - 0.03, y + 0.03, z - 0.005, z)
    for y in (2.5, 6.0):
        z = roof_z(y) - 0.2
        mi.tube((0.5, y, z), (L - 0.4, y, z), 0.012, 8)
    ov.build("grow_bars", "black", coll=coll)
    le.build("grow_emit", "led_grow", coll=coll)
    mi.build("misting", "steel", smooth=True, coll=coll)
    for (x, y) in ((3.0, 4.25), (9.0, 4.25), (15.0, 4.25)):
        ld = bpy.data.lights.new("int", "AREA")
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = 1.5, 0.3
        ld.energy = 400 if S.NIGHT else 0
        ld.color = (1.0, 0.86, 0.72)
        lo = bpy.data.objects.new("int_light", ld)
        lo.location = (x, y, roof_z(y) - 0.3)
        link(lo, coll)


def build_louver_display(P):
    """Potted plants on the louver sill/fins and LED strips under the fins (client's plant-observation window)."""
    coll = collection("louver_display")
    rnd = random.Random(21)
    cf = HC - 0.65
    pots, led = MB(), MB()
    levels = [cf + 0.9, cf + 1.2 + 0.42 + 0.09, cf + 1.2 + 0.84 + 0.09]
    runs = [("side", PIER + 0.45, L - 0.25), ("end", -2.7, -0.45)]
    for kind, a, b in runs:
        n = int((b - a) / 0.3)
        for lv in levels:
            for k in range(n):
                t = a + (k + 0.5) * (b - a) / n
                x, y = (t, -0.12) if kind == "side" else (L + 0.12, t)
                r = rnd.uniform(0.055, 0.07)
                pots.tube((x, y, lv), (x, y, lv + 0.11), r * 0.8, 14, r1=r)
                instance(rnd.choice(P["small"] + P["fern"] + P["red"]), "lp", (x, y, lv + 0.1), (0, 0, rnd.uniform(0, 6)),
                         rnd.uniform(0.7, 0.95), coll)
        z = cf + 1.2
        while z < BEAM - 0.1:
            if kind == "side":
                led.box(a - 0.15, b + 0.15, -0.2, -0.17, z - 0.012, z)
            else:
                led.box(L + 0.03, L + 0.06, a - 0.15, b + 0.15, z - 0.012, z)
            z += 0.42
    pots.build("louver_pots", "white_plastic", smooth=True, coll=coll)
    led.build("louver_led", "led_warm", coll=coll)


def build_station():
    """Campus weather station on the raised platform (client's picture): white pole on a ballast plinth,
    double-sided red LED screen, control box, sensors on a top arm. Built at the origin, then placed."""
    coll = collection("station")
    sx, sy = 0.0, 0.0
    z = K
    white, steel, dark, base, blue = MB(), MB(), MB(), MB(), MB()
    base.box(sx - 0.4, sx + 0.4, sy - 0.4, sy + 0.4, z, z + 0.3)              # ballast plinth, no drilling
    steel.box(sx - 0.2, sx + 0.2, sy - 0.2, sy + 0.2, z + 0.3, z + 0.32)       # flange
    white.tube((sx, sy, z + 0.32), (sx, sy, z + 3.62), 0.057, 24)             # pole, dia 114
    white.box(sx - 0.22, sx + 0.22, sy - 0.29, sy - 0.07, z + 1.05, z + 1.65)  # control box
    blue.box(sx - 0.18, sx + 0.18, sy - 0.292, sy - 0.288, z + 1.5, z + 1.56)
    dark.box(sx - 0.82, sx + 0.82, sy - 0.08, sy + 0.08, z + 1.95, z + 2.79)   # LED cabinet 1.6 x 0.8
    plane_uv("station_led_s", (sx, sy - 0.081, z + 2.37), (1.58, 0.79), (math.radians(90), 0, 0), "station_led", coll)
    plane_uv("station_led_n", (sx, sy + 0.081, z + 2.37), (1.58, 0.79), (math.radians(90), 0, math.radians(180)),
             "station_led", coll)
    # top arm: wind speed (cups) at one end, wind vane at the other, radiation shield, rain gauge, lightning rod
    za = z + 3.3
    white.box(sx - 0.65, sx + 0.65, sy - 0.03, sy + 0.03, za, za + 0.05)
    cx = sx - 0.6
    steel.tube((cx, sy, za + 0.05), (cx, sy, za + 0.32), 0.012, 10)
    for k in range(3):
        a = k * 2 * math.pi / 3
        ex, ey = cx + 0.13 * math.cos(a), sy + 0.13 * math.sin(a)
        steel.tube((cx, sy, za + 0.3), (ex, ey, za + 0.3), 0.005, 6)
        tx, ty = -math.sin(a), math.cos(a)
        white.tube((ex - tx * 0.02, ey - ty * 0.02, za + 0.3), (ex + tx * 0.02, ey + ty * 0.02, za + 0.3), 0.012, 12,
                   r1=0.035)
    vx = sx + 0.6
    steel.tube((vx, sy, za + 0.05), (vx, sy, za + 0.32), 0.012, 10)
    steel.tube((vx - 0.18, sy, za + 0.3), (vx + 0.14, sy, za + 0.3), 0.006, 6)
    white.box(vx - 0.2, vx - 0.08, sy - 0.003, sy + 0.003, za + 0.25, za + 0.37)
    for k in range(7):                                                         # louvred radiation shield
        zz = za - 0.06 - k * 0.032
        white.tube((sx - 0.3, sy, zz - 0.012), (sx - 0.3, sy, zz), 0.075, 20)
    white.tube((sx + 0.3, sy, za + 0.05), (sx + 0.3, sy, za + 0.28), 0.07, 20, r1=0.08)   # rain gauge
    steel.tube((sx, sy, z + 3.62), (sx, sy, z + 4.1), 0.008, 8)                # lightning rod
    base.build("station_base", "cap_stone", coll=coll, bevel=0.01)
    white.build("station_white", "pvc_white", smooth=True, coll=coll)
    steel.build("station_steel", "steel_brushed", smooth=True, coll=coll)
    dark.build("station_cabinet", "black", coll=coll, bevel=0.008)
    blue.build("station_label", "tank_blue", coll=coll)
    place = Matrix.Translation((STATION[0], STATION[1], 0)) @ Matrix.Rotation(math.radians(STATION_ROT), 4, "Z")
    bpy.context.view_layer.update()
    for ob in coll.objects:
        ob.matrix_world = place @ ob.matrix_world
    return coll


# ---------------------------------------------------------------- world / cameras
def world_overcast(strength=1.0, sun=0.6):
    sc = bpy.context.scene
    w = bpy.data.worlds.new("overcast")
    w.use_nodes = True
    sc.world = w
    nb = S.NB(w)
    bg = nb.nodes["Background"]
    tc = nb.n("ShaderNodeTexCoord")
    sp = nb.n("ShaderNodeSeparateXYZ")
    nb.l(tc.outputs["Generated"], sp.inputs[0])
    grad = nb.ramp(sp.outputs[2], [(0.0, (0.55, 0.56, 0.56)), (0.1, (0.86, 0.88, 0.9)), (1.0, (0.95, 0.96, 0.98))])
    nb.l(grad, bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    ld = bpy.data.lights.new("sun", "SUN")
    ld.energy = sun
    ld.angle = math.radians(25)
    lo = bpy.data.objects.new("sun", ld)
    lo.rotation_euler = (math.radians(35), 0, math.radians(200))
    link(lo)


def calibrated_camera(name):
    c = CAL["cams"][name]
    import numpy as np  # bpy ships numpy
    rv = np.array(c["rv"], float)
    theta = np.linalg.norm(rv)
    k = rv / theta
    Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    R = np.eye(3) + math.sin(theta) * Kx + (1 - math.cos(theta)) * Kx @ Kx      # world -> cv camera
    pos = -R.T @ np.array(c["tv"])
    R_bl = np.diag([1, -1, -1]) @ R                                               # world -> blender camera
    cam = bpy.data.cameras.new(name)
    w, h = c["size"]
    cam.sensor_fit = "HORIZONTAL"
    cam.sensor_width = 36
    cam.lens = c["f"] * 36 / w
    cam.clip_start = 0.05
    cam.clip_end = 2000
    ob = bpy.data.objects.new(name, cam)
    ob.matrix_world = Matrix.Translation(Vector(pos)) @ Matrix(R_bl.T.tolist()).to_4x4()
    link(ob)
    return ob, (w, h)


VIEWS = {
    # name: (location, target, lens, shift_y)
    "interior_in": ((DOOR[0] + 0.75, 0.9, 1.55), (4.0, 6.2, 1.25), 16.0, 0.04),
    "interior_wall": ((8.6, 6.6, 1.6), (17.8, 3.0, 1.5), 17.0, 0.06),
    "interior_kerb": ((5.2, 1.6, 1.5), (0.0, 5.8, 0.8), 18.0, 0.02),
    "germ": ((1.75, 1.35, 1.2), (0.3, 3.9, 0.55), 22.0, 0.0),
    "aerial": ((-7.0, 21.0, 17.5), (8.6, 3.2, 0.0), 30.0, 0.0),
    "corridor": ((DOOR[0] - 1.0, -2.7, 1.2), (PIER + 0.4, 0.3, 1.2), 15.0, 0.12),
    "station_corridor": ((-1.5, -1.6, 1.25), (-1.15, 8.39, 1.25), 20.0, 0.1),
    "station_terrace": ((-10.3, 7.3, 1.6), (-1.5, 4.0, 1.6), 24.0, 0.13),
}


def add_view(name):
    if name == "plan":
        cam = bpy.data.cameras.new(name)
        cam.type = "ORTHO"
        cam.ortho_scale = 20.5
        ob = bpy.data.objects.new(name, cam)
        ob.location = (L / 2 - 0.6, W / 2 - 0.3, 30)
        link(ob)
        return ob
    loc, tgt, lens, sy = VIEWS[name]
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.sensor_width = 36
    cam.shift_y = sy
    cam.clip_start = 0.05
    cam.clip_end = 3000
    ob = bpy.data.objects.new(name, cam)
    ob.location = loc
    d = Vector(tgt) - Vector(loc)
    if name not in ("aerial", "germ"):
        d.z = 0
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    link(ob)
    return ob


def main():
    global MODE, HC
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="3d", choices=["3d", "montage"])
    ap.add_argument("--shots", default="interior_in")
    ap.add_argument("--res", default="960x640")
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--scale", type=float, default=1.0, help="montage resolution scale")
    ap.add_argument("--time", default="day", choices=["day", "dusk"])
    ap.add_argument("--exposure", type=float, default=None)
    ap.add_argument("--out", default=os.path.join(HERE, "renders"))
    ap.add_argument("--suffix", default="")
    ap.add_argument("--hc", type=float, default=None, help="corridor parapet height override (per photo)")
    args = ap.parse_args(argv)
    MODE = args.mode
    if args.hc is not None:
        HC = args.hc
    S.NIGHT = args.time == "dusk"
    t0 = time.time()
    random.seed(2)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    S.make_materials()
    make_materials_v2()
    build_existing()
    roof_coll = build_shell()
    build_signage()
    build_station()
    P = plant_meshes()
    build_interior(P)
    if MODE == "3d":            # photo-matched alignment at the far corridor end is too loose for small props
        build_louver_display(P)
    sc = bpy.context.scene
    S.setup_render((960, 640), args.samples)
    if MODE == "montage":
        world_overcast(1.0, 0.8)
        sc.render.film_transparent = True
        sc.view_settings.view_transform = "Standard"
        sc.view_settings.look = "None"
        sc.view_settings.exposure = -0.3 if args.exposure is None else args.exposure
    else:
        if S.NIGHT:
            S.build_world(-3.0, 35.0, 1.0, 0.0, (1.0, 0.55, 0.3))
            sc.view_settings.exposure = 1.6 if args.exposure is None else args.exposure
        else:
            S.build_world(40.0, 230.0, 0.32, 4.2, (1.0, 0.95, 0.88))
            sc.view_settings.exposure = 0.0 if args.exposure is None else args.exposure
    print(f"built in {time.time() - t0:.1f}s, objects={len(bpy.data.objects)}")
    os.makedirs(args.out, exist_ok=True)
    for shot in args.shots.split(","):
        if MODE == "montage":
            cam, (w, h) = calibrated_camera(shot)
            sc.render.resolution_x, sc.render.resolution_y = int(w * args.scale), int(h * args.scale)
        else:
            cam = add_view(shot)
            w, h = (int(v) for v in args.res.split("x"))
            sc.render.resolution_x, sc.render.resolution_y = w, h
            roof_coll.hide_render = shot == "plan"
            if "context" in bpy.data.collections:
                bpy.data.collections["context"].hide_render = shot == "plan"
        sc.camera = cam
        sc.render.filepath = os.path.join(args.out, f"{'m_' if MODE == 'montage' else ''}{shot}{args.suffix}.png")
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"rendered {shot} in {time.time() - t1:.1f}s -> {sc.render.filepath}")


if __name__ == "__main__":
    main()
