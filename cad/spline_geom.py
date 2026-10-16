"""20°压力角渐开线内花键齿形几何计算 (Q/STB13.110.22, 齿形参照 JIS D2001; m=2.5, z=85, x=+0.8)."""
import math

M_MOD = 2.5          # 模数 m
Z = 85               # 齿数 z
ALPHA = math.radians(20.0)  # 压力角 α
X = 0.8              # 变位系数 x

D_PITCH = M_MOD * Z                      # 分度圆直径 d = 212.5
R_PITCH = D_PITCH / 2
D_BASE = D_PITCH * math.cos(ALPHA)       # 基圆直径 db = 199.685
R_BASE = D_BASE / 2

D_MAJOR = 218.25     # 内花键大径 D1 (H11)
D_MINOR = 212.5      # 内花键小径 d1 (H7)
R_MAJOR = D_MAJOR / 2
R_MINOR = D_MINOR / 2

R_ROOT_FILLET = 0.5  # 齿根圆角 R0.5
C_TIP = 0.2          # 齿顶倒角 C0.2

PIN_D = 5.0          # 量棒直径


def inv(a):
    return math.tan(a) - a


def ainv(v):
    """渐开线函数反函数 (牛顿迭代)."""
    a = (3 * v) ** (1 / 3)
    for _ in range(50):
        a -= (inv(a) - v) / math.tan(a) ** 2
    return a


# 分度圆理论齿槽宽 e = m(π/2 + 2x·tanα)  (= 外花键理论齿厚)
E_PITCH = M_MOD * (math.pi / 2 + 2 * X * math.tan(ALPHA))
# 基圆齿厚 sb = db(s/d + invα)
S_BASE = D_BASE * (E_PITCH / D_PITCH + inv(ALPHA))


def psi(r):
    """半径 r 处齿槽的半角宽 (rad)."""
    ar = math.acos(R_BASE / r)
    return E_PITCH / (2 * R_PITCH) + inv(ALPHA) - inv(ar)


def pin_measurement(e=E_PITCH, dp=PIN_D):
    """内花键量棒测跨距 M (棒间距)."""
    inv_am = e / D_PITCH + inv(ALPHA) - dp / D_BASE
    am = ainv(inv_am)
    dm = D_BASE / math.cos(am)          # 量棒中心圆直径
    if Z % 2:
        m_val = dm * math.cos(math.pi / (2 * Z)) - dp
    else:
        m_val = dm - dp
    return m_val, dm


