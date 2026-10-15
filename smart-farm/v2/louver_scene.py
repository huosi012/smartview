"""3D layer for the corridor-end louver photo (photos/p_louver.jpg).

Client note on the louvers: "外面用玻璃封起来，里面装上灯带，做盆栽植物观察" -- glass on the outer face,
LED strips under the fins on the corridor side, potted plants on the fins.

The walls and fins are modelled from calib_louver.json (camera solved on the photo, fin levels measured on it).
They are never seen; they only hide and light the added parts. louver_edit.py puts the passes onto the photo.

    python louver_scene.py [--samples 160] [--scale 1.0]
      -> renders/louver_beauty.png   plants, pots and LED strips (RGBA, walls held out)
         renders/louver_light.npy    relight factor for the photo: LED light and plant shadows (float16, HxWx4)
         renders/louver_glass.png    where the new glass is seen (alpha)
"""
import argparse
import json
import math
import os
import random
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scene_v2 as V  # noqa: E402  (puts the v1 helpers on sys.path)
import scene as S  # noqa: E402
from scene import M, MB, collection, instance, link  # noqa: E402

CAL = json.load(open(os.path.join(HERE, "calib_louver.json")))
G = CAL["geom"]
T, WC = G["T"], G["WC"]
LINTEL, SILL, CEIL = G["lintel"], G["sill"], G["ceiling"]
FINS = G["fins"]                                   # (underside, top) of each fin, top to bottom
SIDE = G["side_openings"]                          # x ranges of the openings in the side wall (y 0..T)
END = G["end_opening"]                             # y range of the opening in the end wall (x 0..T)
TIERS = [SILL] + [f[1] for f in FINS[1:]][::-1]    # plant shelves: sill, fin 4, fin 3, fin 2
LED_Z = [f[0] for f in FINS]                       # strips under fins 1-4, each lighting the shelf below
OUT = os.path.join(HERE, "renders")


def camera():
    c = CAL["cam"]
    rv = np.array(c["rv"], float)
    th = np.linalg.norm(rv)
    k = rv / th
    Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    R = np.eye(3) + math.sin(th) * Kx + (1 - math.cos(th)) * Kx @ Kx
    pos = -R.T @ np.array(c["tv"])
    R_bl = np.diag([1, -1, -1]) @ R
    w, h = c["size"]
    cam = bpy.data.cameras.new("p_louver")
    cam.sensor_fit = "HORIZONTAL"
    cam.sensor_width = 36
    cam.lens = c["f"] * 36 / w
    cam.clip_start = 0.05
    ob = bpy.data.objects.new("p_louver", cam)
    ob.matrix_world = Matrix.Translation(Vector(pos)) @ Matrix(R_bl.T.tolist()).to_4x4()
    link(ob)
    return ob, (w, h)


def materials(led_strength):
    for name, col, rough in (("pot_white", (0.80, 0.80, 0.78), 0.55), ("pot_sage", (0.36, 0.42, 0.36), 0.6),
                             ("led_alu", (0.75, 0.75, 0.74), 0.3)):
        m, nb, b = S.new_mat(name)
        S.set_bsdf(b, col, rough, 0.0 if name != "led_alu" else 1.0, 0.5)
        M[name] = m
    m, nb, b = S.new_mat("led_strip")
    S.set_bsdf(b, (1.0, 0.9, 0.75), 0.4)
    b.inputs["Emission Color"].default_value = (1.0, 0.72, 0.42, 1)
    b.inputs["Emission Strength"].default_value = led_strength
    M["led_strip"] = m
    m, nb, b = S.new_mat("mask_white")
    b.inputs["Emission Color"].default_value = (1, 1, 1, 1)
    b.inputs["Emission Strength"].default_value = 1.0
    M["mask_white"] = m


