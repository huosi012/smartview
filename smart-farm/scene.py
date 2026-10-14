"""Rooftop smart-farm greenhouse — procedural Blender scene + renders.

Everything (site, greenhouse, planting, lighting, cameras) is generated from code so
dimensions can be changed and the renders re-run.

    python scene.py --time day  --shots hero,terrace,aerial,interior --res 1920x1280 --samples 160
    python scene.py --time dusk --shots dusk --res 1920x1280 --samples 200
    python scene.py --time day  --shots plan --res 1600x2000 --samples 96

Requires the `bpy` module (pip install bpy) and Pillow. Coordinates are metres, Z up.
The terrace floor is z=0; +y points away from the corridor (north), +x to the east.
"""
import argparse
import math
import os
import random
import sys
import time

import bpy
from mathutils import Euler, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "tex")
CJK_FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
LATIN_FONT = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"

# ---------------------------------------------------------------- dimensions
TX0, TX1, TY0, TY1 = -5.0, 9.0, -5.0, 9.0      # lower terrace (approx. 14 x 14 m)
CORR_Z = 0.55                                   # corridor floor is ~3 steps above terrace
FLOOR_H = 3.3
N_FLOORS = 3                                    # floors of teaching block above terrace level
BX0, BX1 = -14.0, 12.5                          # teaching block extent along x
OPEN_X0, OPEN_X1 = 1.1, 2.9                     # new opening cut into the corridor railing

GX0, GY0 = -0.8, -2.0                           # greenhouse SW corner
GW, GL = 5.6, 9.0                               # 5.6 x 9.0 = 50.4 m2
EH = 2.8                                        # eave height
PITCH = math.radians(25)
RISE = GW / 2 * math.tan(PITCH)
RH = EH + RISE                                  # ridge height ~4.1 m
PLINTH = 0.35
DECK = 0.10                                     # top of WPC decking
DOOR_V0, DOOR_V1 = 1.8, 3.8                     # door opening (local v across the gable)
DOOR_H = 2.45
BAY = GL / 8
GXC = GX0 + GW / 2

ARGS = None
NIGHT = False


# ---------------------------------------------------------------- utilities
def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def sock(node, ident, out=False):
    for s in (node.outputs if out else node.inputs):
        if s.identifier == ident or s.name == ident:
            return s
    raise KeyError(f"{node.bl_idname} has no socket {ident}")


