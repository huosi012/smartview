"""Render potted-plant sprites (transparent PNG) for the louver-corner photo edit."""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import scene as S  # noqa: E402
from scene import M, MB, instance, link, rosette_mesh  # noqa: E402

OUT = os.path.join(HERE, "tex", "pots")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    S.make_materials()
    m, nb, b = S.new_mat("terracotta")
    S.set_bsdf(b, (0.45, 0.17, 0.08), 0.6)
    M["terracotta"] = m
    m, nb, b = S.new_mat("ceramic")
    S.set_bsdf(b, (0.82, 0.82, 0.8), 0.2, spec=0.7)
    M["ceramic"] = m
    m, nb, b = S.new_mat("ceramic_g")
    S.set_bsdf(b, (0.12, 0.22, 0.17), 0.25, spec=0.7)
    M["ceramic_g"] = m
    variants = [
        dict(plant=dict(n=24, L=(0.04, 0.09), W=0.5, tilt=(80, 30), droop=0.4, cup=0.5), leaf="leaf_basil", pot="terracotta", sc=1.0),
        dict(plant=dict(n=14, L=(0.05, 0.1), W=0.6, tilt=(70, 20), droop=0.8, cup=0.3, flowers=0), leaf="leaf_dark", pot="ceramic", sc=1.0, fl="flower_red"),
        dict(plant=dict(n=18, L=(0.04, 0.07), W=0.9, tilt=(60, 30), droop=0.2, cup=0.6), leaf="leaf_lettuce", pot="ceramic_g", sc=0.9),
        dict(plant=dict(n=22, L=(0.1, 0.2), W=0.3, tilt=(70, 10), droop=1.4, cup=0.1, ruffle=0.006, rfreq=12), leaf="leaf_palm", pot="ceramic", sc=1.0),
        dict(plant=dict(n=12, L=(0.05, 0.1), W=0.6, tilt=(70, 25), droop=0.7, cup=0.3, flowers=0), leaf="leaf_dark", pot="terracotta", sc=1.0, fl="flower_yellow"),
        dict(plant=dict(n=16, L=(0.06, 0.13), W=0.62, tilt=(80, 12), droop=0.9, cup=0.3, ruffle=0.012, rfreq=7), leaf="leaf_lettuce", pot="ceramic_g", sc=0.9),
    ]
    sc = bpy.context.scene
    S.setup_render((420, 420), 64)
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    sc.world = w
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.9, 0.9, 0.9, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    ld = bpy.data.lights.new("k", "AREA")
    ld.size = 0.6
    ld.energy = 12
    lo = bpy.data.objects.new("k", ld)
    lo.location = (0.3, -0.5, 0.8)
    lo.rotation_euler = (math.radians(45), 0, math.radians(30))
    link(lo)
    cam = bpy.data.cameras.new("c")
    cam.type = "ORTHO"
    cam.ortho_scale = 0.42
    co = bpy.data.objects.new("c", cam)
    co.location = (0, -2.0, 0.55)
    co.rotation_euler = (math.radians(78), 0, 0)
    link(co)
    sc.camera = co
    os.makedirs(OUT, exist_ok=True)
    for i, v in enumerate(variants):
        for ob in list(bpy.data.objects):
            if ob.name.startswith("pv"):
                bpy.data.objects.remove(ob)
        pot = MB()
        pot.tube((0, 0, 0.0), (0, 0, 0.11), 0.055, 28, r1=0.07)
        po = pot.build("pv_pot", v["pot"], smooth=True)
        soil = MB()
        soil.disc((0, 0, 0.1), 0.066, 1, 24)
        soil.build("pv_soil", "soil")
        me = rosette_mesh(f"pv_me{i}", 200 + i, **v["plant"])
        me.materials.append(M[v["leaf"]])
        me.materials.append(M[v["leaf"]])
        me.materials.append(M[v.get("fl", "flower_white")])
        ob = bpy.data.objects.new("pv_plant", me)
        ob.location = (0, 0, 0.1)
        ob.scale = (v["sc"] * 1.25,) * 3
        link(ob)
        sc.render.filepath = os.path.join(OUT, f"pot{i}.png")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