def walls():
    """Side wall, end wall and fins (white); the corridor around them is a separate object."""
    mb, cor = MB(), MB()
    (a0, a1), (b0, b1) = SIDE
    e0, _ = END
    XN = -9.0
    mb.box(XN, a0, 0, T, 0, CEIL)                     # side wall up to the openings
    mb.box(a0, T, 0, T, 0, SILL)                      # below the sill
    mb.box(a0, T, 0, T, LINTEL, CEIL)                 # above the openings
    mb.box(a1, b0, 0, T, SILL, LINTEL)                # pier between the two side openings
    mb.box(0, T, -WC - 0.3, e0, 0, CEIL)              # end wall jamb on the classroom side
    mb.box(0, T, e0, T, 0, SILL)
    mb.box(0, T, e0, T, LINTEL, CEIL)
    for z0, z1 in FINS:
        mb.box(a0, a1, 0, T, z0, z1)
        mb.box(b0, T, 0, T, z0, z1)
        mb.box(0, T, e0, T, z0, z1)
    cor.box(XN, T, -WC - 0.3, T, -0.1, 0.0)           # corridor floor
    cor.box(XN, T, -WC - 0.3, T, CEIL, CEIL + 0.1)    # corridor ceiling
    cor.box(XN, 0, -WC - 0.3, -WC, 0, CEIL)           # classroom wall
    return mb.build("louver_walls", "paint_white"), cor.build("corridor", "paint_white")


def glass():
    """Panes on the outer face of the louvers (only used for the mask pass)."""
    mb = MB()
    (a0, a1), (b0, b1) = SIDE
    e0, _ = END
    y = T + 0.002
    for x0, x1 in ((a0, a1), (b0, T)):
        mb.poly([(x0, y, SILL), (x1, y, SILL), (x1, y, LINTEL), (x0, y, LINTEL)])
    x = T + 0.002
    mb.poly([(x, e0, SILL), (x, T, SILL), (x, T, LINTEL), (x, e0, LINTEL)])
    return mb.build("louver_glass", "mask_white")


def leds():
    """Aluminium profile with a warm LED strip under each fin, on the corridor edge."""
    prof, strip = MB(), MB()
    (a0, a1), (b0, b1) = SIDE
    e0, _ = END
    for z in LED_Z:
        runs = [("x", a0 + 0.02, a1 - 0.02), ("x", b0 + 0.02, 0.035), ("y", e0 + 0.02, 0.02)]
        for axis, s0, s1 in runs:
            if axis == "x":
                prof.box(s0, s1, 0.015, 0.04, z - 0.012, z)
                strip.box(s0 + 0.005, s1 - 0.005, 0.02, 0.035, z - 0.014, z - 0.012)
            else:
                prof.box(0.015, 0.04, s0, s1, z - 0.012, z)
                strip.box(0.02, 0.035, s0 + 0.005, s1 - 0.005, z - 0.014, z - 0.012)
    return prof.build("led_profile", "led_alu"), strip.build("led_strip", "led_strip")


def fit(me, h, w):
    """Scale that makes a plant mesh at most h tall and w wide."""
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    return min(h / max(1e-3, max(zs) - min(zs)), w / max(1e-3, max(max(xs) - min(xs), max(ys) - min(ys))))


def plants(P):
    """Pots along each shelf; one crop per shelf so the window reads as a set of observation rows."""
    coll = collection("louver_plants")
    rnd = random.Random(7)
    pots, soil = MB(), MB()
    (a0, a1), (b0, b1) = SIDE
    e0, _ = END
    kinds = {SILL: ["straw"], TIERS[1]: ["lettuce", "red"], TIERS[2]: ["small", "red"], TIERS[3]: ["fern"]}
    for z in TIERS:
        clear = min([f[0] for f in FINS if f[0] > z] + [LINTEL]) - z
        ph = 0.085                                        # pot height
        hmax = clear - ph - 0.035                         # keep the leaves under the LED strip
        spots = []
        for x0, x1 in ((a0, a1), (b0, -0.12)):
            n = max(1, round((x1 - x0 - 0.1) / 0.25))
            spots += [(x0 + 0.05 + (k + 0.5) * (x1 - x0 - 0.1) / n, T / 2) for k in range(n)]
        n = round((-0.12 - e0 - 0.1) / 0.25)
        spots += [(T / 2, e0 + 0.05 + (k + 0.5) * (-0.12 - e0 - 0.1) / n) for k in range(n)]
        for i, (x, y) in enumerate(spots):
            r = 0.058
            pots.tube((x, y, z), (x, y, z + ph), r * 0.8, 20, r1=r)
            soil.disc((x, y, z + ph + 0.002), r * 0.9, normal_z=1, seg=20)
            kind = kinds[z][i % len(kinds[z])]
            src = P[kind][rnd.randrange(len(P[kind]))]
            sc = fit(src, hmax, 0.24 if kind != "fern" else 0.28) * rnd.uniform(0.9, 1.0)
            instance(src, "lp", (x, y, z + ph - 0.005), (0, 0, rnd.uniform(0, 6.28)), sc, coll)
    pots.build("louver_pots", "pot_white", smooth=True, coll=coll)
    soil.build("louver_soil", "soil", coll=coll)
    return coll