def _flank_pt(r, side):
    """局部坐标 (齿槽中心在 0 rad) 下的齿面点, side=+1/-1."""
    t = side * psi(r)
    return (r * math.cos(t), r * math.sin(t))


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _solve(f, lo, hi, n=80):
    flo = f(lo)
    for _ in range(n):
        mid = (lo + hi) / 2
        fm = f(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


def _dist_to_flank(p):
    best = 1e9
    lo, hi = R_MINOR, R_MAJOR
    for _ in range(4):
        n = 60
        rs = [lo + (hi - lo) * i / n for i in range(n + 1)]
        ds = [_dist(p, _flank_pt(r, +1)) for r in rs]
        i = min(range(len(ds)), key=ds.__getitem__)
        best = min(best, ds[i])
        lo, hi = rs[max(i - 1, 0)], rs[min(i + 1, n)]
    return best, (lo + hi) / 2


def half_space_profile(n_flank=12):
    """
    '+' 侧半个齿槽的轮廓 (局部极坐标, 齿槽中心角 = 0)，由齿顶(小径)到齿根(大径)。
    返回 dict:
      tip_corner_arc  : 齿顶圆上倒角起点 (r, θ)
      chamfer_flank   : 齿面上倒角终点 r
      fillet_flank_r  : 齿面与 R0.5 圆角切点处半径
      fillet_center   : 圆角圆心 (x, y)
      root_theta      : 圆角与大径圆切点角度
    """
    # --- 齿顶倒角 C0.2 ---
    t_corner = psi(R_MINOR)
    tip_theta = t_corner + C_TIP / R_MINOR
    corner = _flank_pt(R_MINOR, +1)
    r_ch = _solve(lambda r: _dist(corner, _flank_pt(r, +1)) - C_TIP, R_MINOR, R_MINOR + 1.0)
    # --- 齿根圆角 R0.5: 圆心在 R_MAJOR-rf 圆上, 与齿面距离 = rf ---
    rc = R_MAJOR - R_ROOT_FILLET

    def g(th):
        c = (rc * math.cos(th), rc * math.sin(th))
        return _dist_to_flank(c)[0] - R_ROOT_FILLET

    th_c = _solve(g, 0.0, psi(rc))
    center = (rc * math.cos(th_c), rc * math.sin(th_c))
    _, r_tan = _dist_to_flank(center)
    return dict(tip_theta=tip_theta, chamfer_r=r_ch, fillet_r=r_tan,
                fillet_center=center, root_theta=th_c)


if __name__ == "__main__":
    print(f"d  = {D_PITCH:.3f}")
    print(f"db = {D_BASE:.3f}")
    print(f"e(分度圆理论齿槽宽) = {E_PITCH:.4f}")
    print(f"sb(基圆齿厚) = {S_BASE:.3f}")
    m_val, dm = pin_measurement()
    print(f"M(Ø{PIN_D}) = {m_val:.3f}, 量棒中心圆 = {dm:.3f}")
    for r in (R_MINOR, R_PITCH, R_MAJOR):
        print(f"r={r:.3f}: 齿槽宽 {2*psi(r)*r:.3f}, 齿宽 {(2*math.pi/Z-2*psi(r))*r:.3f}")
    print(half_space_profile())


# ---------------------------------------------------------------- 齿形轮廓 (多段线顶点)
PITCH_ANG = 2 * math.pi / Z
_HP = None


def _hp():
    global _HP
    if _HP is None:
        _HP = half_space_profile()
    return _HP


def space_chain(phi, n_flank=10):
    """一个齿槽 (中心角 phi) 的轮廓顶点 [x, y, bulge], 逆时针."""
    from cad_common import bulge_of, rot
    hp = _hp()
    tip_t, r_ch, r_fl = hp["tip_theta"], hp["chamfer_r"], hp["fillet_r"]
    fc, th_r = hp["fillet_center"], hp["root_theta"]

    def pol(r, t):
        return (r * math.cos(phi + t), r * math.sin(phi + t))

    def flank(r, side):
        return pol(r, side * psi(r))

    rs = [r_ch + (r_fl - r_ch) * i / n_flank for i in range(n_flank + 1)]
    v = [[*pol(R_MINOR, -tip_t), 0.0]]
    for r in rs:
        v.append([*flank(r, -1), 0.0])
    c_minus = rot((fc[0], -fc[1]), phi)
    p2 = pol(R_MAJOR, -th_r)
    v[-1][2] = bulge_of(c_minus, v[-1][:2], p2)
    v.append([*p2, math.tan(2 * th_r / 4)])
    p3 = pol(R_MAJOR, th_r)
    c_plus = rot(fc, phi)
    v.append([*p3, bulge_of(c_plus, p3, flank(r_fl, +1))])
    for r in reversed(rs):
        v.append([*flank(r, +1), 0.0])
    v.append([*pol(R_MINOR, tip_t), 0.0])
    return v


def full_profile():
    """整圈内花键轮廓 (齿槽中心在 90°), 闭合多段线顶点."""
    tip_t = _hp()["tip_theta"]
    verts = []
    for k in range(Z):
        ch = space_chain(math.pi / 2 + k * PITCH_ANG)
        ch[-1][2] = math.tan((PITCH_ANG - 2 * tip_t) / 4)
        verts.extend(ch)
    return verts


def window_profile(ks, th_s, th_e):
    """齿槽 ks 范围内的开口轮廓, 起止于小径圆上角度 th_s / th_e."""
    tip_t = _hp()["tip_theta"]
    phis = [math.pi / 2 + k * PITCH_ANG for k in ks]
    verts = [[R_MINOR * math.cos(th_s), R_MINOR * math.sin(th_s),
              math.tan(((phis[0] - tip_t) - th_s) / 4)]]
    for i, phi in enumerate(phis):
        ch = space_chain(phi)
        if i + 1 < len(phis):
            ch[-1][2] = math.tan((PITCH_ANG - 2 * tip_t) / 4)
        else:
            ch[-1][2] = math.tan((th_e - (phi + tip_t)) / 4)
        verts.extend(ch)
    verts.append([R_MINOR * math.cos(th_e), R_MINOR * math.sin(th_e), 0.0])
    return verts
