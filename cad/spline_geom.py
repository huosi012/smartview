"""JIS D2001 渐开线花键 —— 内花键齿形几何计算 (m=2.5, z=85, α=20°, x=+0.8)."""
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