def world(strength):
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new("louver_world")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.92, 0.94, 0.97, 1)
    bg.inputs["Strength"].default_value = strength


def read_exr(path, w, h):
    im = bpy.data.images.load(path)
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)[::-1]


def render(path, samples, denoise=True):
    sc = bpy.context.scene
    sc.cycles.samples = samples
    sc.cycles.use_denoising = denoise
    sc.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"  {os.path.basename(path)} {time.time() - t:.0f}s", flush=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=160)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--led", type=float, default=14.0, help="LED strip emission strength")
    ap.add_argument("--exposure", type=float, default=0.0)
    ap.add_argument("--passes", default="beauty,light,glass")
    args = ap.parse_args(argv)
    random.seed(3)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    S.make_materials()
    materials(args.led)
    P = V.plant_meshes()
    wall_ob, cor_ob = walls()
    glass_ob = glass()
    prof_ob, strip_ob = leds()
    plant_coll = plants(P)
    cam, (w, h) = camera()
    sc = bpy.context.scene
    S.setup_render((int(w * args.scale), int(h * args.scale)), args.samples)
    sc.camera = cam
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = args.exposure
    W_, H_ = sc.render.resolution_x, sc.render.resolution_y
    passes = args.passes.split(",")
    os.makedirs(OUT, exist_ok=True)

    def state(walls_holdout, show_plants, plants_cam, show_led, led_cam, show_glass, world_strength):
        wall_ob.is_holdout = walls_holdout
        cor_ob.is_holdout = True              # only the louvers themselves get relit
        plant_coll.hide_render = not show_plants
        for ob in plant_coll.objects:
            ob.visible_camera = plants_cam
        for ob in (prof_ob, strip_ob):
            ob.hide_render = not show_led
            ob.visible_camera = led_cam
        glass_ob.hide_render = not show_glass
        world(world_strength)

    if "beauty" in passes:
        sc.render.image_settings.file_format = "PNG"
        sc.render.image_settings.color_mode = "RGBA"
        state(True, True, True, True, True, False, 1.0)
        render(os.path.join(OUT, "louver_beauty.png"), args.samples)
    if "light" in passes:
        sc.render.image_settings.file_format = "OPEN_EXR"
        sc.render.image_settings.color_mode = "RGBA"
        lit, base = os.path.join(OUT, "louver_lit.exr"), os.path.join(OUT, "louver_base.exr")
        state(False, True, False, True, False, False, 1.0)
        render(lit, max(32, args.samples // 3))
        state(False, False, False, False, False, False, 1.0)
        render(base, max(32, args.samples // 3))
        a, b = read_exr(lit, W_, H_), read_exr(base, W_, H_)
        f = np.ones_like(a)
        ok = b[..., 3] > 0.5
        f[..., :3][ok] = np.clip(a[..., :3][ok] / np.maximum(b[..., :3][ok], 0.02), 0.5, 6.0)
        f[..., 3] = b[..., 3]
        np.save(os.path.join(OUT, "louver_light.npy"), f.astype(np.float16))
        os.remove(lit)
        os.remove(base)
    if "glass" in passes:
        sc.render.image_settings.file_format = "PNG"
        sc.render.image_settings.color_mode = "RGBA"
        state(True, False, False, False, False, True, 0.0)
        render(os.path.join(OUT, "louver_glass.png"), 4, denoise=False)


if __name__ == "__main__":
    main()
