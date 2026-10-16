"""链轮 2292-IH-000139 齿形几何: z=23, p=88.9, d1=53.98 (三圆弧一直线齿形, 尺寸按原图).

局部坐标: 链轮中心为原点, 齿槽中心在 +Y 方向, 滚子中心 O=(0, R_P).
  齿沟圆弧   R27.3   圆心 O
  工作段圆弧 R70.36  圆心 O + (∓34.21, +26.35)   (= 0.8·d1·(sinα, cosα), α=55°-60°/z)
  齿顶圆弧   R39.27  圆心 O + (±69.52, -9.56)    (= 1.3·d1·(cos, sin)(180°/z))
  工作段圆弧与齿顶圆弧之间为公切直线.
齿侧: 齿侧半径 R88.9 (=p), 齿侧倒角宽 11.56 (=0.13p), 与端面相切.
"""
import math

Z = 23
PITCH = 88.9
D1 = 53.98
D_P = PITCH / math.sin(math.pi / Z)     # 分度圆 652.88
R_P = D_P / 2
D_A = 694.8                              # 齿顶圆
R_A = D_A / 2
D_F = 598.89                             # 齿根圆 (标注值 d - d1)

R1 = 27.3                                # 齿沟圆弧
R2 = 70.36                               # 工作段圆弧
R3 = 39.27                               # 齿顶圆弧
C2_OFF = (34.21, 26.35)                  # 工作段圆弧圆心相对 O (另一侧为 -x)
C3_OFF = (69.52, -9.56)                  # 齿顶圆弧圆心相对 O

RIM_W = 50.67                            # 齿宽
BA = 11.56                               # 齿侧倒角
RX = 88.9                                # 齿侧半径
R_CHAMFER_START = R_A - math.sqrt(RX ** 2 - (RX - BA) ** 2)   # 齿侧圆弧与端面切点半径

PITCH_ANG = 2 * math.pi / Z


def _circle_intersections(c1, r1, c2, r2):
    dx, dy = c2[0] - c1[0], c2[1] - c1[1]
    d = math.hypot(dx, dy)
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(r1 * r1 - a * a, 0.0))
    mx, my = c1[0] + a * dx / d, c1[1] + a * dy / d
    return [(mx + h * dy / d, my - h * dx / d), (mx - h * dy / d, my + h * dx / d)]