class NB:
    """Tiny node-graph helper."""

    def __init__(self, mat):
        self.nt = mat.node_tree
        self.nodes = self.nt.nodes
        self.links = self.nt.links

    def n(self, kind, **props):
        node = self.nodes.new(kind)
        for k, v in props.items():
            if k.startswith("in_"):
                node.inputs[k[3:].replace("_", " ")].default_value = v
            else:
                setattr(node, k, v)
        return node

    def l(self, a, b):
        self.links.new(a, b)

    def math(self, op, a, b=None, clamp=False):
        m = self.n("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                self.l(v, m.inputs[i])
        return m.outputs[0]

    def mix_rgb(self, fac, a, b, blend="MIX"):
        m = self.n("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        for ident, v in (("Factor_Float", fac), ("A_Color", a), ("B_Color", b)):
            s = sock(m, ident)
            if isinstance(v, (int, float)):
                s.default_value = v
            elif isinstance(v, tuple):
                s.default_value = (*v, 1.0) if len(v) == 3 else v
            else:
                self.l(v, s)
        return sock(m, "Result_Color", out=True)

    def ramp(self, fac, stops):
        r = self.n("ShaderNodeValToRGB")
        els = r.color_ramp.elements
        els[0].position, els[0].color = stops[0][0], (*stops[0][1], 1)
        els[1].position, els[1].color = stops[-1][0], (*stops[-1][1], 1)
        for p, c in stops[1:-1]:
            e = els.new(p)
            e.color = (*c, 1)
        self.l(fac, r.inputs["Fac"])
        return r.outputs["Color"]

    def world_pos(self):
        return self.n("ShaderNodeNewGeometry").outputs["Position"]

    def noise(self, vec, scale, detail=4.0, rough=0.5, out="Fac"):
        t = self.n("ShaderNodeTexNoise", in_Scale=scale, in_Detail=detail, in_Roughness=rough)
        if vec is not None:
            self.l(vec, t.inputs["Vector"])
        return t.outputs[out]

    def mapping(self, vec, scale=(1, 1, 1), loc=(0, 0, 0), rot=(0, 0, 0)):
        m = self.n("ShaderNodeMapping")
        m.inputs["Scale"].default_value = scale
        m.inputs["Location"].default_value = loc
        m.inputs["Rotation"].default_value = rot
        self.l(vec, m.inputs["Vector"])
        return m.outputs["Vector"]

    def bump(self, height, strength=0.3, distance=0.02, bsdf=None):
        b = self.n("ShaderNodeBump", in_Strength=strength, in_Distance=distance)
        self.l(height, b.inputs["Height"])
        if bsdf is not None:
            self.l(b.outputs["Normal"], bsdf.inputs["Normal"])
        return b

    def attr(self, name, out="Fac"):
        return self.n("ShaderNodeAttribute", attribute_name=name).outputs[out]


def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, NB(m), m.node_tree.nodes["Principled BSDF"]


def set_bsdf(b, color=None, rough=None, metal=None, spec=None, coat=None, sheen=None):
    if color is not None:
        b.inputs["Base Color"].default_value = (*color, 1)
    if rough is not None:
        b.inputs["Roughness"].default_value = rough
    if metal is not None:
        b.inputs["Metallic"].default_value = metal
    if spec is not None:
        b.inputs["Specular IOR Level"].default_value = spec
    if coat is not None:
        b.inputs["Coat Weight"].default_value = coat
    if sheen is not None:
        b.inputs["Sheen Weight"].default_value = sheen


def output_of(nb):
    return nb.nodes["Material Output"]


# ---------------------------------------------------------------- materials
M = {}


def make_materials():
    def simple(name, color, rough=0.5, metal=0.0, spec=0.5, coat=0.0):
        m, nb, b = new_mat(name)
        set_bsdf(b, color, rough, metal, spec, coat)
        M[name] = m
        return m, nb, b

    # graphite powder-coated frame (RAL 7016 feel)
    m, nb, b = simple("frame", (0.032, 0.036, 0.040), 0.32, 0.55, 0.6, 0.25)
    simple("frame_dark", (0.018, 0.019, 0.021), 0.38, 0.4)
    # aluminium composite cladding for portal + plinth
    m, nb, b = simple("cladding", (0.028, 0.030, 0.033), 0.42, 0.35, 0.5)
    nb.bump(nb.noise(None, 900, 2), 0.04, 0.002, b)
    simple("steel", (0.78, 0.78, 0.77), 0.16, 1.0)
    simple("steel_brushed", (0.70, 0.70, 0.69), 0.28, 1.0)
    simple("champagne", (0.78, 0.60, 0.36), 0.22, 1.0)
    simple("black", (0.012, 0.012, 0.013), 0.35)
    simple("black_gloss", (0.004, 0.004, 0.005), 0.05, 0.0, 0.8)
    simple("pvc_white", (0.83, 0.85, 0.85), 0.35, 0.0, 0.5, 0.2)
    simple("white_plastic", (0.80, 0.81, 0.80), 0.45)
    simple("tank_blue", (0.04, 0.22, 0.55), 0.3, 0.0, 0.5, 0.3)
    simple("tank_white", (0.75, 0.78, 0.78), 0.3)
    simple("paint_white", (0.78, 0.78, 0.76), 0.75)
    simple("paint_red", (0.30, 0.032, 0.026), 0.7)
    simple("paint_cream", (0.72, 0.66, 0.55), 0.8)
    simple("cap_stone", (0.62, 0.62, 0.60), 0.6)
    simple("bark", (0.16, 0.12, 0.09), 0.9)
    simple("berry", (0.55, 0.02, 0.025), 0.25, 0.0, 0.7, 0.4)
    simple("flower_white", (0.85, 0.85, 0.80), 0.5)
    simple("flower_red", (0.75, 0.05, 0.08), 0.5)
    simple("flower_yellow", (0.85, 0.55, 0.03), 0.5)
    simple("flower_purple", (0.35, 0.10, 0.55), 0.5)
    simple("solar", (0.01, 0.02, 0.06), 0.12, 0.3, 0.8)

    # thin architectural glass / clear polycarbonate
    for name, tint, rough in (("glass", (0.93, 0.97, 0.96), 0.0), ("glass_roof", (0.90, 0.95, 0.94), 0.04),
                              ("glass_dark", (0.25, 0.30, 0.32), 0.0)):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nb = NB(m)
        nb.nodes.remove(nb.nodes["Principled BSDF"])
        tr = nb.n("ShaderNodeBsdfTransparent")
        tr.inputs["Color"].default_value = (*tint, 1)
        gl = nb.n("ShaderNodeBsdfGlossy", in_Roughness=rough)
        fr = nb.n("ShaderNodeFresnel", in_IOR=1.45)
        mix = nb.n("ShaderNodeMixShader")
        nb.l(nb.math("MULTIPLY", fr.outputs[0], 0.55 if name == "glass_roof" else 0.75), mix.inputs[0])
        nb.l(tr.outputs[0], mix.inputs[1])
        nb.l(gl.outputs[0], mix.inputs[2])
        nb.l(mix.outputs[0], output_of(nb).inputs["Surface"])
        M[name] = m

    # building window glass (opaque dark reflective; a few lit at dusk)
    m, nb, b = new_mat("window")
    set_bsdf(b, (0.012, 0.016, 0.02), 0.06, 0.0, 0.9)
    if NIGHT:
        r = nb.n("ShaderNodeObjectInfo").outputs["Random"]
        lit = nb.math("GREATER_THAN", r, 0.45)
        b.inputs["Emission Color"].default_value = (1.0, 0.78, 0.5, 1)
        nb.l(nb.math("MULTIPLY", lit, 2.5), b.inputs["Emission Strength"])
    M["window"] = m

    # WPC decking, grain along x or y
    for name, axis, c0, c1 in (("wpc_x", "x", (0.26, 0.14, 0.075), (0.40, 0.24, 0.13)),
                               ("wpc_y", "y", (0.26, 0.14, 0.075), (0.40, 0.24, 0.13)),
                               ("wpc_dark_x", "x", (0.10, 0.065, 0.045), (0.17, 0.11, 0.07)),
                               ("wpc_dark_y", "y", (0.10, 0.065, 0.045), (0.17, 0.11, 0.07)),
                               ("wpc_dark_z", "z", (0.10, 0.065, 0.045), (0.17, 0.11, 0.07))):
        m, nb, b = new_mat(name)
        sc = {"x": (1.5, 40, 40), "y": (40, 1.5, 40), "z": (1.5, 1.5, 40)}[axis]
        if axis == "z":
            sc = (40, 40, 1.5)
        v = nb.mapping(nb.world_pos(), sc)
        grain = nb.noise(v, 1.0, 8, 0.6)
        rnd = nb.attr("rand")
        col = nb.ramp(grain, [(0.3, c0), (0.7, c1)])
        hsv = nb.n("ShaderNodeHueSaturation")
        nb.l(col, hsv.inputs["Color"])
        nb.l(nb.math("ADD", nb.math("MULTIPLY", rnd, 0.35), 0.82), hsv.inputs["Value"])
        nb.l(hsv.outputs["Color"], b.inputs["Base Color"])
        set_bsdf(b, rough=0.55, spec=0.4)
        groove = nb.n("ShaderNodeTexWave", wave_type="BANDS",
                      bands_direction={"x": "Y", "y": "X", "z": "Z"}[axis] if axis != "z" else "X",
                      in_Scale=3.0)
        groove.inputs["Distortion"].default_value = 0.0
        nb.l(nb.world_pos(), groove.inputs["Vector"])
        nb.bump(groove.outputs["Fac"], 0.08, 0.004, b)
        M[name] = m

    # soil / growing substrate
    m, nb, b = new_mat("soil")
    n1 = nb.noise(None, 120, 6, 0.7)
    nb.l(nb.ramp(n1, [(0.3, (0.035, 0.022, 0.014)), (0.7, (0.09, 0.06, 0.04))]), b.inputs["Base Color"])
    set_bsdf(b, rough=0.95, spec=0.2)
    nb.bump(n1, 0.6, 0.01, b)
    M["soil"] = m

    # artificial turf
    m, nb, b = new_mat("turf")
    p = nb.world_pos()
    big = nb.noise(p, 1.2, 3)
    fine = nb.noise(p, 650, 2)
    c = nb.ramp(big, [(0.35, (0.05, 0.17, 0.010)), (0.65, (0.085, 0.24, 0.014))])
    c = nb.mix_rgb(nb.math("MULTIPLY", fine, 0.6), c, (0.15, 0.32, 0.03))
    nb.l(c, b.inputs["Base Color"])
    set_bsdf(b, rough=0.8, spec=0.2, sheen=0.15)
    nb.bump(fine, 0.9, 0.01, b)
    M["turf"] = m

    # white pebbles
    m, nb, b = new_mat("pebble")
    vor = nb.n("ShaderNodeTexVoronoi", in_Scale=55)
    nb.l(nb.world_pos(), vor.inputs["Vector"])
    edge = nb.math("POWER", vor.outputs["Distance"], 0.5)
    nb.l(nb.mix_rgb(0.75, (0.62, 0.62, 0.60), vor.outputs["Color"], "OVERLAY"), b.inputs["Base Color"])
    set_bsdf(b, rough=0.6)
    nb.bump(edge, 1.0, 0.02, b)
    M["pebble"] = m

    # concrete
    m, nb, b = new_mat("concrete")
    p = nb.world_pos()
    n1 = nb.noise(p, 3.0, 6, 0.65)
    n2 = nb.noise(p, 60, 4)
    c = nb.ramp(n1, [(0.35, (0.30, 0.30, 0.29)), (0.7, (0.45, 0.45, 0.43))])
    c = nb.mix_rgb(0.25, c, nb.ramp(n2, [(0.4, (0.25, 0.25, 0.24)), (0.6, (0.5, 0.5, 0.48))]))
    nb.l(c, b.inputs["Base Color"])
    set_bsdf(b, rough=0.92, spec=0.3)
    nb.bump(n2, 0.25, 0.01, b)
    M["concrete"] = m

    # glazed wall tiles (works for walls running along x or y)
    def tiles(name, col, mortar, tw, th, rough=0.25):
        m, nb, b = new_mat(name)
        sp = nb.n("ShaderNodeSeparateXYZ")
        nb.l(nb.world_pos(), sp.inputs[0])
        cb = nb.n("ShaderNodeCombineXYZ")
        nb.l(nb.math("ADD", sp.outputs[0], sp.outputs[1]), cb.inputs[0])
        nb.l(sp.outputs[2], cb.inputs[1])
        br = nb.n("ShaderNodeTexBrick", offset=0.0, in_Scale=1.0, in_Mortar_Size=0.004,
                  in_Brick_Width=tw, in_Row_Height=th)
        br.inputs["Color1"].default_value = (*col, 1)
        br.inputs["Color2"].default_value = (*[c * 0.96 for c in col], 1)
        br.inputs["Mortar"].default_value = (*mortar, 1)
        nb.l(cb.outputs[0], br.inputs["Vector"])
        nb.l(br.outputs["Color"], b.inputs["Base Color"])
        set_bsdf(b, rough=rough, spec=0.6)
        nb.bump(nb.math("SUBTRACT", 1.0, br.outputs["Fac"]), 0.3, 0.003, b)
        M[name] = m

    tiles("wall_tile", (0.80, 0.81, 0.80), (0.55, 0.55, 0.53), 0.45, 0.30)
    tiles("wall_tile_dirty", (0.66, 0.67, 0.66), (0.40, 0.40, 0.38), 0.45, 0.30, 0.5)

    m, nb, b = new_mat("floor_tile")
    br = nb.n("ShaderNodeTexBrick", offset=0.0, in_Scale=1.0, in_Mortar_Size=0.004,
              in_Brick_Width=0.6, in_Row_Height=0.6)
    br.inputs["Color1"].default_value = (0.60, 0.56, 0.50, 1)
    br.inputs["Color2"].default_value = (0.57, 0.53, 0.47, 1)
    br.inputs["Mortar"].default_value = (0.42, 0.40, 0.36, 1)
    nb.l(nb.world_pos(), br.inputs["Vector"])
    nb.l(br.outputs["Color"], b.inputs["Base Color"])
    set_bsdf(b, rough=0.3, spec=0.5)
    M["floor_tile"] = m

    # leaves: colour along the leaf (attribute 'lu', 0 = base, 1 = tip) + per-plant variation
    def leaf(name, stops, rough=0.45, trans=0.3, hue_var=0.03, bump=0.15):
        m, nb, b = new_mat(name)
        c = nb.ramp(nb.attr("lu"), stops)
        r = nb.n("ShaderNodeObjectInfo").outputs["Random"]
        hsv = nb.n("ShaderNodeHueSaturation")
        nb.l(c, hsv.inputs["Color"])
        nb.l(nb.math("ADD", nb.math("MULTIPLY", r, hue_var), 0.5 - hue_var / 2), hsv.inputs["Hue"])
        nb.l(nb.math("ADD", nb.math("MULTIPLY", r, 0.35), 0.8), hsv.inputs["Value"])
        nb.l(hsv.outputs["Color"], b.inputs["Base Color"])
        set_bsdf(b, rough=rough, spec=0.45)
        vein = nb.noise(None, 90, 3)
        nb.bump(vein, bump, 0.003, b)
        tr = nb.n("ShaderNodeBsdfTranslucent")
        nb.l(hsv.outputs["Color"], tr.inputs["Color"])
        mix = nb.n("ShaderNodeMixShader")
        mix.inputs[0].default_value = trans
        nb.l(b.outputs[0], mix.inputs[1])
        nb.l(tr.outputs[0], mix.inputs[2])
        nb.l(mix.outputs[0], output_of(nb).inputs["Surface"])
        M[name] = m

    leaf("leaf_lettuce", [(0.0, (0.55, 0.70, 0.30)), (0.45, (0.25, 0.52, 0.07)), (1.0, (0.16, 0.42, 0.04))])
    leaf("leaf_red", [(0.0, (0.40, 0.55, 0.15)), (0.5, (0.22, 0.12, 0.05)), (1.0, (0.28, 0.03, 0.06))])
    leaf("leaf_bokchoy", [(0.0, (0.80, 0.86, 0.72)), (0.38, (0.70, 0.80, 0.55)), (0.55, (0.10, 0.30, 0.04)),
                          (1.0, (0.07, 0.25, 0.03))])
    leaf("leaf_dark", [(0.0, (0.10, 0.25, 0.04)), (1.0, (0.05, 0.16, 0.025))], rough=0.35)
    leaf("leaf_basil", [(0.0, (0.12, 0.35, 0.05)), (1.0, (0.08, 0.30, 0.03))], rough=0.3)
    leaf("leaf_grass", [(0.0, (0.08, 0.20, 0.04)), (0.6, (0.25, 0.32, 0.08)), (1.0, (0.55, 0.45, 0.20))],
         trans=0.4, hue_var=0.02)
    leaf("leaf_palm", [(0.0, (0.10, 0.18, 0.04)), (1.0, (0.13, 0.24, 0.05))], trans=0.25, hue_var=0.02)
    leaf("leaf_seedling", [(0.0, (0.6, 0.75, 0.35)), (1.0, (0.30, 0.62, 0.10))], trans=0.4)

    m, nb, b = new_mat("boxwood")
    vor = nb.n("ShaderNodeTexVoronoi", in_Scale=140)
    nb.l(nb.world_pos(), vor.inputs["Vector"])
    big = nb.noise(None, 6, 3)
    c = nb.ramp(vor.outputs["Distance"], [(0.0, (0.10, 0.24, 0.03)), (0.5, (0.05, 0.15, 0.02)),
                                          (1.0, (0.02, 0.06, 0.01))])
    c = nb.mix_rgb(nb.math("MULTIPLY", big, 0.4), c, (0.18, 0.30, 0.05))
    nb.l(c, b.inputs["Base Color"])
    set_bsdf(b, rough=0.5, spec=0.4)
    nb.bump(vor.outputs["Distance"], 0.8, 0.01, b)
    M["boxwood"] = m

    m, nb, b = new_mat("tree_canopy")
    vor = nb.n("ShaderNodeTexVoronoi", in_Scale=7)
    nb.l(nb.world_pos(), vor.inputs["Vector"])
    fine = nb.noise(None, 25, 4)
    c = nb.ramp(vor.outputs["Distance"], [(0.0, (0.09, 0.18, 0.035)), (0.6, (0.04, 0.10, 0.02)),
                                          (1.0, (0.012, 0.035, 0.008))])
    r = nb.n("ShaderNodeObjectInfo").outputs["Random"]
    hsv = nb.n("ShaderNodeHueSaturation")
    nb.l(c, hsv.inputs["Color"])
    nb.l(nb.math("ADD", nb.math("MULTIPLY", r, 0.05), 0.475), hsv.inputs["Hue"])
    nb.l(nb.math("ADD", nb.math("MULTIPLY", r, 0.5), 0.75), hsv.inputs["Value"])
    nb.l(hsv.outputs["Color"], b.inputs["Base Color"])
    set_bsdf(b, rough=0.75, spec=0.3)
    nb.bump(nb.math("ADD", vor.outputs["Distance"], nb.math("MULTIPLY", fine, 0.5)), 1.0, 0.15, b)
    M["tree_canopy"] = m

    # emissive things
    def emit(name, color, strength):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nb = NB(m)
        nb.nodes.remove(nb.nodes["Principled BSDF"])
        e = nb.n("ShaderNodeEmission", in_Strength=strength)
        e.inputs["Color"].default_value = (*color, 1)
        nb.l(e.outputs[0], output_of(nb).inputs["Surface"])
        M[name] = m

    emit("led_grow", (1.0, 0.88, 0.95), 22 if NIGHT else 6)
    emit("led_purple", (0.75, 0.22, 1.0), 18 if NIGHT else 10)
    emit("led_warm", (1.0, 0.80, 0.55), 25 if NIGHT else 4)
    emit("ceiling_lamp", (1.0, 0.97, 0.92), 12 if NIGHT else 1.5)

    # sign letters: champagne metal by day, glowing at dusk
    m, nb, b = new_mat("sign")
    set_bsdf(b, (0.86, 0.68, 0.40), 0.2, 1.0)
    b.inputs["Emission Color"].default_value = (1.0, 0.85, 0.62, 1)
    b.inputs["Emission Strength"].default_value = 18.0 if NIGHT else 0.6
    M["sign"] = m
    m, nb, b = new_mat("sign_white")
    set_bsdf(b, (0.85, 0.85, 0.82), 0.3)
    b.inputs["Emission Color"].default_value = (1.0, 0.95, 0.88, 1)
    b.inputs["Emission Strength"].default_value = 6.0 if NIGHT else 0.0
    M["sign_white"] = m

    # image-textured panels
    def image_mat(name, path, emission=0.0, rough=0.4):
        m, nb, b = new_mat(name)
        tex = nb.n("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(path)
        nb.l(tex.outputs["Color"], b.inputs["Base Color"])
        set_bsdf(b, rough=rough, spec=0.5)
        if emission:
            nb.l(tex.outputs["Color"], b.inputs["Emission Color"])
            b.inputs["Emission Strength"].default_value = emission
            b.inputs["Base Color"].default_value = (0, 0, 0, 1)
            nb.links.remove(b.inputs["Base Color"].links[0])
            set_bsdf(b, (0.0, 0.0, 0.0), 0.05, spec=0.6)
        M[name] = m

    image_mat("screen", os.path.join(TEX, "dashboard.jpg"), 2.2 if NIGHT else 3.2)
    for i in (1, 2, 3):
        image_mat(f"board{i}", os.path.join(TEX, f"board{i}.jpg"), 0.0, 0.5)
    simple("board_frame", (0.05, 0.30, 0.18), 0.4, 0.2)

    # distant residential towers: window grid + aerial haze
    for i, col in enumerate([(0.62, 0.46, 0.40), (0.66, 0.66, 0.64), (0.52, 0.55, 0.58),
                             (0.68, 0.60, 0.47), (0.60, 0.55, 0.50)]):
        m, nb, b = new_mat(f"tower{i}")
        p = nb.world_pos()
        sp = nb.n("ShaderNodeSeparateXYZ")
        nb.l(p, sp.inputs[0])
        h = nb.math("ADD", sp.outputs[0], sp.outputs[1])
        wx = nb.math("LESS_THAN", nb.math("FRACT", nb.math("DIVIDE", h, 3.4)), 0.42)
        wz = nb.math("LESS_THAN", nb.math("FRACT", nb.math("DIVIDE", sp.outputs[2], 3.0)), 0.45)
        win = nb.math("MULTIPLY", wx, wz)
        band = nb.math("LESS_THAN", nb.math("FRACT", nb.math("DIVIDE", sp.outputs[2], 3.0)), 0.07)
        base = nb.mix_rgb(band, col, tuple(min(1.0, c * 1.18) for c in col))
        base = nb.mix_rgb(win, base, (0.13, 0.16, 0.20))
        dirt = nb.noise(p, 0.15, 5)
        base = nb.mix_rgb(nb.math("MULTIPLY", dirt, 0.35), base, (0.25, 0.24, 0.22), "MULTIPLY")
        nb.l(base, b.inputs["Base Color"])
        set_bsdf(b, rough=0.8, spec=0.3)
        if NIGHT:
            cell = nb.n("ShaderNodeCombineXYZ")
            nb.l(nb.math("FLOOR", nb.math("DIVIDE", h, 3.4)), cell.inputs[0])
            nb.l(nb.math("FLOOR", nb.math("DIVIDE", sp.outputs[2], 3.0)), cell.inputs[1])
            wn = nb.n("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
            nb.l(cell.outputs[0], wn.inputs["Vector"])
            lit = nb.math("MULTIPLY", win, nb.math("GREATER_THAN", wn.outputs["Value"], 0.62))
            b.inputs["Emission Color"].default_value = (1.0, 0.75, 0.45, 1)
            nb.l(nb.math("MULTIPLY", lit, 3.0), b.inputs["Emission Strength"])
        # haze: blend towards horizon colour with distance
        cam = nb.n("ShaderNodeCameraData")
        k = nb.math("MULTIPLY", cam.outputs["View Distance"], -1.0 / 260.0)
        fac = nb.math("SUBTRACT", 1.0, nb.math("EXPONENT", k))
        haze = nb.n("ShaderNodeEmission", in_Strength=HAZE_STRENGTH)
        haze.inputs["Color"].default_value = (*HAZE_COLOR, 1)
        mix = nb.n("ShaderNodeMixShader")
        nb.l(nb.math("MULTIPLY", fac, 0.85), mix.inputs[0])
        nb.l(b.outputs[0], mix.inputs[1])
        nb.l(haze.outputs[0], mix.inputs[2])
        nb.l(mix.outputs[0], output_of(nb).inputs["Surface"])
        M[f"tower{i}"] = m

    m, nb, b = new_mat("ground")
    p = nb.world_pos()
    n1 = nb.noise(p, 0.05, 4)
    nb.l(nb.ramp(n1, [(0.35, (0.05, 0.09, 0.03)), (0.65, (0.20, 0.20, 0.18))]), b.inputs["Base Color"])
    set_bsdf(b, rough=0.9)
    M["ground"] = m


HAZE_COLOR = (0.70, 0.78, 0.88)
HAZE_STRENGTH = 1.0


# ---------------------------------------------------------------- mesh builder
class MB:
    """Accumulates boxes / prisms / tubes into one mesh object (fast, few objects)."""

    def __init__(self):
        self.v, self.f, self.r, self.mi = [], [], [], []

    def _faces(self, base, faces, rnd, mat):
        for fc in faces:
            self.f.append(tuple(base + k for k in fc))
            self.r.append(rnd)
            self.mi.append(mat)

    def box(self, x0, x1, y0, y1, z0, z1, rnd=None, mat=0):
        if x0 > x1: x0, x1 = x1, x0
        if y0 > y1: y0, y1 = y1, y0
        if z0 > z1: z0, z1 = z1, z0
        i = len(self.v)
        self.v += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                   (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        self._faces(i, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)],
                    random.random() if rnd is None else rnd, mat)

    def beam(self, p0, p1, w, h, up=(0, 0, 1), rnd=0.0, mat=0):
        p0, p1 = Vector(p0), Vector(p1)
        d = (p1 - p0).normalized()
        upv = Vector(up)
        if abs(d.dot(upv)) > 0.99:
            upv = Vector((1, 0, 0))
        side = d.cross(upv).normalized()
        u = side.cross(d).normalized()
        i = len(self.v)
        for p in (p0, p1):
            for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                self.v.append(tuple(p + side * (sx * w / 2) + u * (sz * h / 2)))
        self._faces(i, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)],
                    rnd, mat)

    def tube(self, p0, p1, r, seg=12, caps=True, rnd=0.0, mat=0, r1=None):
        p0, p1 = Vector(p0), Vector(p1)
        d = (p1 - p0).normalized()
        a = Vector((1, 0, 0)) if abs(d.x) < 0.9 else Vector((0, 1, 0))
        s = d.cross(a).normalized()
        t = d.cross(s).normalized()
        r1 = r if r1 is None else r1
        i = len(self.v)
        for p, rr in ((p0, r), (p1, r1)):
            for k in range(seg):
                ang = 2 * math.pi * k / seg
                self.v.append(tuple(p + s * (math.cos(ang) * rr) + t * (math.sin(ang) * rr)))
        faces = [(k, (k + 1) % seg, seg + (k + 1) % seg, seg + k) for k in range(seg)]
        if caps:
            faces.append(tuple(range(seg - 1, -1, -1)))
            faces.append(tuple(seg + k for k in range(seg)))
        self._faces(i, faces, rnd, mat)

    def poly(self, pts, rnd=0.0, mat=0):
        i = len(self.v)
        self.v += [tuple(p) for p in pts]
        self._faces(i, [tuple(range(len(pts)))], rnd, mat)

    def disc(self, c, r, normal_z=-1, seg=20, mat=0):
        pts = [(c[0] + r * math.cos(2 * math.pi * k / seg), c[1] + r * math.sin(2 * math.pi * k / seg), c[2])
               for k in range(seg)]
        if normal_z < 0:
            pts.reverse()
        self.poly(pts, mat=mat)

    def build(self, name, mats, smooth=False, bevel=0.0, coll=None):
        if not self.v:
            return None
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        me.update()
        at = me.attributes.new("rand", "FLOAT", "FACE")
        at.data.foreach_set("value", self.r)
        if not isinstance(mats, (list, tuple)):
            mats = [mats]
        for m in mats:
            me.materials.append(M[m] if isinstance(m, str) else m)
        me.polygons.foreach_set("material_index", self.mi)
        if smooth:
            me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        ob = bpy.data.objects.new(name, me)
        link(ob, coll)
        if bevel:
            md = ob.modifiers.new("bevel", "BEVEL")
            md.width = bevel
            md.segments = 2
            md.limit_method = "ANGLE"
            md.harden_normals = False
        return ob


def collection(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def instance(src_mesh, name, loc, rot=(0, 0, 0), scale=1.0, coll=None):
    ob = bpy.data.objects.new(name, src_mesh)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = (scale, scale, scale) if isinstance(scale, (int, float)) else scale
    link(ob, coll)
    return ob


def plane_uv(name, center, size, rot, mat, coll=None):
    """Textured rectangle (has UVs); default faces +z before rotation."""
    w, h = size
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)], [],
                   [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    for li, co in zip(range(4), [(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[li].uv = co
    me.materials.append(M[mat])
    ob = bpy.data.objects.new(name, me)
    ob.location = center
    ob.rotation_euler = rot
    link(ob, coll)
    return ob


def text(body, font_path, size, loc, rot, mat, extrude=0.01, align="CENTER", coll=None, spacing=1.0):
    cu = bpy.data.curves.new("txt", type="FONT")
    cu.body = body
    cu.font = bpy.data.fonts.load(font_path, check_existing=True)
    cu.size = size
    cu.extrude = extrude
    cu.align_x = align
    cu.align_y = "CENTER"
    cu.space_character = spacing
    ob = bpy.data.objects.new("txt_" + body[:6], cu)
    ob.location = loc
    ob.rotation_euler = rot
    ob.data.materials.append(M[mat])
    link(ob, coll)
    return ob


# ---------------------------------------------------------------- plants
def rosette_mesh(name, seed, n=16, L=(0.07, 0.16), W=0.55, tilt=(75, 15), droop=0.7, cup=0.35,
                 ruffle=0.0, rfreq=6, spoon=False, z0=0.0, nu=8, nv=6, berries=0, flowers=0,
                 flower_mat=None):
    rnd = random.Random(seed)
    verts, faces, lu, mats = [], [], [], []
    for i in range(n):
        t = i / max(1, n - 1)
        Ll = (L[0] + (L[1] - L[0]) * t) * rnd.uniform(0.85, 1.15)
        tl = math.radians(tilt[0] + (tilt[1] - tilt[0]) * t + rnd.uniform(-8, 8))
        az = i * 2.39996 + rnd.uniform(-0.25, 0.25)
        dr = droop * (0.35 + 0.65 * t) * rnd.uniform(0.8, 1.2)
        phase = rnd.uniform(0, 6.28)
        mid = [(0.004, z0 + 0.01 * (1 - t), tl)]
        for k in range(1, nu + 1):
            u = k / nu
            a = tl - dr * u ** 1.5
            px, pz, _ = mid[-1]
            mid.append((px + Ll / nu * math.cos(a), pz + Ll / nu * math.sin(a), a))
        base = len(verts)
        ca, sa = math.cos(az), math.sin(az)
        for k, (mx, mz, a) in enumerate(mid):
            u = k / nu
            if spoon:
                w = Ll * W * (0.12 + 0.88 * max(0.0, min(1.0, (u - 0.3) / 0.4))) * math.sqrt(max(0.0, 1 - u ** 6))
            else:
                w = Ll * W * math.sin(math.pi * min(1.0, u * 0.92 + 0.04)) ** 0.75
            nx, nz = -math.sin(a), math.cos(a)
            for j in range(nv + 1):
                v = -1 + 2 * j / nv
                off = cup * v * v * w + ruffle * math.sin(rfreq * math.pi * v + phase + u * 7) * u ** 2 * abs(v)
                lx = mx + nx * off
                lz = mz + nz * off
                ly = v * w
                verts.append((lx * ca - ly * sa, lx * sa + ly * ca, lz))
                lu.append(u)
        for k in range(nu):
            for j in range(nv):
                a0 = base + k * (nv + 1) + j
                faces.append((a0, a0 + 1, a0 + nv + 2, a0 + nv + 1))
                mats.append(0)
    # berries / flowers (simple low-poly blobs)
    for kind, count, mi in (("berry", berries, 1), ("flower", flowers, 2)):
        for b in range(count):
            az = rnd.uniform(0, 6.28)
            rr = rnd.uniform(0.6, 1.0) * L[1] * 0.9
            cx, cy = rr * math.cos(az), rr * math.sin(az)
            cz = z0 + (0.03 if kind == "berry" else 0.09) + rnd.uniform(0, 0.03)
            sz = 0.018 if kind == "berry" else 0.016
            base = len(verts)
            ring = 6
            verts.append((cx, cy, cz + sz * (0.6 if kind == "berry" else 0.2)))
            lu.append(0.5)
            for k in range(ring):
                ang = 2 * math.pi * k / ring
                verts.append((cx + sz * math.cos(ang), cy + sz * math.sin(ang), cz))
                lu.append(0.5)
            verts.append((cx, cy, cz - (sz * 1.6 if kind == "berry" else sz * 0.2)))
            lu.append(0.5)
            for k in range(ring):
                faces.append((base, base + 1 + k, base + 1 + (k + 1) % ring))
                faces.append((base + ring + 1, base + 1 + (k + 1) % ring, base + 1 + k))
                mats += [mi, mi]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    at = me.attributes.new("lu", "FLOAT", "POINT")
    at.data.foreach_set("value", lu)
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.polygons.foreach_set("material_index", mats)
    return me


def grass_mesh(name, seed, blades=90, H=(0.45, 0.85)):
    rnd = random.Random(seed)
    verts, faces, lu = [], [], []
    seg = 6
    for _ in range(blades):
        az = rnd.uniform(0, 6.28)
        r0 = rnd.uniform(0, 0.07)
        bx, by = r0 * math.cos(az), r0 * math.sin(az)
        Ln = rnd.uniform(*H)
        lean = rnd.uniform(0.15, 0.6)
        bend = rnd.uniform(0.2, 0.7)
        dx, dy = math.cos(az), math.sin(az)
        wv = (-dy, dx)
        base = len(verts)
        for k in range(seg + 1):
            t = k / seg
            hdist = Ln * (lean * t + bend * t * t)
            z = Ln * (t - 0.35 * bend * t * t) * 1.0
            w = 0.006 * (1 - t) + 0.0008
            cx, cy = bx + dx * hdist, by + dy * hdist
            verts.append((cx - wv[0] * w, cy - wv[1] * w, z))
            verts.append((cx + wv[0] * w, cy + wv[1] * w, z))
            lu += [t, t]
        for k in range(seg):
            a = base + 2 * k
            faces.append((a, a + 1, a + 3, a + 2))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    at = me.attributes.new("lu", "FLOAT", "POINT")
    at.data.foreach_set("value", lu)
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.materials.append(M["leaf_grass"])
    return me


def palm_mesh(name, seed, height=9.0, fronds=18):
    rnd = random.Random(seed)
    mb = MB()
    # trunk (slightly leaning)
    lean = Vector((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), 0))
    pts = [Vector((0, 0, 0)) + lean * (t / 6) ** 2 + Vector((0, 0, height * t / 6)) for t in range(7)]
    for a, b in zip(pts[:-1], pts[1:]):
        mb.tube(a, b, 0.2, 10, caps=False, mat=0)
    top = pts[-1]
    verts, faces, lu = [], [], []
    for f in range(fronds):
        az = f * 2.39996 + rnd.uniform(-0.2, 0.2)
        elev = math.radians(rnd.uniform(-10, 60))
        Lf = rnd.uniform(2.2, 3.0)
        d = Vector((math.cos(az), math.sin(az), 0))
        side = Vector((-math.sin(az), math.cos(az), 0))
        rach = []
        p = top.copy()
        ang = elev
        ns = 14
        for k in range(ns + 1):
            rach.append((p.copy(), ang))
            p += (d * math.cos(ang) + Vector((0, 0, math.sin(ang)))) * (Lf / ns)
            ang -= math.radians(5.5)
        for k in range(1, ns + 1):
            pk, ak = rach[k]
            t = k / ns
            ll = 0.75 * math.sin(math.pi * (0.15 + 0.85 * t)) + 0.08
            for sgn in (-1, 1):
                tipdir = (side * sgn * 0.8 + d * 0.5).normalized()
                tip = pk + tipdir * ll + Vector((0, 0, -0.35 * ll))
                mid = pk + tipdir * (ll * 0.5) + Vector((0, 0, -0.05 * ll))
                w = 0.035
                fwd = d * w
                base = len(verts)
                for q, uu in ((pk - fwd, 0), (pk + fwd, 0), (mid + fwd * 0.8, 0.5), (mid - fwd * 0.8, 0.5),
                              (tip, 1.0)):
                    verts.append(tuple(q))
                    lu.append(uu)
                faces.append((base, base + 1, base + 2, base + 3))
                faces.append((base + 3, base + 2, base + 4))
    me = bpy.data.meshes.new(name + "_leaf")
    me.from_pydata(verts, [], faces)
    at = me.attributes.new("lu", "FLOAT", "POINT")
    at.data.foreach_set("value", lu)
    me.materials.append(M["leaf_palm"])
    return mb, me


# ---------------------------------------------------------------- site: corridor block, terrace, context
def build_site():
    coll = collection("site")
    walls = MB()     # white paint
    tiles = MB()     # white tiles
    reds = MB()      # red paint
    floors = MB()    # corridor floor tiles
    caps = MB()      # stone caps
    rails = MB()     # stainless
    concrete = MB()
    lamps = MB()
    win = MB()       # window glass
    winf = MB()      # window frames (white)

    # ---- lower terrace slab + podium below (seen in aerial)
    concrete.box(TX0 - 0.25, BX1, TY0 - 0.05, TY1 + 0.25, -0.30, 0.0)
    walls.box(TX0 - 0.25, BX1, TY0, TY1 + 0.25, -7.2, -0.30)

    # ---- teaching block: corridor floors on the terrace side
    cols_x = [-11.65, -7.75, -3.85, 0.05, 3.95, 7.85, 11.75]
    for k in range(N_FLOORS):
        zf = CORR_Z + k * FLOOR_H
        zc = zf + FLOOR_H
        floors.box(BX0, BX1, -7.9, -5.0, zf - 0.20, zf)
        # parapet with railing
        segs = [(BX0, OPEN_X0), (OPEN_X1, BX1)] if k == 0 else [(BX0, BX1)]
        for (a, b) in segs:
            if k == 0:
                tiles.box(a, b, -5.25, -5.0, 0.0, zf + 0.95)
                caps.box(a - (0 if a == BX0 else 0.02), b + (0.02 if b != BX1 else 0), -5.28, -4.97,
                         zf + 0.95, zf + 1.0)
            else:
                reds.box(a, b, -5.25, -5.0, zf - 0.2, zf + 0.95)
                caps.box(a, b, -5.28, -4.97, zf + 0.95, zf + 1.0)
            x = a + 0.15
            while x < b - 0.1:
                rails.tube((x, -5.12, zf + 1.0), (x, -5.12, zf + 1.22), 0.018, 8)
                x += 1.1
            rails.tube((a + 0.05, -5.12, zf + 1.24), (b - 0.05, -5.12, zf + 1.24), 0.026, 12)
        # spandrel beam below next slab + ceiling lamps
        walls.box(BX0, BX1, -5.35, -5.0, zc - 0.75, zc - 0.20)
        x = BX0 + 1.8
        while x < BX1:
            lamps.disc((x, -6.5, zc - 0.205), 0.17, -1, 20)
            x += 3.9
        # inner wall with windows
        walls.box(BX0, BX1, -8.15, -7.9, zf, zc - 0.2)
        x = BX0 + 0.9
        i = 0
        while x + 1.8 < BX1:
            if i % 3 == 2:
                winf.box(x + 0.4, x + 1.45, -7.92, -7.88, zf, zf + 2.2)
                win.box(x + 0.48, x + 1.37, -7.93, -7.87, zf + 0.05, zf + 2.15)
            else:
                winf.box(x, x + 2.1, -7.92, -7.87, zf + 0.9, zf + 2.55)
                win.box(x + 0.06, x + 2.04, -7.93, -7.86, zf + 0.96, zf + 2.49)
                win.box(x + 1.04, x + 1.06, -7.94, -7.85, zf + 0.96, zf + 2.49)
            x += 3.9
            i += 1
    # roof slab + parapet
    ztop = CORR_Z + N_FLOORS * FLOOR_H
    walls.box(BX0, BX1, -16.0, -5.0, ztop - 0.2, ztop)
    walls.box(BX0, BX1, -5.25, -5.0, ztop, ztop + 1.1)
    # columns
    for cx in cols_x:
        walls.box(cx - 0.25, cx + 0.25, -5.45, -4.95, 0.0, ztop + 1.1)
    # classroom mass (behind corridor) + end wall
    walls.box(BX0, BX1, -16.0, -8.15, CORR_Z - 0.2, ztop - 0.2)
    walls.box(BX0 - 0.3, BX0, -16.0, -5.0, -7.2, ztop + 1.1)

    # ---- opening: steps from corridor down to the terrace deck
    steel_bits = MB()
    deck = MB()
    deck.box(OPEN_X0, OPEN_X1, -5.25, -5.0, CORR_Z - 0.04, CORR_Z)        # threshold
    for i, (y0, y1, z) in enumerate([(-5.0, -4.7, 0.40), (-4.7, -4.4, 0.25)]):
        x = OPEN_X0
        tiles.box(OPEN_X0, OPEN_X1, y0, y1, 0.0, z - 0.04)
        while x < OPEN_X1 - 0.01:
            deck.box(x, min(OPEN_X1, x + 0.145), y0, y1, z - 0.04, z)
            x += 0.15
        steel_bits.box(OPEN_X0, OPEN_X1, y0 - 0.005, y0 + 0.03, z - 0.045, z + 0.002)
    # handrails along the steps
    for xx in (OPEN_X0 + 0.06, OPEN_X1 - 0.06):
        steel_bits.tube((xx, -5.15, CORR_Z + 1.0), (xx, -5.15, CORR_Z + 1.24), 0.03, 12)
        steel_bits.tube((xx, -4.25, DECK), (xx, -4.25, DECK + 0.95), 0.025, 12)
        steel_bits.tube((xx, -5.15, CORR_Z + 1.0), (xx, -4.25, DECK + 0.95), 0.022, 12)
    # opened gate leaves (stainless frame + glass), swung back against the parapet
    gate_glass = MB()
    for xx, sgn in ((OPEN_X0 + 0.03, 1), (OPEN_X1 - 0.03, -1)):
        x0 = xx + sgn * 0.08
        y0, y1 = -4.98, -4.18
        steel_bits.box(x0 - 0.02, x0 + 0.02, y0, y1, DECK + 0.12, DECK + 0.16)
        steel_bits.box(x0 - 0.02, x0 + 0.02, y0, y1, DECK + 1.06, DECK + 1.1)
        steel_bits.box(x0 - 0.02, x0 + 0.02, y1 - 0.04, y1, DECK + 0.12, DECK + 1.1)
        gate_glass.box(x0 - 0.004, x0 + 0.004, y0 + 0.02, y1 - 0.04, DECK + 0.16, DECK + 1.06)
    steel_bits.build("steps_steel", "steel", coll=coll)
    gate_glass.build("gate_glass", "glass", coll=coll)
    deck.build("steps_deck", "wpc_x", coll=coll, bevel=0.003)

    # ---- terrace parapets (north + west) and east raised platform
    tiles.box(TX0 - 0.25, TX1, TY1, TY1 + 0.25, 0.0, 1.45)
    caps.box(TX0 - 0.28, TX1, TY1 - 0.03, TY1 + 0.28, 1.45, 1.5)
    tiles.box(TX0 - 0.25, TX0, TY0, TY1, 0.0, 1.45)
    caps.box(TX0 - 0.28, TX0 + 0.03, TY0, TY1, 1.45, 1.5)
    concrete.box(TX1, BX1, TY0, TY1 + 0.25, 0.0, 0.9)
    tiles.box(TX1, BX1, TY1, TY1 + 0.25, 0.9, 2.1)
    caps.box(TX1, BX1, TY1 - 0.03, TY1 + 0.28, 2.1, 2.15)
    dark = MB()
    dark.box(TX1 - 0.01, TX1 + 0.01, TY0, TY1, 0.0, 0.25)
    dark.box(TX0 - 0.01, TX0 + 0.005, TY0, TY1, 0.0, 0.18)
    dark.box(TX0, TX1, TY1 - 0.005, TY1 + 0.01, 0.0, 0.18)
    dark.build("waterproof_band", "black", coll=coll)

    # bulletin boards (existing, re-skinned as science boards)
    frames = MB()
    for i, cx in enumerate([-3.0, 6.6]):
        frames.box(cx - 1.25, cx + 1.25, TY1 - 0.06, TY1, 0.5, 1.45)
        plane_uv(f"board_n{i}", (cx, TY1 - 0.065, 0.975), (2.38, 0.85), (math.radians(90), 0, 0),
                 f"board{1 + i % 3}", coll)
    for i, cy in enumerate([1.0, 5.4]):
        frames.box(TX0, TX0 + 0.06, cy - 1.25, cy + 1.25, 0.5, 1.45)
        plane_uv(f"board_w{i}", (TX0 + 0.065, cy, 0.975), (2.38, 0.85),
                 (math.radians(90), 0, math.radians(-90)), f"board{2 + i % 2}", coll)
    frames.build("board_frames", "board_frame", coll=coll, bevel=0.01)

    # red stair block to the east (matches the photos)
    reds.box(BX1, BX1 + 6.5, -12.0, 3.0, -7.2, 12.4)
    k = 0
    while CORR_Z + k * FLOOR_H < 12.4:
        z = CORR_Z + k * FLOOR_H - 0.15
        caps.box(BX1 - 0.02, BX1 + 6.52, -12.02, 3.02, z, z + 0.16)
        k += 1
    caps.box(BX1 - 0.02, BX1 + 6.52, -12.02, 3.02, 12.4, 12.55)
    x = BX1 + 0.2
    while x < BX1 + 6.4:
        rails.tube((x, 2.9, 12.55), (x, 2.9, 13.4), 0.02, 8)
        x += 1.2
    rails.tube((BX1 + 0.1, 2.9, 13.4), (BX1 + 6.4, 2.9, 13.4), 0.025, 10)

    tiles.build("wall_tiles", "wall_tile", coll=coll)
    walls.build("walls", "paint_white", coll=coll)
    reds.build("red_paint", "paint_red", coll=coll)
    floors.build("corridor_floor", "floor_tile", coll=coll)
    caps.build("caps", "cap_stone", coll=coll, bevel=0.008)
    rails.build("railings", "steel", smooth=True, coll=coll)
    concrete.build("concrete", "concrete", coll=coll)
    lamps.build("ceiling_lamps", "ceiling_lamp", coll=coll)
    win.build("windows", "window", coll=coll)
    winf.build("window_frames", "paint_white", coll=coll)

    # ---- distant context: ground, towers, trees
    ctx = collection("context")
    g = MB()
    g.box(-600, 600, -600, 600, -7.4, -7.2)
    g.build("ground", "ground", coll=ctx)
    rnd = random.Random(11)
    placed = []
    for i in range(80):
        for _ in range(60):
            ang = rnd.uniform(-math.pi, math.pi)
            dist = rnd.uniform(60, 300)
            cx, cy = 3 + dist * math.cos(ang), 2 + dist * math.sin(ang)
            if -45 < cx < 45 and -60 < cy < 0:      # keep the school campus clear
                continue
            if all((cx - px) ** 2 + (cy - py) ** 2 > 30 ** 2 for px, py in placed):
                break
        placed.append((cx, cy))
        north = 55 < math.degrees(ang) < 125
        tall = dist > (170 if north else 95) and rnd.random() < 0.6
        h = rnd.uniform(38, 85) if tall else rnd.uniform(16, 25)
        w = rnd.uniform(15, 24) if tall else rnd.uniform(24, 45)
        d = rnd.uniform(12, 17)
        rot = math.atan2(cy - 2, cx - 3) + math.pi / 2 + rnd.uniform(-0.3, 0.3)
        tb = MB()
        tb.box(-w / 2, w / 2, -d / 2, d / 2, -7.2, h - 7.2)
        if rnd.random() < 0.6:
            tb.box(-w / 4, w / 4, -d / 3, d / 3, h - 7.2, h - 7.2 + rnd.uniform(3, 6))
        ob = tb.build(f"tower{i}", f"tower{rnd.randrange(5)}", coll=ctx)
        ob.location = (cx, cy, 0)
        ob.rotation_euler = (0, 0, rot)

    # trees beyond the parapets (tops visible over the wall, like the photos)
    tree_mb = MB()
    trnd = random.Random(5)
    for (tx, ty, hh, rr) in [(-10, 14, 9.5, 3.0), (-3, 16.5, 9.0, 2.8), (12, 15, 9.8, 3.2), (17, 11, 8.6, 2.6),
                             (-13, 6, 8.8, 2.8), (-12, -3, 8.2, 2.4), (21, 7, 9.0, 2.8), (4, 18, 10.0, 3.2)]:
        tree_mb.tube((tx, ty, -7.2), (tx, ty, -7.2 + hh * 0.7), 0.22, 8)
        for j in range(11):
            a = trnd.uniform(0, 6.28)
            rad = trnd.uniform(0.1, 0.65) * rr
            r = rr * trnd.uniform(0.3, 0.5)
            loc = (tx + rad * math.cos(a), ty + rad * math.sin(a),
                   -7.2 + hh * 0.72 + trnd.uniform(-0.15, 0.3) * rr + (rr * 0.35 if j == 0 else 0))
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=r, location=loc)
            ob = bpy.context.active_object
            ob.scale = (1, 1, 0.85)
            ob.data.materials.append(M["tree_canopy"])
            ob.data.polygons.foreach_set("use_smooth", [True] * len(ob.data.polygons))
            md = ob.modifiers.new("disp", "DISPLACE")
            tx_ = bpy.data.textures.new("clouds", "CLOUDS")
            tx_.noise_scale = 0.35 * rr
            tx_.noise_depth = 3
            md.texture = tx_
            md.strength = 0.55 * r
            md.mid_level = 0.5
            for c in ob.users_collection:
                c.objects.unlink(ob)
            ctx.objects.link(ob)
    tree_mb.build("tree_trunks", "bark", coll=ctx)
    # palms
    for i, (px, py, hh) in enumerate([(-3.8, 11.6, 9.6), (1.5, 10.8, 10.2), (7.5, 11.5, 9.2)]):
        mb, leaf_me = palm_mesh(f"palm{i}", 30 + i, hh)
        tr = mb.build(f"palm_trunk{i}", "bark", smooth=True, coll=ctx)
        tr.location = (px, py, -7.2)
        lo = bpy.data.objects.new(f"palm_leaf{i}", leaf_me)
        lo.location = (px, py, -7.2)
        link(lo, ctx)


# ---------------------------------------------------------------- terrace landscaping
def build_landscape():
    coll = collection("landscape")
    turf = MB()
    turf.box(TX0 + 0.45, TX1 - 0.45, TY0 + 0.45, TY1 - 0.45, 0.0, 0.025)
    turf.build("turf", "turf", coll=coll)
    peb = MB()
    peb.box(TX0, TX1, TY0, TY1, 0.0, 0.02)                             # perimeter drainage strip
    peb.box(GX0 - 0.45, GX0 + GW + 0.45, GY0 - 0.2, GY0 + GL + 0.45, 0.0, 0.045)
    peb.build("pebbles", "pebble", coll=coll)
    edge = MB()
    for (x0, x1, y0, y1) in [(GX0 - 0.48, GX0 - 0.45, GY0 - 0.2, GY0 + GL + 0.48),
                             (GX0 + GW + 0.45, GX0 + GW + 0.48, GY0 - 0.2, GY0 + GL + 0.48),
                             (GX0 - 0.48, GX0 + GW + 0.48, GY0 + GL + 0.45, GY0 + GL + 0.48)]:
        edge.box(x0, x1, y0, y1, 0.0, 0.06)
    edge.build("pebble_edge", "steel_brushed", coll=coll)

    # decking: path from the steps + apron in front of the gable
    dx = MB()
    y = -4.4
    while y < GY0 - 1.15:
        dx.box(OPEN_X0 + 0.05, OPEN_X1 - 0.05, y, y + 0.14, 0.02, DECK)
        y += 0.146
    x = GX0 - 1.0
    while x < GX0 + GW + 1.0:
        dx.box(x, x + 0.14, GY0 - 1.2, GY0 - 0.02, 0.02, DECK)
        x += 0.146
    dx.build("deck", "wpc_x", coll=coll, bevel=0.004)
    dy = MB()
    dy.build("deck_y", "wpc_y", coll=coll)

    # entrance planters: boxwood balls flanking the portal
    planters = MB()
    box_me = None
    for (cx, cy) in [(GX0 + 0.75, GY0 - 0.75), (GX0 + GW - 0.75, GY0 - 0.75)]:
        planters.box(cx - 0.3, cx + 0.3, cy - 0.3, cy + 0.3, DECK, DECK + 0.6)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=0.36, location=(cx, cy, DECK + 0.6 + 0.3))
        ob = bpy.context.active_object
        ob.data.materials.append(M["boxwood"])
        ob.data.polygons.foreach_set("use_smooth", [True] * len(ob.data.polygons))
        md = ob.modifiers.new("disp", "DISPLACE")
        t = bpy.data.textures.new("bw", "CLOUDS")
        t.noise_scale = 0.12
        md.texture = t
        md.strength = 0.05
        for c in ob.users_collection:
            c.objects.unlink(ob)
        coll.objects.link(ob)
    planters.build("planters_dark", "cladding", coll=coll, bevel=0.006)

    # ornamental grass in long planters along the path
    gm = grass_mesh("grass", 5)
    wp = MB()
    soil = MB()

    def planter(x0, x1, y0, y1, h, t=0.05):
        wp.box(x0, x1, y0, y0 + t, 0.0, h)
        wp.box(x0, x1, y1 - t, y1, 0.0, h)
        wp.box(x0, x0 + t, y0 + t, y1 - t, 0.0, h)
        wp.box(x1 - t, x1, y0 + t, y1 - t, 0.0, h)
        soil.box(x0 + t, x1 - t, y0 + t, y1 - t, 0.0, h - 0.06)

    for x0 in (OPEN_X0 - 0.75, OPEN_X1 + 0.25):
        planter(x0, x0 + 0.5, -4.35, -3.45, 0.5)
        for j, yy in enumerate((-4.15, -3.9, -3.65)):
            instance(gm, "grass", (x0 + 0.25, yy, 0.44), (0, 0, j * 1.7), 1.0, coll)
    # outdoor raised beds (west learning area) + benches
    flower_meshes = [rosette_mesh(f"flower{i}", 70 + i, n=14, L=(0.06, 0.12), W=0.6, tilt=(60, 20),
                                  flowers=14) for i in range(3)]
    for i, me in enumerate(flower_meshes):
        me.materials.append(M["leaf_dark"])
        me.materials.append(M["leaf_dark"])
        me.materials.append(M[["flower_red", "flower_yellow", "flower_purple"][i]])
    for k, (x0, y0) in enumerate([(-4.25, 3.2), (-4.25, 5.1), (-4.25, 7.0)]):
        planter(x0, x0 + 1.6, y0, y0 + 0.8, 0.55)
        rnd = random.Random(k)
        for a in range(5):
            for b in range(3):
                instance(flower_meshes[(a + b + k) % 3], "fl",
                         (x0 + 0.2 + a * 0.3 + rnd.uniform(-0.04, 0.04), y0 + 0.17 + b * 0.23, 0.49),
                         (0, 0, rnd.uniform(0, 6)), rnd.uniform(1.6, 2.0), coll)
        for gx in (x0 + 0.25, x0 + 1.35):
            instance(gm, "grass", (gx, y0 + 0.4, 0.49), (0, 0, k), 0.8, coll)
    wp.build("wpc_planters", "wpc_x", coll=coll, bevel=0.006)
    soil.build("outdoor_soil", "soil", coll=coll)
    # slatted benches for outdoor lessons
    bs = MB()
    bl = MB()
    for (x0, y0) in [(-3.9, -1.2), (-3.9, 0.4)]:
        for k in range(4):
            bs.box(x0, x0 + 1.9, y0 + k * 0.105, y0 + k * 0.105 + 0.09, 0.42, 0.455)
        for xx in (x0 + 0.15, x0 + 1.7):
            bl.box(xx, xx + 0.05, y0 + 0.02, y0 + 0.39, 0.38, 0.42)
            bl.box(xx, xx + 0.05, y0 + 0.02, y0 + 0.07, 0.0, 0.42)
            bl.box(xx, xx + 0.05, y0 + 0.34, y0 + 0.39, 0.0, 0.42)
    bs.build("bench_slats", "wpc_x", coll=coll, bevel=0.005)
    bl.build("bench_legs", "frame", coll=coll, bevel=0.004)

    # weather station (smart-farm sensor mast)
    ws = MB()
    sx, sy = -2.4, 2.3
    ws.tube((sx, sy, 0.0), (sx, sy, 3.0), 0.035, 12)
    ws.tube((sx, sy, 2.4), (sx + 0.6, sy, 2.4), 0.015, 8)
    ws.tube((sx, sy, 2.6), (sx - 0.5, sy, 2.6), 0.015, 8)
    for k in range(3):
        a = k * 2.09
        ws.tube((sx + 0.6, sy, 2.55), (sx + 0.6 + 0.13 * math.cos(a), sy + 0.13 * math.sin(a), 2.55), 0.006, 6)
    ws.tube((sx + 0.6, sy, 2.4), (sx + 0.6, sy, 2.56), 0.01, 6)
    ws.build("weather_mast", "steel", smooth=True, coll=coll)
    wsw = MB()
    for k in range(5):
        r = 0.09 - k * 0.008
        wsw.tube((sx - 0.5, sy, 2.3 + k * 0.045), (sx - 0.5, sy, 2.33 + k * 0.045), r, 16)
    wsw.box(sx - 0.15, sx + 0.15, sy - 0.12, sy + 0.12, 1.5, 1.85)
    for k in range(3):
        a = k * 2.09
        wsw.disc((sx + 0.6 + 0.13 * math.cos(a), sy + 0.13 * math.sin(a), 2.55), 0.03, 1, 10)
    wsw.build("weather_parts", "white_plastic", coll=coll, bevel=0.005)
    sp = MB()
    sp.beam((sx, sy - 0.05, 2.0), (sx, sy - 0.45, 2.25), 0.5, 0.02, up=(0, 0, 1))
    sp.build("solar_panel", "solar", coll=coll)


# ---------------------------------------------------------------- greenhouse shell
def roof_z(v):
    return EH + RISE * (1 - abs(v - GW / 2) / (GW / 2))


def build_greenhouse():
    coll = collection("greenhouse")
    roof_coll = collection("greenhouse_roof")
    fr = MB()          # frame
    rf = MB()          # roof frame (hidden in plan render)
    S = 0.06
    xa, xb = GX0, GX0 + GW
    ya, yb = GY0, GY0 + GL

    # long walls: columns + rails
    for i in range(9):
        y = ya + i * BAY
        for x in (xa, xb):
            fr.box(x - S / 2, x + S / 2, y - S / 2, y + S / 2, PLINTH, EH)
    for x in (xa, xb):
        for z in (PLINTH, DOOR_H, EH - S):
            fr.box(x - S / 2, x + S / 2, ya, yb, z, z + S)
    # gable walls
    for y, south in ((ya, True), (yb, False)):
        for v in (0.9, DOOR_V0, DOOR_V1, 4.7):
            z0 = DECK if (south and v in (DOOR_V0, DOOR_V1)) else PLINTH
            fr.box(xa + v - S / 2, xa + v + S / 2, y - S / 2, y + S / 2, z0, roof_z(v))
        fr.box(GXC - S / 2, GXC + S / 2, y - S / 2, y + S / 2, DOOR_H if south else PLINTH, RH)
        for z in (PLINTH, DOOR_H, EH - S):
            if south and z == PLINTH:
                fr.box(xa, xa + DOOR_V0, y - S / 2, y + S / 2, z, z + S)
                fr.box(xa + DOOR_V1, xb, y - S / 2, y + S / 2, z, z + S)
            else:
                fr.box(xa, xb, y - S / 2, y + S / 2, z, z + S)
    # roof: rafters, ridge, purlins
    for i in range(9):
        y = ya + i * BAY
        rf.beam((xa, y, EH), (GXC, y, RH), S, 0.08)
        rf.beam((GXC, y, RH), (xb, y, EH), S, 0.08)
    rf.box(GXC - 0.05, GXC + 0.05, ya, yb, RH - 0.04, RH + 0.06)
    for t in (0.5,):
        for (x0, x1) in ((xa, GXC), (GXC, xb)):
            xm = x0 + (x1 - x0) * t
            zm = EH + RISE * t
            rf.beam((xm, ya, zm), (xm, yb, zm), S, 0.05)
    # gutters + downpipes
    gut = MB()
    for x in (xa - 0.09, xb + 0.09):
        gut.box(x - 0.08, x + 0.08, ya - 0.08, yb + 0.08, EH - 0.14, EH + 0.02)
    for x in (xa - 0.09, xb + 0.09):
        for y in (ya + 0.12, yb - 0.12):
            gut.tube((x, y, EH - 0.14), (x, y, 0.05), 0.045, 12)
    gut.build("gutters", "frame", smooth=False, coll=coll, bevel=0.004)

    # plinth (aluminium composite cladding)
    pl = MB()
    pl.box(xa - 0.06, xb + 0.06, yb - 0.06, yb + 0.06, 0.0, PLINTH)
    pl.box(xa - 0.06, xa + 0.06, ya - 0.06, yb + 0.06, 0.0, PLINTH)
    pl.box(xb - 0.06, xb + 0.06, ya - 0.06, yb + 0.06, 0.0, PLINTH)
    pl.box(xa - 0.06, xa + DOOR_V0, ya - 0.06, ya + 0.06, 0.0, PLINTH)
    pl.box(xa + DOOR_V1, xb + 0.06, ya - 0.06, ya + 0.06, 0.0, PLINTH)
    pl.build("plinth", "cladding", coll=coll, bevel=0.005)

    # glazing (thin planes)
    gl = MB()
    for x in (xa, xb):
        gl.poly([(x, ya, PLINTH), (x, yb, PLINTH), (x, yb, EH), (x, ya, EH)])
    # north gable
    gl.poly([(xa, yb, PLINTH), (xb, yb, PLINTH), (xb, yb, EH), (GXC, yb, RH), (xa, yb, EH)])
    # south gable around the door
    v0, v1 = xa + DOOR_V0, xa + DOOR_V1
    gl.poly([(xa, ya, PLINTH), (v0, ya, PLINTH), (v0, ya, roof_z(DOOR_V0)), (xa, ya, EH)])
    gl.poly([(v1, ya, PLINTH), (xb, ya, PLINTH), (xb, ya, EH), (v1, ya, roof_z(DOOR_V1))])
    gl.poly([(v0, ya, DOOR_H), (v1, ya, DOOR_H), (v1, ya, roof_z(DOOR_V1)), (GXC, ya, RH),
             (v0, ya, roof_z(DOOR_V0))])
    gl.build("glazing", "glass", coll=coll)
    rg = MB()
    rg.poly([(xa, ya, EH), (GXC, ya, RH), (GXC, yb, RH), (xa, yb, EH)])
    rg.poly([(GXC, ya, RH), (xb, ya, EH), (xb, yb, EH), (GXC, yb, RH)])
    rg.build("roof_glazing", "glass_roof", coll=roof_coll)

    # sliding doors: left leaf closed, right leaf slid behind it (doorway half open)
    dfr = MB()
    dgl = MB()
    leaf_w = (DOOR_V1 - DOOR_V0) / 2 + 0.03
    for (u0, yoff) in ((DOOR_V0, -0.03), (DOOR_V0 + 0.32, -0.07)):
        x0 = xa + u0
        x1 = x0 + leaf_w
        yy = ya + yoff
        for (a, b, c, d) in ((x0, x0 + 0.05, DECK, DOOR_H - 0.04), (x1 - 0.05, x1, DECK, DOOR_H - 0.04),
                             (x0, x1, DECK, DECK + 0.08), (x0, x1, DOOR_H - 0.09, DOOR_H - 0.04)):
            dfr.box(a, b, yy - 0.02, yy + 0.02, c, d)
        dgl.poly([(x0 + 0.05, yy, DECK + 0.08), (x1 - 0.05, yy, DECK + 0.08), (x1 - 0.05, yy, DOOR_H - 0.09),
                  (x0 + 0.05, yy, DOOR_H - 0.09)])
    dfr.box(xa + DOOR_V0, xa + DOOR_V1, ya - 0.1, ya - 0.0, DOOR_H - 0.06, DOOR_H)     # track
    dfr.build("door_frames", "frame_dark", coll=coll, bevel=0.003)
    dgl.build("door_glass", "glass", coll=coll)
    hd = MB()
    for x in (xa + DOOR_V0 + leaf_w - 0.1, xa + DOOR_V0 + 0.32 + leaf_w - 0.1):
        hd.tube((x, ya - 0.08, 0.95), (x, ya - 0.08, 1.75), 0.014, 10)
    hd.build("door_handles", "steel", smooth=True, coll=coll)

    # roof vents (one each slope, opened ~12 degrees about the ridge)
    for side in (-1, 1):
        for yc in (ya + 2.5 * BAY, ya + 5.5 * BAY):
            hinge0 = Vector((GXC, yc - 0.55, RH + 0.03))
            hinge1 = Vector((GXC, yc + 0.55, RH + 0.03))
            down = Vector((side * math.cos(PITCH - math.radians(12)), 0, -math.sin(PITCH - math.radians(12))))
            far = down * 1.0
            vb = MB()
            vb.beam(hinge0, hinge0 + far, 0.04, 0.05)
            vb.beam(hinge1, hinge1 + far, 0.04, 0.05)
            vb.beam(hinge0 + far, hinge1 + far, 0.04, 0.05)
            vb.build("vent_frame", "frame", coll=roof_coll)
            vg = MB()
            vg.poly([tuple(hinge0), tuple(hinge1), tuple(hinge1 + far), tuple(hinge0 + far)])
            vg.build("vent_glass", "glass_roof", coll=roof_coll)

    fr.build("frame", "frame", coll=coll, bevel=0.006)
    rf.build("roof_frame", "frame", coll=roof_coll, bevel=0.006)

    # ---- entrance portal with sign
    po = MB()
    py0, py1 = ya - 0.62, ya + 0.04
    pv0, pv1 = xa + DOOR_V0 - 0.48, xa + DOOR_V1 + 0.48
    ptop = 3.45
    po.box(pv0, xa + DOOR_V0 - 0.05, py0, py1, 0.0, ptop)
    po.box(xa + DOOR_V1 + 0.05, pv1, py0, py1, 0.0, ptop)
    po.box(pv0, pv1, py0, py1, DOOR_H + 0.02, ptop)
    po.build("portal", "cladding", coll=coll, bevel=0.008)
    # wood lining inside the portal
    wl = MB()
    wl.box(xa + DOOR_V0 - 0.06, xa + DOOR_V1 + 0.06, py0 + 0.02, py1 - 0.06, DOOR_H, DOOR_H + 0.025)
    wl.box(xa + DOOR_V0 - 0.07, xa + DOOR_V0 - 0.045, py0 + 0.02, py1 - 0.06, 0.0, DOOR_H + 0.02)
    wl.box(xa + DOOR_V1 + 0.045, xa + DOOR_V1 + 0.07, py0 + 0.02, py1 - 0.06, 0.0, DOOR_H + 0.02)
    wl.build("portal_wood", "wpc_x", coll=coll)
    lt = MB()
    for x in (GXC - 0.55, GXC + 0.55):
        lt.disc((x, (py0 + py1) / 2 - 0.1, DOOR_H - 0.003), 0.045, -1, 16)
    lt.box(pv0 + 0.03, pv1 - 0.03, py0 - 0.012, py0 - 0.002, DOOR_H + 0.05, DOOR_H + 0.07)   # LED line
    lt.build("portal_lights", "led_warm", coll=coll)
    face_y = py0 - 0.004
    text("智慧农场", CJK_FONT, 0.40, (GXC, face_y, 3.05), (math.radians(90), 0, 0), "sign", 0.018,
         coll=coll, spacing=1.08)
    text("SMART FARM · 劳动教育实践基地", CJK_FONT, 0.105, (GXC, face_y, 2.68), (math.radians(90), 0, 0),
         "sign_white", 0.006, coll=coll, spacing=1.05)
    # small wall sign at the corridor opening
    text("智慧农场 →", CJK_FONT, 0.09, (OPEN_X1 + 0.5, -4.982, 1.25), (math.radians(90), 0, 0),
         "sign", 0.004, coll=coll)
    return roof_coll


# ---------------------------------------------------------------- greenhouse interior
def L2W(u, v, z=0.0):
    """greenhouse local (u along length from the door, v across from the west wall) -> world"""
    return (GX0 + v, GY0 + u, z)


def build_interior():
    coll = collection("interior")
    rnd = random.Random(7)
    # floor
    fl = MB()
    x = GX0 + 0.06
    while x < GX0 + GW - 0.06:
        fl.box(x, min(x + 0.14, GX0 + GW - 0.06), GY0 + 0.06, GY0 + GL - 0.06, 0.02, DECK)
        x += 0.146
    fl.build("floor_deck", "wpc_y", coll=coll, bevel=0.003)

    # plant meshes
    lettuce = [rosette_mesh(f"lettuce{i}", i, n=18, L=(0.06, 0.15), W=0.62, tilt=(80, 12), droop=0.9,
                            cup=0.3, ruffle=0.012, rfreq=7) for i in range(4)]
    red = [rosette_mesh(f"red{i}", 20 + i, n=18, L=(0.06, 0.15), W=0.5, tilt=(80, 15), droop=0.8,
                        cup=0.25, ruffle=0.016, rfreq=9) for i in range(3)]
    bok = [rosette_mesh(f"bok{i}", 40 + i, n=11, L=(0.12, 0.2), W=0.42, tilt=(85, 55), droop=0.5, cup=0.4,
                        spoon=True) for i in range(3)]
    straw = [rosette_mesh(f"straw{i}", 60 + i, n=11, L=(0.08, 0.13), W=0.85, tilt=(65, 25), droop=0.9,
                          cup=0.2, berries=7, flowers=3) for i in range(3)]
    basil = [rosette_mesh(f"basil{i}", 80 + i, n=26, L=(0.03, 0.06), W=0.6, tilt=(70, 35), droop=0.5,
                          cup=0.5, z0=0.0) for i in range(3)]
    small = [rosette_mesh(f"small{i}", 90 + i, n=12, L=(0.05, 0.11), W=0.6, tilt=(80, 20), droop=0.9,
                          cup=0.3, ruffle=0.01) for i in range(3)]
    seedling = rosette_mesh("seedling", 99, n=4, L=(0.02, 0.03), W=0.7, tilt=(60, 40), droop=0.3, cup=0.2)
    for me in lettuce + small:
        me.materials.append(M["leaf_lettuce"])
    for me in red:
        me.materials.append(M["leaf_red"])
    for me in bok:
        me.materials.append(M["leaf_bokchoy"])
    for me in straw:
        for m in ("leaf_dark", "berry", "flower_white"):
            me.materials.append(M[m])
    for me in basil:
        me.materials.append(M["leaf_basil"])
    seedling.materials.append(M["leaf_seedling"])
    small_red = [rosette_mesh(f"smallred{i}", 95 + i, n=12, L=(0.05, 0.11), W=0.5, tilt=(80, 20), droop=0.8,
                              ruffle=0.014, rfreq=9) for i in range(2)]
    for me in small_red:
        me.materials.append(M["leaf_red"])

    # ---- class raised beds (east side, along the aisle)
    beds = MB()
    soil = MB()
    labels = []
    crops = [(lettuce, 1.35, "一年级 · 生菜"), (straw, 1.25, "二年级 · 草莓"), (bok, 1.0, "三年级 · 小白菜"),
             (red, 1.3, "四年级 · 紫叶生菜")]
    for k, (u0, u1) in enumerate([(0.9, 2.5), (2.7, 4.3), (4.5, 6.1), (6.3, 7.9)]):
        v0, v1 = 3.75, 4.95
        x0, y0, _ = L2W(u0, v0)
        x1, y1, _ = L2W(u1, v1)
        hb = 0.68
        n_pl = 5
        for p in range(n_pl):
            z0 = 0.0 + p * hb / n_pl
            r = rnd.random()
            beds.box(x0, x1, y0, y0 + 0.04, z0 + 0.004, z0 + hb / n_pl, r)
            beds.box(x0, x1, y1 - 0.04, y1, z0 + 0.004, z0 + hb / n_pl, r)
            beds.box(x0, x0 + 0.04, y0, y1, z0 + 0.004, z0 + hb / n_pl, r)
            beds.box(x1 - 0.04, x1, y0, y1, z0 + 0.004, z0 + hb / n_pl, r)
        beds.box(x0 - 0.02, x1 + 0.02, y0 - 0.02, y0 + 0.06, hb, hb + 0.03)
        beds.box(x0 - 0.02, x1 + 0.02, y1 - 0.06, y1 + 0.02, hb, hb + 0.03)
        beds.box(x0 - 0.02, x0 + 0.06, y0, y1, hb, hb + 0.03)
        beds.box(x1 - 0.06, x1 + 0.02, y0, y1, hb, hb + 0.03)
        soil.box(x0 + 0.04, x1 - 0.04, y0 + 0.04, y1 - 0.04, hb - 0.3, hb - 0.06)
        meshes, sc, label = crops[k]
        nx, ny = 4, 6
        for a in range(nx):
            for b in range(ny):
                px = x0 + 0.17 + a * (x1 - x0 - 0.34) / (nx - 1) + rnd.uniform(-0.03, 0.03)
                py = y0 + 0.16 + b * (y1 - y0 - 0.32) / (ny - 1) + rnd.uniform(-0.03, 0.03)
                instance(rnd.choice(meshes), "plant", (px, py, hb - 0.06), (0, 0, rnd.uniform(0, 6.3)),
                         sc * rnd.uniform(0.85, 1.15), coll)
        # class label plate on the aisle side
        labels.append((x0 - 0.025, (y0 + y1) / 2, label))
    beds.build("raised_beds", "wpc_dark_y", coll=coll, bevel=0.004)
    soil.build("bed_soil", "soil", coll=coll)
    plates = MB()
    for (lx, ly, label) in labels:
        plates.box(lx - 0.012, lx, ly - 0.24, ly + 0.24, 0.42, 0.56)
        text(label, CJK_FONT, 0.05, (lx - 0.016, ly, 0.49), (math.radians(90), 0, math.radians(-90)), "black",
             0.002, coll=coll)
    plates.build("bed_plates", "white_plastic", coll=coll, bevel=0.002)

    # ---- vertical aeroponic towers (west, front half)
    tw = MB()
    tw_base = MB()
    pockets = MB()
    for (u, v) in [(1.2, 0.6), (1.2, 1.45), (2.15, 0.6), (2.15, 1.45), (3.1, 0.6), (3.1, 1.45)]:
        cx, cy, _ = L2W(u, v)
        tw_base.tube((cx, cy, DECK), (cx, cy, DECK + 0.38), 0.3, 24)
        tw.tube((cx, cy, DECK + 0.38), (cx, cy, 2.05), 0.11, 20)
        tw.tube((cx, cy, 2.05), (cx, cy, 2.12), 0.13, 20)
        meshes = small if (u + v) % 2 < 1 else small + small_red
        for ring in range(7):
            z = 0.62 + ring * 0.205
            for k in range(5):
                az = k * 2 * math.pi / 5 + (ring % 2) * math.pi / 5 + v
                ox, oy = math.cos(az), math.sin(az)
                p0 = (cx + ox * 0.08, cy + oy * 0.08, z)
                p1 = (cx + ox * 0.17, cy + oy * 0.17, z + 0.07)
                pockets.tube(p0, p1, 0.035, 8)
                instance(rnd.choice(meshes), "tplant", p1, (0, math.radians(50), az), rnd.uniform(0.75, 1.0), coll)
    tw.build("towers", "pvc_white", smooth=True, coll=coll)
    tw_base.build("tower_tanks", "frame_dark", smooth=True, coll=coll)
    pockets.build("tower_pockets", "pvc_white", smooth=True, coll=coll)

    # ---- NFT A-frame hydroponic racks (west, back half)
    af = MB()
    pipes = MB()
    for (u0, u1) in [(3.9, 5.6), (5.9, 7.6)]:
        vc = 1.05
        for u in (u0 + 0.05, (u0 + u1) / 2, u1 - 0.05):
            x, y, _ = L2W(u, vc)
            for s in (-1, 1):
                af.beam((x + s * 0.62, y, DECK), (x + s * 0.08, y, 1.7), 0.04, 0.04)
            af.box(x - 0.6, x + 0.6, y - 0.02, y + 0.02, 0.3, 0.34)
        for s in (-1, 1):
            for k in range(4):
                h = 0.42 + k * 0.36
                off = 0.62 - (h - DECK) / (1.7 - DECK) * 0.54
                x, y0, _ = L2W(u0, vc)
                _, y1, _ = L2W(u1, vc)
                px = x + s * (off + 0.03)
                pipes.box(px - 0.05, px + 0.05, y0 - 0.06, y1 + 0.06, h, h + 0.06)
                y = y0 + 0.12
                while y < y1 - 0.05:
                    meshes = lettuce if k % 2 else bok
                    instance(rnd.choice(meshes if rnd.random() < 0.8 else red), "nplant", (px, y, h + 0.06),
                             (0, 0, rnd.uniform(0, 6.3)), rnd.uniform(0.55, 0.75), coll)
                    y += 0.21
        x, y0, _ = L2W(u0, vc)
        _, y1, _ = L2W(u1, vc)
        af.box(x - 0.3, x + 0.3, y0 + 0.15, y1 - 0.15, DECK, DECK + 0.22)
    af.build("aframe", "steel_brushed", coll=coll)
    pipes.build("nft_pipes", "pvc_white", coll=coll, bevel=0.01)

    # ---- back wall: smart screen, fertigation unit, seedling rack
    sx, sy, _ = L2W(8.72, 2.8)
    st = MB()
    st.box(sx - 0.7, sx + 0.7, sy - 0.25, sy + 0.25, DECK, DECK + 0.03)
    st.box(sx - 0.05, sx + 0.05, sy - 0.05, sy + 0.05, DECK, 1.5)
    st.box(sx - 0.7, sx + 0.7, sy - 0.05, sy + 0.01, 1.02, 1.82)
    st.build("screen_stand", "black", coll=coll, bevel=0.006)
    plane_uv("screen", (sx, sy - 0.052, 1.42), (1.36, 0.765), (math.radians(90), 0, 0), "screen", coll)
    # teaching table in front of the screen
    tb = MB()
    tx, ty, _ = L2W(7.95, 2.8)
    tb.box(tx - 0.75, tx + 0.75, ty - 0.3, ty + 0.3, 0.86, 0.9)
    for ox in (-0.7, 0.7):
        tb.box(tx + ox - 0.025, tx + ox + 0.025, ty - 0.27, ty + 0.27, DECK, 0.86)
    tb.build("teach_table", "wpc_x", coll=coll, bevel=0.004)
    for k in range(3):
        instance(rnd.choice(basil), "potted", (tx - 0.45 + k * 0.45, ty, 0.95), (0, 0, k), 2.0, coll)
    pots = MB()
    for k in range(3):
        pots.tube((tx - 0.45 + k * 0.45, ty, 0.9), (tx - 0.45 + k * 0.45, ty, 1.0), 0.07, 16, r1=0.085)
    pots.build("pots", "white_plastic", smooth=True, coll=coll)

    # fertigation (水肥一体机) in the NE corner
    fx, fy, _ = L2W(8.55, 4.6)
    fu = MB()
    fu.box(fx - 0.35, fx + 0.35, fy - 0.25, fy + 0.25, DECK, 1.55)
    fu.build("fertigation", "white_plastic", coll=coll, bevel=0.01)
    pn = MB()
    pn.box(fx - 0.2, fx + 0.2, fy - 0.252, fy - 0.248, 1.05, 1.35)
    pn.build("fert_panel", "black_gloss", coll=coll)
    tk = MB()
    for k, ox in enumerate((-0.9, -0.45)):
        tk.tube((fx + ox + 0.05, fy, DECK), (fx + ox + 0.05, fy, 0.9), 0.19, 24)
    tk.build("tanks", "tank_blue", smooth=True, coll=coll)

    # seedling rack with purple grow lights in the NW corner
    rx, ry, _ = L2W(8.55, 1.0)
    rk = MB()
    lights = MB()
    trays = MB()
    for ox in (-0.65, 0.65):
        for oy in (-0.22, 0.22):
            rk.box(rx + ox - 0.015, rx + ox + 0.015, ry + oy - 0.015, ry + oy + 0.015, DECK, 1.9)
    for z in (0.45, 0.95, 1.45):
        rk.box(rx - 0.67, rx + 0.67, ry - 0.24, ry + 0.24, z, z + 0.02)
        trays.box(rx - 0.6, rx + 0.6, ry - 0.2, ry + 0.2, z + 0.02, z + 0.06)
        for k in range(3):
            lights.box(rx - 0.6, rx + 0.6, ry - 0.15 + k * 0.15, ry - 0.13 + k * 0.15, z + 0.43, z + 0.44)
        for a in range(10):
            for b in range(3):
                instance(seedling, "sd", (rx - 0.54 + a * 0.12, ry - 0.13 + b * 0.13, z + 0.06),
                         (0, 0, rnd.uniform(0, 6)), rnd.uniform(1.0, 1.6), coll)
    rk.build("seed_rack", "steel_brushed", coll=coll)
    lights.build("seed_leds", "led_purple", coll=coll)
    trays.build("seed_trays", "black", coll=coll)

    # ---- overhead: grow-light bars, misting lines, fans, sensors, cameras
    ov = MB()
    led = MB()
    mist = MB()
    for v in (1.05, 4.35):
        for k in range(6):
            u0 = 1.0 + k * 1.15
            x, y0, _ = L2W(u0, v)
            _, y1, _ = L2W(u0 + 1.0, v)
            ov.box(x - 0.04, x + 0.04, y0, y1, 2.42, 2.47)
            led.box(x - 0.03, x + 0.03, y0 + 0.02, y1 - 0.02, 2.415, 2.42)
            for yy in (y0 + 0.1, y1 - 0.1):
                mist.tube((x, yy, 2.47), (x, yy, EH - 0.05), 0.003, 4)
        x, y0, _ = L2W(0.3, v)
        _, y1, _ = L2W(8.7, v)
        mist.tube((x, y0, 2.62), (x, y1, 2.62), 0.012, 8)
        y = y0 + 0.3
        while y < y1:
            mist.tube((x, y, 2.62), (x, y, 2.56), 0.008, 6)
            y += 0.6
    ov.build("led_bars", "black", coll=coll)
    led.build("led_emit", "led_grow", coll=coll)
    mist.build("misting", "steel", smooth=True, coll=coll)
    sens = MB()
    for k in range(4):
        x, y, _ = L2W(1.7 + k * 1.8, 4.35)
        sens.tube((x, y, 0.62), (x, y, 1.05), 0.008, 6)
        sens.box(x - 0.04, x + 0.04, y - 0.03, y + 0.03, 1.05, 1.17)
    x, y, _ = L2W(4.5, 2.8)
    sens.tube((x, y, RH), (x, y, 2.35), 0.006, 6)
    for k in range(6):
        sens.box(x - 0.1 + k * 0.004, x + 0.1 - k * 0.004, y - 0.1 + k * 0.004, y + 0.1 - k * 0.004,
                 2.05 + k * 0.05, 2.08 + k * 0.05)
    for (u, v) in ((0.2, 0.2), (8.8, 5.4)):
        x, y, _ = L2W(u, v)
        sens.tube((x, y, EH - 0.05), (x, y, EH - 0.15), 0.06, 16)
    sens.build("sensors", "white_plastic", smooth=False, coll=coll, bevel=0.003)
    # interior area lights (only meaningful at dusk; low at day)
    for u in (2.0, 4.5, 7.0):
        for v in (1.4, 4.2):
            ld = bpy.data.lights.new("int", "AREA")
            ld.shape = "RECTANGLE"
            ld.size, ld.size_y = 0.3, 1.6
            ld.energy = 380 if NIGHT else 0
            ld.color = (1.0, 0.86, 0.72)
            lo = bpy.data.objects.new("int_light", ld)
            lo.location = L2W(u, v, 2.38)
            link(lo, coll)


# ---------------------------------------------------------------- world, sun, render
def build_world(sun_elev, sun_azimuth, strength, sun_strength, sun_color, clouds=True):
    scene = bpy.context.scene
    w = bpy.data.worlds.new("sky")
    w.use_nodes = True
    scene.world = w
    nb = NB(w)
    bg = nb.nodes["Background"]
    sky = nb.n("ShaderNodeTexSky", sky_type="MULTIPLE_SCATTERING", sun_disc=False,
               sun_elevation=math.radians(sun_elev), sun_rotation=math.radians(sun_azimuth))
    sky.air_density = 1.0
    sky.aerosol_density = 0.6 if not NIGHT else 1.5
    col = sky.outputs["Color"]
    if clouds:
        tc = nb.n("ShaderNodeTexCoord")
        sp = nb.n("ShaderNodeSeparateXYZ")
        nb.l(tc.outputs["Generated"], sp.inputs[0])
        zc = nb.math("MAXIMUM", sp.outputs[2], 0.02)
        proj = nb.n("ShaderNodeCombineXYZ")
        nb.l(nb.math("DIVIDE", sp.outputs[0], zc), proj.inputs[0])
        nb.l(nb.math("DIVIDE", sp.outputs[1], zc), proj.inputs[1])
        n = nb.noise(proj.outputs[0], 0.35, 8, 0.62)
        mr = nb.n("ShaderNodeMapRange", in_From_Min=0.52, in_From_Max=0.72)
        nb.l(n, mr.inputs["Value"])
        horizon = nb.n("ShaderNodeMapRange", in_From_Min=0.0, in_From_Max=0.25)
        nb.l(sp.outputs[2], horizon.inputs["Value"])
        mask = nb.math("MULTIPLY", mr.outputs[0], horizon.outputs[0])
        cloud_col = (0.42, 0.42, 0.44) if not NIGHT else (0.06, 0.035, 0.04)
        col = nb.mix_rgb(nb.math("MULTIPLY", mask, 0.85), col, cloud_col)
    nb.l(col, bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    # separate sun lamp (cleaner than sampling the sky's sun)
    ld = bpy.data.lights.new("sun", "SUN")
    ld.energy = sun_strength
    ld.angle = math.radians(1.2)
    ld.color = sun_color
    lo = bpy.data.objects.new("sun", ld)
    el, az = math.radians(sun_elev), math.radians(sun_azimuth)
    to_sun = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
    lo.rotation_euler = (-to_sun).to_track_quat("-Z", "Y").to_euler()
    link(lo)


def add_camera(name, loc, target, lens, shift=(0.0, 0.0), level=True, ortho=None):
    cam = bpy.data.cameras.new(name)
    cam.sensor_width = 36
    cam.lens = lens
    cam.clip_start = 0.05
    cam.clip_end = 3000
    cam.shift_x, cam.shift_y = shift
    if ortho:
        cam.type = "ORTHO"
        cam.ortho_scale = ortho
    ob = bpy.data.objects.new(name, cam)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    if level:
        d.z = 0
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    link(ob)
    return ob


PLAN_C, PLAN_SCALE = (1.85, 1.95), 15.6     # plan view centre + ortho width (m); used by annotate.py

CAMERAS = {
    # name: (location, target, lens, shift, keep verticals)
    "hero": ((2.0, -6.35, CORR_Z + 1.6), (2.0, 3.0, 1.9), 16.0, (0.0, 0.06), True),
    "terrace_e": ((8.3, -4.5, 1.6), (1.4, 2.6, 1.7), 18.0, (0.0, 0.1), True),
    "terrace": ((-4.3, -4.45, 1.55), (3.6, 2.4, 1.6), 18.0, (0.0, 0.12), True),
    "aerial": ((-13.0, 17.0, 15.0), (2.6, 1.5, 0.5), 30.0, (0.0, 0.0), False),
    "interior": ((GXC + 0.35, GY0 + 0.35, 1.45), (GXC - 0.1, GY0 + GL, 1.45), 15.0, (0.0, 0.05), True),
    "dusk": ((-4.3, -4.45, 1.55), (3.6, 2.4, 1.6), 18.0, (0.0, 0.12), True),
    "hero_dusk": ((2.0, -6.35, CORR_Z + 1.6), (2.0, 3.0, 1.9), 16.0, (0.0, 0.06), True),
    "plan": ((PLAN_C[0], PLAN_C[1], 30.0), (PLAN_C[0], PLAN_C[1] + 0.0001, 0.0), 50.0, (0.0, 0.0), False),
}


def setup_render(res, samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.max_bounces = 8
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 6
    sc.cycles.transparent_max_bounces = 32
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.sample_clamp_indirect = 8.0
    sc.cycles.blur_glossy = 1.0
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.render.threads_mode = "AUTO"


def main():
    global ARGS, NIGHT, HAZE_STRENGTH, HAZE_COLOR
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--time", default="day", choices=["day", "dusk"])
    ap.add_argument("--shots", default="hero")
    ap.add_argument("--res", default="960x640")
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--out", default=os.path.join(HERE, "renders"))
    ap.add_argument("--suffix", default="")
    ap.add_argument("--save-blend", action="store_true")
    ap.add_argument("--sun-elev", type=float, default=None)
    ap.add_argument("--sky", type=float, default=None)
    ap.add_argument("--sun-az", type=float, default=None)
    ap.add_argument("--exposure", type=float, default=None)
    ARGS = ap.parse_args(argv)
    NIGHT = ARGS.time == "dusk"
    if NIGHT:
        HAZE_STRENGTH, HAZE_COLOR = 0.12, (0.55, 0.42, 0.45)
    t0 = time.time()
    random.seed(1)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    make_materials()
    build_site()
    build_landscape()
    roof_coll = build_greenhouse()
    build_interior()
    if NIGHT:
        el = -3.0 if ARGS.sun_elev is None else ARGS.sun_elev
        build_world(el, 35.0, 1.0 if ARGS.sky is None else ARGS.sky, 0.0, (1.0, 0.55, 0.30))
    else:
        el = 38.0 if ARGS.sun_elev is None else ARGS.sun_elev
        az = 215.0 if ARGS.sun_az is None else ARGS.sun_az
        build_world(el, az, 0.32 if ARGS.sky is None else ARGS.sky, 4.2, (1.0, 0.95, 0.88))
    res = tuple(int(v) for v in ARGS.res.split("x"))
    setup_render(res, ARGS.samples)
    sc = bpy.context.scene
    sc.view_settings.exposure = ARGS.exposure if ARGS.exposure is not None else (1.6 if NIGHT else 0.0)
    print(f"scene built in {time.time() - t0:.1f}s, objects={len(bpy.data.objects)}")
    if ARGS.save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ARGS.out, f"smart_farm_{ARGS.time}.blend"))
    os.makedirs(ARGS.out, exist_ok=True)
    for shot in ARGS.shots.split(","):
        loc, tgt, lens, shift, level = CAMERAS[shot]
        cam = add_camera(shot, loc, tgt, lens, shift, level, ortho=PLAN_SCALE if shot == "plan" else None)
        sc.camera = cam
        roof_coll.hide_render = shot == "plan"
        bpy.data.collections["context"].hide_render = shot == "plan"
        sc.render.filepath = os.path.join(ARGS.out, f"{shot}{ARGS.suffix}.png")
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"rendered {shot} in {time.time() - t1:.1f}s -> {sc.render.filepath}")


if __name__ == "__main__":
    main()
