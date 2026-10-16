"""链轮轴测着色图 (光线步进渲染隐式实体, 输出带透明背景的 PNG)."""
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sprocket_geom as sg  # noqa: E402
import spline_geom as spg  # noqa: E402
from cad_common import sample_bulge_polyline  # noqa: E402

# 轴向尺寸 (左端面 z=0)
L_HUB = 110.5
X_RIM_L, X_RIM_R = L_HUB - 19.0 - 50.67, L_HUB - 19.0
X_WEB_L, X_WEB_R = X_RIM_L + 3.0, L_HUB - 20.0
HOLES = [(190.0 * math.cos(math.radians(a)), 190.0 * math.sin(math.radians(a)))
         for a in (90, 210, 330)]


def _radial_table(verts):
    pts = np.array(sample_bulge_polyline(verts, closed=True, max_step=0.3))
    th = np.arctan2(pts[:, 1], pts[:, 0])
    r = np.hypot(pts[:, 0], pts[:, 1])
    o = np.argsort(th)
    th, r = th[o], r[o]
    th = np.concatenate([th - 2 * np.pi, th, th + 2 * np.pi])
    r = np.concatenate([r, r, r])
    return th, r


TH_OUT, R_OUT = _radial_table(sg.full_profile())
TH_SPL, R_SPL = _radial_table(spg.full_profile())


def inside(p):
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    r = np.hypot(x, y)
    th = np.arctan2(y, x)
    # 内孔: 花键 + 两端倒角/退刀槽
    rb = np.interp(th, TH_SPL, R_SPL)
    rb = np.maximum(rb, spg.R_MINOR + 4.0 - z)
    rb = np.where(z >= L_HUB - 10.0, 111.0, np.maximum(rb, spg.R_MINOR + (z - (L_HUB - 14.0))))
    ok = (z >= 0) & (z <= L_HUB) & (r >= rb)
    # 轮毂外径
    r_hub = np.where(z < 10, 145.0, np.where(z < 17, 145.0 + (z - 10) * 5 / 7, 150.0))
    r_hub = np.where(z > X_WEB_R, 145.0, r_hub)
    hub = r <= r_hub
    web = (z >= X_WEB_L) & (z <= X_WEB_R) & (r <= 240.0)
    # 齿圈 + 齿侧倒角
    r_lim = np.full_like(r, sg.R_A)
    for face, sgn in ((X_RIM_L, 1), (X_RIM_R, -1)):
        u = (z - face) * sgn
        cx = sg.RX - u
        lim = sg.R_CHAMFER_START + np.sqrt(np.clip(sg.RX ** 2 - cx ** 2, 0, None))
        r_lim = np.where((u >= 0) & (u < sg.BA), np.minimum(r_lim, lim), r_lim)
    rim = (z >= X_RIM_L) & (z <= X_RIM_R) & (r >= 236.0) & (r <= np.minimum(
        np.interp(th, TH_OUT, R_OUT), r_lim))
    solid = ok & (hub | web | rim)
    for hx, hy in HOLES:
        solid &= ~(((x - hx) ** 2 + (y - hy) ** 2 < 32.0 ** 2) & (r > 150.0))
    return solid


def render(path, size=(640, 700), az=-38.0, el=22.0, half=390.0):
    """az/el: 观察方向 (度). 输出 RGBA PNG."""
    W, H = size
    a, e = math.radians(az), math.radians(el)
    # 视线方向 (由相机指向物体), 朝 +z 看到左端面
    f = np.array([math.sin(a) * math.cos(e), -math.sin(e), math.cos(a) * math.cos(e)])
    f /= np.linalg.norm(f)
    up0 = np.array([0.0, 1.0, 0.0])
    rgt = np.cross(up0, f)
    rgt /= np.linalg.norm(rgt)
    up = np.cross(f, rgt)
    ctr = np.array([0.0, 0.0, L_HUB / 2])
    pix = 2 * half / H
    us = (np.arange(W) - W / 2 + 0.5) * pix
    vs = (H / 2 - np.arange(H) - 0.5) * pix
    U, V = np.meshgrid(us, vs)
    origin = ctr + U[..., None] * (-rgt) + V[..., None] * up - f * 420.0
    origin = origin.reshape(-1, 3)
    step = 1.2
    n_steps = int(840 / step)
    t_hit = np.full(origin.shape[0], np.nan)
    active = np.arange(origin.shape[0])
    for i in range(n_steps):
        t = i * step
        pts = origin[active] + f * t
        hit = inside(pts)
        if hit.any():
            idx = active[hit]
            lo = np.full(idx.size, t - step)
            hi = np.full(idx.size, t)
            for _ in range(8):
                mid = (lo + hi) / 2
                m = inside(origin[idx] + f * mid[:, None])
                hi = np.where(m, mid, hi)
                lo = np.where(m, lo, mid)
            t_hit[idx] = hi
            active = active[~hit]
        if active.size == 0:
            break
    depth = t_hit.reshape(H, W)
    mask = ~np.isnan(depth)
    P = origin.reshape(H, W, 3) + f * np.nan_to_num(depth)[..., None]
    du = np.gradient(P, axis=1)
    dv = np.gradient(P, axis=0)
    n = np.cross(du, dv)
    n /= np.linalg.norm(n, axis=2, keepdims=True) + 1e-9
    n = np.where((n @ f)[..., None] > 0, -n, n)
    light = -f + np.array([0.35, 0.55, 0.0])
    light /= np.linalg.norm(light)
    shade = 0.32 + 0.68 * np.clip(n @ light, 0, 1)
    # 轮廓线: 深度跳变 / 法向突变
    d = np.nan_to_num(depth, nan=1e4)
    edge = np.zeros_like(mask)
    for ax in (0, 1):
        dd = np.abs(np.diff(d, axis=ax))
        nn = np.sum(np.diff(n, axis=ax) ** 2, axis=2)
        e1 = (dd > 6.0) | (nn > 0.08)
        if ax == 0:
            edge[1:, :] |= e1
        else:
            edge[:, 1:] |= e1
    gray = np.where(edge, 0.12, shade)
    rgb = np.stack([gray * 0.86, gray * 0.90, gray * 0.96], axis=2)
    alpha = np.where(mask | edge & (d < 1e4), 1.0, 0.0)
    img = np.dstack([rgb, alpha])
    ys, xs = np.nonzero(alpha)
    m = 4
    img = img[max(ys.min() - m, 0):ys.max() + m + 1, max(xs.min() - m, 0):xs.max() + m + 1]
    out = Image.fromarray((img * 255).astype(np.uint8), "RGBA")
    out.save(path)
    return out.size


if __name__ == "__main__":
    print(render(os.path.join(os.path.dirname(os.path.abspath(__file__)), "iso_test.png")))
