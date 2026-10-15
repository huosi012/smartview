"""2D top view (CAD-style) of the science hall and its surroundings, for confirming the site
layout before the 3D views are revised.

    python3 plan2d.py          ->  renders/plan2d.jpg        (site-confirmation draft, with items to measure)
    python3 plan2d.py --clean  ->  renders/plan2d_clean.jpg  (client version: no estimates, phases or notes)

Coordinates as in scene_v2.py: x along the terrace from the kerb (0) to the red wall (17.8),
y from the corridor parapet (0) to the street parapet (8.5). Corridor is y < 0.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "renders", "plan2d.jpg")
CJK = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"

L, W = 17.8, 8.5                 # terrace / hall: kerb -> red wall, corridor parapet -> street parapet
CW = 2.6                         # corridor clear width (estimate)
COLS = [7.0, 12.0]               # corridor columns located from the photos (estimate)
ALC = 2.4                        # louver alcove length (estimate); its end wall is in line with the red wall
PIER = L - ALC                   # last pier: corridor parapet ends here, louver alcove runs on to the red-wall line
DOOR = (PIER - 1.85, PIER - 0.35)  # door in the last bay, right next to the louver alcove
PHASE1_X = 11.8
GAP = 1.2                        # open gap between the end louvers and the red block behind them (as in scene_v2.py)
END_DOOR = (L - 1.0, L - 0.1)    # existing door in the classroom-side wall at the corridor end (louver photo)
PW = 6.0                         # raised platform width along the corridor (estimate, to measure)
BX = 6.5                         # length of the other terrace shown before the break line (not its real size)
GATE = (-PW - 1.9, -PW - 0.3)    # existing sliding gate under the stainless arch, corridor -> other terrace

S = 92                           # px per metre
X0, X1 = -PW - BX - 0.6, 22.4    # drawn extent (m)
Y0, Y1 = -4.3, 10.4
MARGIN_T, MARGIN_B, LEG = 250, 190, 1180
LEG_BAND = 420                   # client version: legend in a band under the drawing instead of a side column
WPX = int((X1 - X0) * S)
HPX = int((Y1 - Y0) * S)

INK = (40, 44, 42)
WALL = (70, 74, 72)
GLASS = (60, 150, 190)
RED = (176, 58, 50)
ORANGE = (214, 110, 50)
GREEN = (31, 77, 58)
GOLD = (176, 138, 70)
MUTED = (110, 112, 108)


def font(s):
    return ImageFont.truetype(CJK, int(s), index=0)


def P(x, y):
    return (int((x - X0) * S), int(MARGIN_T + (Y1 - y) * S))


def rect(d, x0, y0, x1, y1, **kw):
    a, b = P(x0, y1), P(x1, y0)
    d.rectangle((a[0], a[1], b[0], b[1]), **kw)


def hatch(d, x0, y0, x1, y1, col, step=0.35, width=2):
    """45-degree hatch clipped to a rectangle."""
    k = x0 - (y1 - y0)
    while k < x1:
        pts = []
        for t in (0.0, 1.0):
            pass
        ax, ay = k, y0
        bx, by = k + (y1 - y0), y1
        if ax < x0:
            ay += x0 - ax
            ax = x0
        if bx > x1:
            by -= bx - x1
            bx = x1
        if ay <= y1 and by >= y0 and ax <= bx:
            d.line((P(ax, ay), P(bx, by)), fill=col, width=width)
        k += step


def text(d, xy, s, size, col=INK, anchor="mm", bg=None):
    f = font(size)
    if bg:
        tw = d.textlength(s, font=f)
        x, y = xy
        if anchor == "mm":
            box = (x - tw / 2 - 8, y - size * 0.75, x + tw / 2 + 8, y + size * 0.75)
        else:
            box = (x - 6, y - size * 0.75, x + tw + 8, y + size * 0.75)
        d.rounded_rectangle(box, radius=6, fill=bg)
    d.text(xy, s, font=f, fill=col, anchor=anchor)


def dim_h(d, x0, x1, y, label, size=30, off=0):
    a, b = P(x0, y), P(x1, y)
    d.line((a, b), fill=INK, width=2)
    for p in (a, b):
        d.line((p[0], p[1] - 12, p[0], p[1] + 12), fill=INK, width=2)
        d.line((p[0] - 7, p[1] + 7, p[0] + 7, p[1] - 7), fill=INK, width=2)
    text(d, ((a[0] + b[0]) / 2, a[1] - 22 + off), label, size, bg=(255, 255, 255))


def dim_v(d, y0, y1, x, label, size=30):
    a, b = P(x, y0), P(x, y1)
    d.line((a, b), fill=INK, width=2)
    for p in (a, b):
        d.line((p[0] - 12, p[1], p[0] + 12, p[1]), fill=INK, width=2)
        d.line((p[0] - 7, p[1] + 7, p[0] + 7, p[1] - 7), fill=INK, width=2)
    text(d, (a[0] - 10, (a[1] + b[1]) / 2), label, size, bg=(255, 255, 255))


def marker(d, x, y, n):
    px, py = P(x, y)
    r = 21
    d.ellipse((px - r, py - r, px + r, py + r), fill=ORANGE, outline=(255, 255, 255), width=3)
    text(d, (px, py), str(n), 24, col=(255, 255, 255))


def draw_interior(d):
    fill = (255, 255, 255)
    # 1 seed germination window along the kerb
    rect(d, 0.03, 0.4, 0.42, W - 0.4, fill=(150, 112, 80))
    # 2 vertical hydroponic racks along the corridor glass
    for a, b in ((1.2, 3.6), (3.9, 6.3), (6.6, 9.0), (9.3, 11.7)):
        rect(d, a, 0.35, b, 0.95, fill=(226, 214, 238), outline=(150, 120, 170), width=2)
    # 3 class beds along the street side
    for k in range(8):
        a = 1.0 + k * 1.65
        rect(d, a, 7.35, a + 1.4, 8.25, fill=(120, 92, 66), outline=(80, 60, 40), width=2)
    # 4 aeroponic towers
    for (x, y) in [(2.2, 3.1), (3.2, 3.1), (2.2, 5.4), (3.2, 5.4), (12.75, 3.0), (12.75, 5.5)]:
        a, b = P(x - 0.28, y + 0.28), P(x + 0.28, y - 0.28)
        d.ellipse((a[0], a[1], b[0], b[1]), fill=(230, 240, 230), outline=(70, 120, 80), width=3)
    # 5 aquaponics tank
    rect(d, 5.2, 3.85, 7.0, 4.65, fill=(180, 214, 222), outline=(60, 120, 140), width=3)
    # 6 workbenches + stools
    for y0_, y1_ in ((2.6, 3.5), (5.0, 5.9)):
        rect(d, 9.6, y0_, 11.6, y1_, fill=(196, 170, 140), outline=(130, 100, 70), width=2)
        for x in (9.95, 10.6, 11.25):
            for y in (y0_ - 0.32, y1_ + 0.32):
                a, b = P(x - 0.17, y + 0.17), P(x + 0.17, y - 0.17)
                d.ellipse((a[0], a[1], b[0], b[1]), fill=(225, 225, 220), outline=(150, 150, 146))
    # 7 lecture seats
    for x in (14.0, 14.75, 15.5, 16.25):
        for y in (2.75, 3.55, 4.35, 5.15, 5.95):
            a, b = P(x - 0.18, y + 0.18), P(x + 0.18, y - 0.18)
            d.ellipse((a[0], a[1], b[0], b[1]), fill=(240, 200, 120), outline=(170, 130, 60))
    # 8 red-wall feature wall + screen
    rect(d, L - 0.3, 0.3, L - 0.02, 8.2, fill=(140, 96, 60))
    rect(d, L - 0.36, 3.38, L - 0.24, 5.12, fill=(30, 30, 30))
    # 9 seedling rack, 10 fertigation
    rect(d, 12.0, 0.35, 13.2, 0.84, fill=(226, 214, 238), outline=(150, 120, 170), width=2)
    rect(d, 16.9, 7.45, 17.5, 8.25, fill=(235, 235, 232), outline=(120, 120, 116), width=2)
    a, b = P(16.15, 8.1), P(16.65, 7.6)
    d.ellipse((a[0], a[1], b[0], b[1]), fill=(80, 120, 190))


def paste_render(img):
    """Use the rendered top view (renders/plan.png, ortho 20.5 m wide centred on the hall) for the hall interior."""
    src = os.path.join(HERE, "renders", "plan.png")
    r = Image.open(src).convert("RGB")
    ppm = r.width / 20.5
    cx, cy = L / 2 - 0.6, W / 2 - 0.3
    box = (r.width / 2 + (0 - cx) * ppm, r.height / 2 - (W - cy) * ppm,
           r.width / 2 + (L - cx) * ppm, r.height / 2 - (0 - cy) * ppm)
    crop = r.crop(tuple(int(round(v)) for v in box)).resize((int(round(L * S)), int(round(W * S))), Image.LANCZOS)
    img.paste(crop, P(0.0, W))


def main(clean=False):
    def T(draft, client):
        return client if clean else draft
    size = (WPX, HPX + MARGIN_T + MARGIN_B + LEG_BAND) if clean else (WPX + LEG, HPX + MARGIN_T + MARGIN_B)
    img = Image.new("RGB", size, (250, 250, 247))
    d = ImageDraw.Draw(img)

    # ---------------- surroundings
    rect(d, X0, -0.25 - CW - 0.3, L + GAP, -0.25 - CW, fill=(205, 205, 200))      # classroom wall line
    rect(d, X0, -0.25 - CW - 1.3, L + GAP, -0.25 - CW - 0.3, fill=(232, 232, 228))  # classrooms
    text(d, P(5.0, -0.25 - CW - 0.8), "教室", 28, MUTED)
    rect(d, X0, -0.25 - CW, L, -0.25, fill=(236, 233, 224))                       # corridor floor
    text(d, P(3.6, -1.55), T("教学楼走廊（宽约 2.6 m，待量）", "教学楼走廊"), 30, MUTED)
    # raised platform
    rect(d, -PW, 0.0, 0.0, W, fill=(214, 214, 210))
    hatch(d, -PW, 0.0, 0.0, W, (190, 190, 186), 0.5, 1)
    text(d, P(-PW / 2, 5.6), "抬高平台（高台）", 32, INK, bg=(240, 240, 236))
    text(d, P(-PW / 2, 4.9), "高出两侧空地约 0.9 m", 24, MUTED)
    text(d, P(-PW / 2, 4.35), T(f"宽约 {PW:.0f} m（待量）", f"宽约 {PW:.0f} m"), 24, MUTED)
    # the other terrace beyond the platform (drawn partly, break line)
    bx0 = -PW - BX
    rect(d, bx0, 0.0, -PW, W, fill=(244, 243, 238))
    text(d, P(-PW - BX / 2, 5.4), "另一块空地", 32, INK, bg=(250, 250, 247))
    text(d, P(-PW - BX / 2, 4.7), T("（高台另一侧，长度待量，图中未画完）", "（高台另一侧）"), 22, MUTED)
    zz = [P(bx0 + (0.18 if k % 2 else -0.18), -2.0 + k * 0.6) for k in range(int((W + 2.6) / 0.6) + 1)]
    d.line(zz, fill=MUTED, width=3)
    # existing steel steps from the other terrace up onto the platform
    rect(d, -PW - 0.9, 1.6, -PW, 2.8, fill=(150, 112, 80), outline=(90, 60, 40), width=2)
    for k in range(1, 3):
        d.line((P(-PW - 0.9 + k * 0.3, 1.6), P(-PW - 0.9 + k * 0.3, 2.8)), fill=(90, 60, 40), width=2)
    text(d, P(-PW - 0.45, 3.15), "现有钢梯", 20, MUTED)
    text(d, P(-0.25, W - 0.4), "坎", 26, INK, bg=(250, 250, 247))
    # red block beyond the terrace end (its face is in line with the louver alcove's end wall)
    rect(d, L, 0.0, X1, Y1, fill=(232, 200, 194))
    hatch(d, L, 0.0, X1, Y1, RED, 0.45, 2)
    # ... and it continues behind the corridor end, ~1.2 m behind the end louvers
    yb = -0.25 - CW - 1.3
    rect(d, L + GAP, yb, X1, 0.0, fill=(232, 200, 194))
    hatch(d, L + GAP, yb, X1, 0.0, RED, 0.45, 2)
    if not clean:
        text(d, P(L + GAP / 2 + 0.12, -1.5), "空隙", 18, MUTED)
        text(d, P(L + GAP / 2 + 0.12, -1.85), "≈1.2", 16, MUTED)
    text(d, P(20.1, 5.2), "红色楼体", 36, RED, bg=(250, 238, 236))
    text(d, P(20.1, 4.4), "（展厅尽端靠红墙）", 24, RED, bg=(250, 238, 236))
    # street side
    rect(d, X0, W, L, W + 0.25, fill=WALL)
    text(d, P(8.9, W + 0.6), "沿街围墙（保留原宣传栏，墙上装推拉玻璃窗）", 26, MUTED)

    if clean:
        paste_render(img)

    # ---------------- corridor parapet, columns, door, louver alcove
    rect(d, X0, -0.25, GATE[0], 0.0, fill=WALL)
    rect(d, GATE[1], -0.25, DOOR[0], 0.0, fill=WALL)
    d.line((P(GATE[0], -0.12), P(GATE[1], -0.12)), fill=(120, 120, 116), width=5)          # existing sliding gate
    text(d, P((GATE[0] + GATE[1]) / 2, -0.75), "现有推拉门+不锈钢拱门", 20, MUTED, bg=(255, 255, 255))
    rect(d, DOOR[1], -0.25, PIER - 0.25, 0.0, fill=WALL)
    for cx in COLS:
        rect(d, cx - 0.25, -0.55, cx + 0.25, 0.0, fill=INK)
    rect(d, PIER - 0.25, -0.55, PIER + 0.25, 0.0, fill=INK)                        # end pier
    # door: double leaf swing arcs
    mid = (DOOR[0] + DOOR[1]) / 2
    for hinge, sgn in ((DOOR[0], 1), (DOOR[1], -1)):
        hx, hy = P(hinge, 0.0)
        r = (DOOR[1] - DOOR[0]) / 2 * S
        box = (hx - r, hy - r, hx + r, hy + r)
        d.arc(box, 270 if sgn > 0 else 180, 360 if sgn > 0 else 270, fill=ORANGE, width=3)
        d.line((P(hinge, 0.0), P(hinge, (DOOR[1] - DOOR[0]) / 2)), fill=ORANGE, width=4)
    text(d, P(mid, -0.75), "入口 1.5 m", 26, ORANGE, bg=(255, 255, 255))
    # glass sealing the corridor railing (whole hall length except the door)
    for a, b in ((0.0, DOOR[0]), (DOOR[1], PIER - 0.25)):
        d.line((P(a, 0.06), P(b, 0.06)), fill=GLASS, width=6)
    # louver alcove: side louvers face the hall, end louvers in line with the red wall
    d.line((P(PIER + 0.25, 0.06), P(L, 0.06)), fill=GLASS, width=6)                # glass on the hall side
    ax0, ax1 = PIER + 0.25, L
    rect(d, ax0, -0.25 - CW, ax1, -0.25, fill=(236, 233, 224))
    for a, b, horiz in ((ax0, ax1, True),):
        x = a
        while x < b:
            rect(d, x, -0.25, min(b, x + 0.12), 0.0, fill=(120, 120, 116))
            x += 0.3
    y = -0.25 - CW
    while y < -0.25:
        rect(d, ax1, y, ax1 + 0.25, min(-0.25, y + 0.12), fill=(120, 120, 116))
        y += 0.3
    d.rectangle((P(ax0, 0.0)[0], P(ax0, 0.0)[1], P(ax1 + 0.25, -0.25 - CW)[0], P(ax1 + 0.25, -0.25 - CW)[1]),
                outline=ORANGE, width=4)
    text(d, P((ax0 + ax1) / 2, -1.35), "百叶格栅", 28, INK, bg=(255, 255, 255))
    text(d, P((ax0 + ax1) / 2, -1.9), "植物观察窗", 24, MUTED)
    text(d, P((ax0 + ax1) / 2, -2.35), T("（长约 2.4 m，待量）", "（长约 2.4 m）"), 20, MUTED)
    if not clean:
        text(d, P(ax0 + 0.6, 0.75), "格栅朝展厅一侧封玻璃", 20, MUTED)
        text(d, P(ax0 + 0.6, 0.4), "展厅内外都能看到盆栽", 20, MUTED)
    # entrance totem in the corridor
    rect(d, DOOR[0] - 0.9, -0.8, DOOR[0] - 0.3, -0.7, fill=GREEN)
    # existing door at the corridor end (classroom-side wall, next to the end louvers)
    yw = -0.25 - CW
    rect(d, END_DOOR[0], yw - 0.3, END_DOOR[1], yw, fill=(236, 233, 224))
    dw = END_DOOR[1] - END_DOOR[0]
    hx, hy = P(END_DOOR[1], yw - 0.3)
    r = dw * S
    d.arc((hx - r, hy - r, hx + r, hy + r), 90, 180, fill=INK, width=2)
    d.line((P(END_DOOR[1], yw - 0.3), P(END_DOOR[1], yw - 0.3 - dw)), fill=INK, width=4)
    text(d, P(END_DOOR[0] - 1.15, yw - 0.6), "现有门", 20, INK, bg=(255, 255, 255))
    if clean:
        text(d, P(DOOR[0] - 0.6, -1.15), "入口立牌", 20, MUTED)

    # ---------------- hall envelope
    d.line((P(0.03, 0.0), P(0.03, W)), fill=GLASS, width=6)                          # kerb-end glass wall
    d.line((P(0.0, W - 0.06), P(L, W - 0.06)), fill=GLASS, width=6)                 # street sliding windows
    for x in [i * L / 16 for i in range(17)]:
        d.line((P(x, W - 0.18), P(x, W + 0.02)), fill=GLASS, width=2)
    d.rectangle((P(0, W)[0], P(0, W)[1], P(L, 0)[0], P(L, 0)[1]), outline=GREEN, width=3)
    # roof slope arrow
    if clean:
        d.rectangle((P(0, W)[0], P(0, W)[1], P(L, 0)[0], P(L, 0)[1]), outline=GREEN, width=3)
    sx = 8.8
    d.line((P(sx, 1.8), P(sx, 6.6)), fill=(150, 150, 146), width=3)
    tip = P(sx, 6.6)
    d.polygon([tip, (tip[0] - 12, tip[1] + 22), (tip[0] + 12, tip[1] + 22)], fill=(150, 150, 146))

    # ---------------- interior (same positions as scene_v2.py)
    if not clean:
        draw_interior(d)
    # entry clearance
    d.rectangle((P(DOOR[0], 2.2)[0], P(DOOR[0], 2.2)[1], P(DOOR[1], 0.0)[0], P(DOOR[1], 0.0)[1]),
                outline=ORANGE, width=2)
    text(d, P(mid, 1.55), "入口通道", 22, ORANGE, bg=(255, 255, 255) if clean else None)

    # phase line
    if not clean:
        draw_phase(d)

    # numbered markers
    marks = [(0.22, 2.2), (2.4, 0.65), (4.5, 7.8), (2.7, 4.25), (6.1, 4.25), (10.6, 4.25), (16.95, 3.2),
             (17.6, 2.0), (12.6, 0.6), (17.2, 7.0)]
    for i, (x, y) in enumerate(marks, 1):
        marker(d, x, y, i)
    rest(d, img, clean, T)


def draw_phase(d):
    x0p, ytop = P(PHASE1_X, W + 0.1)
    _, ybot = P(PHASE1_X, -0.1)
    yy = ytop
    while yy < ybot:
        d.line((x0p, yy, x0p, min(ybot, yy + 22)), fill=ORANGE, width=5)
        yy += 36
    text(d, P(14.8, W - 1.75), "一期 6.0 × 8.5 m ≈ 51 ㎡", 26, (255, 255, 255), bg=ORANGE)
    text(d, P(6.0, W - 1.75), "二期 ≈ 100 ㎡", 26, (255, 255, 255), bg=(130, 130, 125))


def rest(d, img, clean, T):
    # dimensions
    dim_h(d, 0.0, L, Y1 - 0.4, T("17.8 m（坎 → 红墙，客户给）", "17.8 m（坎 → 红墙）"))
    dim_v(d, 0.0, W, -0.55, "8.5 m")
    dim_h(d, -PW, 0.0, W + 0.6, T(f"高台 ≈{PW:.1f}（待量）", f"高台 ≈{PW:.1f} m"), 22)
    dim_h(d, DOOR[0], DOOR[1], -4.45, "1.5", 22)
    dim_h(d, PIER, L, -4.45, "≈2.4", 22)
    if not clean:
        for cx in COLS + [PIER]:
            px, py = P(cx, -0.55)
            d.line((px, py, px, P(cx, -3.4)[1]), fill=(170, 170, 166), width=1)
            text(d, P(cx, -3.25), f"≈{cx:.1f}", 20, MUTED)
        text(d, P(-PW / 2, -3.25), "柱位（按照片估；高台和另一块空地段未画柱）", 20, MUTED)

    # title
    text(d, (60, 70), T("智慧农业科普展厅 · 二维平面（现场关系确认稿）", "智慧农业科普展厅 · 平面布置图"), 56, GREEN, anchor="lm")
    text(d, (60, 140), T("高台两侧各一块空地，展厅在红墙这一侧：坎 → 红墙 17.8 m，走廊栏杆 → 沿街围墙 8.5 m；走廊尽头是百叶格栅段，末端与红墙齐平、侧面朝展厅；入口紧挨格栅",
                         "高台两侧各一块空地，展厅在红墙一侧，17.8 m × 8.5 m；走廊尽头为百叶格栅植物观察窗，入口紧挨格栅"),
         28, MUTED, anchor="lm")
    d.rectangle((60, 180, 300, 186), fill=GOLD)

    # north-free note + scale bar
    sx0, sy0 = 60, HPX + MARGIN_T + 110
    for k in range(5):
        a = sx0 + k * S
        d.rectangle((a, sy0 - 8, a + S, sy0 + 8), fill=INK if k % 2 == 0 else (255, 255, 255), outline=INK, width=2)
    text(d, (sx0, sy0 - 30), "0", 22, INK)
    text(d, (sx0 + 5 * S, sy0 - 30), "5 m", 22, INK)
    text(d, (sx0 + 5 * S + 60, sy0), T("朝向未知，图中不标指北；屋面坡向：走廊侧高 → 沿街侧低（灰色箭头）",
                                       "屋面坡向：走廊侧高 → 沿街侧低（灰色箭头）。示意图，尺寸以现场实测为准"), 24, MUTED, anchor="lm")

    # legend: side column (draft) or a 3-column band under the drawing (client)
    lx = WPX + 50
    if clean:
        band_y = HPX + MARGIN_T + MARGIN_B
        d.line((60, band_y - 10, WPX - 60, band_y - 10), fill=(214, 214, 208), width=2)
        text(d, (60, band_y + 50), "功能分区", 40, GREEN, anchor="lm")
        col_w = (WPX - 120) / 3
        slots = [(60 + (k // 5) * col_w, band_y + 120 + (k % 5) * 58) for k in range(15)]
    else:
        text(d, (lx, MARGIN_T + 10), "图例", 44, GREEN, anchor="lm")
    items = [
        "种子萌发观察窗（坎内玻璃面，与坎齐平）",
        "立体水培架 ×4（贴走廊玻璃，走廊可看）",
        "班级种植箱 ×8",
        "气雾栽培塔 ×6",
        "鱼菜共生展示缸",
        "研学操作台 ×2（12 座）",
        "科普讲解区（20 座）",
        "红墙展示墙（大屏 · 时间轴 · 照片墙）",
        "育苗架",
        "水肥一体机 + 营养液罐",
    ]
    y = MARGIN_T + 80
    for i, s in enumerate(items, 1):
        if clean:
            lx, y = slots[i - 1]
        px, py = lx + 21, y
        d.ellipse((px - 21, py - 21, px + 21, py + 21), fill=ORANGE)
        text(d, (px, py), str(i), 22, (255, 255, 255))
        text(d, (lx + 56, y), s, 27, INK, anchor="lm")
        y += 58
    y += 20
    keys = [
        ("line", GLASS, "玻璃：走廊栏杆外封闭 / 坎边端墙 / 沿街推拉窗"),
        ("box", WALL, "原有墙体、栏板"),
        ("box", INK, T("走廊柱（位置按照片估）", "走廊柱")),
        ("box", (120, 120, 116), "百叶格栅（走廊尽头，侧面朝展厅）"),
        ("hatch", RED, "红色楼体"),
        ("dash", ORANGE, "一期分界线"),
    ]
    if clean:
        keys = keys[:-1]
    for j, (kind, col, s) in enumerate(keys):
        if clean:
            lx, y = slots[10 + j]
        if kind == "line":
            d.line((lx, y, lx + 44, y), fill=col, width=6)
        elif kind == "box":
            d.rectangle((lx, y - 12, lx + 44, y + 12), fill=col)
        elif kind == "hatch":
            d.rectangle((lx, y - 12, lx + 44, y + 12), fill=(232, 200, 194))
            for k in range(0, 44, 10):
                d.line((lx + k, y + 12, lx + k + 12, y - 12), fill=col, width=2)
        else:
            for k in range(0, 44, 16):
                d.line((lx + k, y, lx + k + 9, y), fill=col, width=5)
        text(d, (lx + 60, y), s, 25, INK, anchor="lm")
        y += 48
    y += 30
    if not clean:
        confirm_list(d, lx, y)
    out = OUT.replace(".jpg", "_clean.jpg") if clean else OUT
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out, quality=93)
    print("saved", out, img.size)


def confirm_list(d, lx, y):
    text(d, (lx, y), "请现场确认", 34, ORANGE, anchor="lm")
    y += 54
    for s in ["1. 17.8 m 是否量到红墙（格栅段末端与红墙齐平）",
              "2. 入口在最后一跨、紧挨格栅",
              f"3. 格栅段长度（≈{ALC:.1f} m）、走廊宽度",
              f"4. 走廊柱实际位置（图中 ≈{COLS[0]:.1f} / ≈{COLS[1]:.1f} / ≈{PIER:.1f}）",
              "5. 露台比走廊地面高多少（门口做台阶还是坡道）",
              "6. 高台宽度、另一块空地的长度",
              "7. 另一块空地这次是否一起设计",
              "8. 走廊尽头现有门的位置、开向，门后是什么房间"]:
        text(d, (lx, y), s, 24, INK, anchor="lm")
        y += 42


if __name__ == "__main__":
    import sys
    main(clean="--clean" in sys.argv)