def _bisect(f, lo, hi, n=100):
    flo = f(lo)
    for _ in range(n):
        mid = (lo + hi) / 2
        fm = f(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


def right_flank():
    """齿槽右侧齿廓的关键点 (局部坐标, x>0), 由齿沟到齿顶."""
    O = (0.0, R_P)
    c2 = (O[0] - C2_OFF[0], O[1] + C2_OFF[1])          # 右侧齿廓的工作段圆弧圆心在左上
    c3 = (O[0] + C3_OFF[0], O[1] + C3_OFF[1])
    # 齿沟圆弧与工作段圆弧的交点 (取更靠上的一个, 即两圆并集的边界)
    pts = [p for p in _circle_intersections(O, R1, c2, R2) if p[0] > 0]
    t1 = max(pts, key=lambda p: p[1])
    # 工作段圆弧上与齿顶圆弧的公切点
    th1 = math.atan2(t1[1] - c2[1], t1[0] - c2[0])

    def g(th):
        p = (c2[0] + R2 * math.cos(th), c2[1] + R2 * math.sin(th))
        u = (-math.sin(th), math.cos(th))
        v = (c3[0] - p[0], c3[1] - p[1])
        return abs(v[0] * u[1] - v[1] * u[0]) - R3

    th2 = _bisect(g, th1, 0.0)
    t2 = (c2[0] + R2 * math.cos(th2), c2[1] + R2 * math.sin(th2))
    u = (-math.sin(th2), math.cos(th2))
    s = (c3[0] - t2[0]) * u[0] + (c3[1] - t2[1]) * u[1]
    t3 = (t2[0] + s * u[0], t2[1] + s * u[1])
    # 齿顶圆弧与齿顶圆的交点
    a3 = math.atan2(t3[1] - c3[1], t3[0] - c3[0])
    a4 = _bisect(lambda a: math.hypot(c3[0] + R3 * math.cos(a), c3[1] + R3 * math.sin(a)) - R_A,
                 a3, math.pi / 2)
    t4 = (c3[0] + R3 * math.cos(a4), c3[1] + R3 * math.sin(a4))
    return dict(O=O, c2=c2, c3=c3, t1=t1, t2=t2, t3=t3, t4=t4,
                bottom=(0.0, R_P - R1))


def _rot(p, a):
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def _bulge(c, p1, p2):
    a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
    a2 = math.atan2(p2[1] - c[1], p2[0] - c[0])
    sw = a2 - a1
    while sw > math.pi:
        sw -= 2 * math.pi
    while sw <= -math.pi:
        sw += 2 * math.pi
    return math.tan(sw / 4)


def space_chain(phi):
    """齿槽 (中心角 phi) 的轮廓 [x, y, bulge], 逆时针: 右侧齿顶 → 齿沟 → 左侧齿顶."""
    f = right_flank()
    m = lambda p: (-p[0], p[1])           # noqa: E731  镜像到左侧
    a = phi - math.pi / 2
    R = lambda p: _rot(p, a)              # noqa: E731
    seq = [
        (f["t4"], f["c3"]), (f["t3"], None), (f["t2"], f["c2"]), (f["t1"], f["O"]),
        (m(f["t1"]), m(f["c2"])), (m(f["t2"]), None), (m(f["t3"]), m(f["c3"])), (m(f["t4"]), "tip"),
    ]
    out = []
    for i, (p, c) in enumerate(seq):
        b = 0.0
        if c is not None and c != "tip":
            b = _bulge(R(c), R(p), R(seq[i + 1][0]))
        out.append([*R(p), b])
    return out


def full_profile():
    """整圈链轮齿廓 (齿槽中心在 90°), 闭合多段线顶点."""
    verts = []
    for k in range(Z):
        phi = math.pi / 2 + k * PITCH_ANG
        ch = space_chain(phi)
        nxt = space_chain(phi + PITCH_ANG)[0]
        ch[-1][2] = _bulge((0.0, 0.0), ch[-1][:2], nxt[:2])
        verts.extend(ch)
    return verts


def flank_angle(r):
    """半径 r 处右侧齿廓点偏离齿槽中心线的角度 (rad, 顺时针为正)."""
    f = right_flank()
    O, c2, c3 = f["O"], f["c2"], f["c3"]

    def on_circle(c, rr):
        # 圆 (c, rr) 与半径 r 圆的交点中 x>0 且最接近齿槽的那个
        pts = [p for p in _circle_intersections((0.0, 0.0), r, c, rr) if p[0] > 0]
        return min(pts, key=lambda p: math.atan2(p[0], p[1])) if pts else None

    rb = R_P - R1
    r1, r2, r3, r4 = (math.hypot(*f[k]) for k in ("t1", "t2", "t3", "t4"))
    if r <= rb:
        return 0.0
    if r <= r1:
        p = on_circle(O, R1)
    elif r <= r2:
        p = on_circle(c2, R2)
    elif r <= r3:
        t2, t3 = f["t2"], f["t3"]
        s = _bisect(lambda s: math.hypot(t2[0] + s * (t3[0] - t2[0]),
                                         t2[1] + s * (t3[1] - t2[1])) - r, 0.0, 1.0)
        p = (t2[0] + s * (t3[0] - t2[0]), t2[1] + s * (t3[1] - t2[1]))
    else:
        pts = [q for q in _circle_intersections((0.0, 0.0), min(r, r4), c3, R3) if q[0] > 0]
        p = min(pts, key=lambda q: math.atan2(q[0], q[1]))
    return math.atan2(p[0], p[1])


def chamfer_r_limit(a, x_left, x_right):
    """齿侧倒角: 轴向位置 a 处轮齿允许的最大半径."""
    for face, sgn in ((x_left, 1), (x_right, -1)):
        u = (a - face) * sgn
        if u < BA:
            cx = RX - u
            return R_CHAMFER_START + math.sqrt(max(RX * RX - cx * cx, 0.0))
    return R_A


if __name__ == "__main__":
    f = right_flank()
    print(f"d={D_P:.3f}  df(槽底)={2 * (R_P - R1):.3f}  倒角起点 R={R_CHAMFER_START:.3f}")
    for k in ("t1", "t2", "t3", "t4"):
        p = f[k]
        print(k, f"({p[0]:.3f}, {p[1] - R_P:.3f}) r={math.hypot(*p):.3f}")
    half_tip = math.pi / Z - math.atan2(f["t4"][0], f["t4"][1])
    print(f"齿顶弧长 {2 * half_tip * R_A:.3f} mm")
    for r in (300, 310, 320, 330, 340, 347.4):
        print(r, round(math.degrees(flank_angle(r)), 3))
