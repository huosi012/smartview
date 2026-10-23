#!/usr/bin/env python3
"""婚车路线图生成器。

路线：中国石油万金塔派出所北加油站（男方）→ 腰周家（女方）
      → 德惠市人民政府 → 中国石油万金塔派出所北加油站（男方）

用法：
  python3 make_route_map.py                       # 只生成 SVG / HTML
  python3 make_route_map.py --fonts <dir> --png   # 同时用 Chromium 渲染 PNG

--fonts 指向 `npm i @fontsource/noto-sans-sc @fontsource/zcool-qingke-huangyou
@fontsource/ma-shan-zheng` 后的 node_modules/@fontsource 目录；不指定时使用系统字体。
日期、姓名、时间安排、电话等请直接修改下面的 INFO。
"""
import argparse
import html
import math
import os
import subprocess

# ---------------------------------------------------------------- 可修改的信息
INFO = {
    "date": "2026.10.28",
    "lunar": "农历九月十九 · 星期三",
    "groom": "谢拾雨",
    "bride": "周心语",
    # (时间, 事项, 备注)；备注可留空
    "schedule": [
        ("5:00 – 5:20", "到达万金塔集结扎花", ""),
        ("5:30", "从万金塔出发（男方）", ""),
        ("6:30", "到达腰周家（女方）", ""),
        ("8:00", "从腰周家出发返回万金塔", "途经德惠市人民政府"),
    ],
    "thanks": "感谢各位朋友，请按图示路线行驶",
    "phone": "",  # 留空则不显示联系电话
}

W, H = 1800, 1280

PINK = "#ff2a73"
ORANGE = "#ff8a00"
BLUE = "#1f49ff"
RED_ROAD = "#e8232f"
BLUE_ROAD = "#27a2e6"
ROAD_FILL = "#fffafd"
TEXT = "#4a4a4a"

SANS = "'Noto Sans SC','WenQuanYi Zen Hei',sans-serif"
DISPLAY = "'ZCOOL QingKe HuangYou','Noto Sans SC','WenQuanYi Zen Hei',sans-serif"
BRUSH = "'Ma Shan Zheng','Noto Sans SC','WenQuanYi Zen Hei',serif"

# ---------------------------------------------------------------- 路网（示意坐标）
HOME = (205, 262)          # 新郎家：中国石油万金塔派出所北加油站
P0 = (225, 350)            # 加油站出口接 303 省道
TIANTAI = (760, 400)       # 天台镇
J1 = (1060, 445)           # 303 省道转向德惠
J2 = (1155, 600)           # 德惠西北路口
J3 = (1194, 925)           # 德农路路口
J4 = (1252, 1100)          # 德农环路 × G102
BRIDE = (1175, 1180)       # 新娘家：腰周家
K = (1487, 857)            # G102 在红旗大市场处转入城区
K2 = (1505, 818)
GOV = (1629, 906)          # 德惠市人民政府
N1 = (1675, 860)

G1 = [(1345, -10), (1252, 464), (1214, 590), (1160, 790), (1112, 940), (1052, 1120),
      (1012, 1290)]      # 京哈高速，只作参照
S303 = [(60, 333), P0, (470, 371), TIANTAI, J1, (1270, 466), (1390, 472)]
WEST_RING = [J2, (1178, 664), (1236, 732), (1262, 778), J3, (1220, 1068), J4]
G102 = [(1090, 1267), BRIDE, J4, K]
CITY = [K, K2, GOV, N1, (1592, 795), (1378, 694), (1338, 640), (1290, 610), (1232, 602), J2]

MAJOR, MINOR = (RED_ROAD, 40), (BLUE_ROAD, 34)
HIGHWAY = ("#7f93c4", 26)
ROADS = [
    (G1, HIGHWAY),                                     # 先画，路线道路从上方跨过
    (S303, MAJOR),
    ([J1, J2], MAJOR),
    (G102 + CITY[1:], MAJOR),                         # G102 进城后接城区道路
    (WEST_RING, MINOR),
    ([J3, (1000, 960), (960, 967)], MINOR),            # 德农路
    ([J4, (1460, 1150), (1610, 1140)], MINOR),          # 德农环路东段
    ([HOME, P0], MINOR),                                # 加油站出口
]

LEG_TO_BRIDE = [HOME, P0, (470, 371), TIANTAI, J1, J2] + WEST_RING[1:] + [BRIDE]
LEG_TO_GOV = [BRIDE, J4, K, K2, GOV]
LEG_HOME = CITY[CITY.index(GOV):] + [J1, TIANTAI, (470, 371), P0, HOME]
LEGS = [(LEG_TO_BRIDE, PINK, 30), (LEG_TO_GOV, ORANGE, 40), (LEG_HOME, BLUE, 70)]


# ---------------------------------------------------------------- 几何工具
def seg_lengths(pts):
    return [math.dist(a, b) for a, b in zip(pts, pts[1:])]


def point_at(pts, s):
    """返回折线上弧长 s 处的点、单位切向量，以及到最近折点的距离。"""
    acc = 0.0
    lens = seg_lengths(pts)
    for i, ln in enumerate(lens):
        if acc + ln >= s or i == len(lens) - 1:
            t = (s - acc) / ln
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            dx, dy = (x1 - x0) / ln, (y1 - y0) / ln
            near = min(s - acc, acc + ln - s)
            return (x0 + t * (x1 - x0), y0 + t * (y1 - y0)), (dx, dy), near
        acc += ln


def pts_attr(pts):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


# ---------------------------------------------------------------- SVG 片段
def text(x, y, s, size, fill=TEXT, family=SANS, weight=400, anchor="middle",
         rotate=0, halo=None, extra=""):
    tr = f' transform="rotate({rotate:.1f} {x:.1f} {y:.1f})"' if rotate else ""
    st = (f' stroke="{halo}" stroke-width="{max(4, size // 6)}" stroke-linejoin="round"'
          f' paint-order="stroke"') if halo else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'font-family="{family}" font-weight="{weight}" text-anchor="{anchor}"'
            f'{tr}{st}{extra}>{html.escape(s)}</text>')


def arrow(x, y, dx, dy, color, length=46, shaft=7, head=20, half=9):
    tx, ty = x - dx * length / 2, y - dy * length / 2
    hx, hy = x + dx * length / 2, y + dy * length / 2
    bx, by = hx - dx * head, hy - dy * head
    nx, ny = -dy, dx
    tri = [(hx, hy), (bx + nx * half, by + ny * half), (bx - nx * half, by - ny * half)]
    return (f'<line x1="{tx:.1f}" y1="{ty:.1f}" x2="{bx + dx * 2:.1f}" y2="{by + dy * 2:.1f}" '
            f'stroke="{color}" stroke-width="{shaft}" stroke-linecap="round"/>'
            f'<polygon points="{pts_attr(tri)}" fill="{color}" stroke="{color}" '
            f'stroke-width="2" stroke-linejoin="round"/>')


def leg_arrows(pts, color, phase, spacing=128, offset=9, margin=48, corner=30):
    out = []
    total = sum(seg_lengths(pts))
    s = margin + phase
    while s < total - margin:
        (x, y), (dx, dy), near = point_at(pts, s)
        if near < corner:
            s += 12
            continue
        # 靠右行驶：箭头画在行进方向右侧车道
        out.append(arrow(x - dy * offset, y + dx * offset, dx, dy, color))
        s += spacing
    return out


def road_label(a, b, s, side=1, gap=40, size=24, t=0.5, fill="#5b5b5b"):
    (x0, y0), (x1, y1) = a, b
    ln = math.dist(a, b)
    dx, dy = (x1 - x0) / ln, (y1 - y0) / ln
    x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
    x, y = x - dy * gap * side, y + dx * gap * side
    ang = math.degrees(math.atan2(dy, dx))
    if ang > 90:
        ang -= 180
    elif ang <= -90:
        ang += 180
    return text(x, y + size * 0.35, s, size, fill, SANS, 500, rotate=ang,
                halo="#fff3f7")


def shield(x, y, label, bg, fg, rotate=0, border="#ffffff"):
    w = 14 * len(label) + 16
    tr = f' transform="rotate({rotate:.1f} {x} {y})"' if rotate else ""
    return (f'<g{tr}><rect x="{x - w / 2:.1f}" y="{y - 15}" width="{w}" height="30" rx="6" '
            f'fill="{bg}" stroke="{border}" stroke-width="3"/>'
            + text(x, y + 8, label, 20, fg, SANS, 700) + "</g>")


def poi(x, y, label, color, glyph, size=22):
    """地图上的小地标：彩色圆点图标 + 文字，(x, y) 为文字基线起点。"""
    return (f'<circle cx="{x - 16}" cy="{y - size * 0.35:.1f}" r="12" fill="{color}"/>'
            + text(x - 16, y - size * 0.35 + 5, glyph, 14, "#fff", SANS, 700)
            + text(x, y, label, size, color, SANS, 500, anchor="start", halo="#fff3f7"))


def pin(x, y, color, inner="♥"):
    body = (f'M{x},{y} C{x - 6},{y - 14} {x - 24},{y - 26} {x - 24},{y - 44} '
            f'A24,24 0 1 1 {x + 24},{y - 44} C{x + 24},{y - 26} {x + 6},{y - 14} {x},{y} Z')
    return (f'<ellipse cx="{x}" cy="{y}" rx="13" ry="5" fill="#000" opacity=".18"/>'
            f'<path d="{body}" fill="{color}" stroke="#fff" stroke-width="4"/>'
            f'<circle cx="{x}" cy="{y - 44}" r="15" fill="#fff"/>'
            + text(x, y - 36, inner, 22, color, SANS, 900))


def heart(x, y, size, color, rot=0, opacity=1.0):
    k = size / 60
    return (f'<path transform="translate({x} {y}) rotate({rot}) scale({k:.3f})" '
            f'd="M0,26 C-34,2 -46,-14 -38,-30 C-30,-46 -8,-44 0,-26 '
            f'C8,-44 30,-46 38,-30 C46,-14 34,2 0,26 Z" fill="{color}" opacity="{opacity}"/>')


# ---------------------------------------------------------------- 组装
def build_svg():
    o = []
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}">')
    o.append('''<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="0.35" y2="1">
    <stop offset="0" stop-color="#fff7fa"/><stop offset=".55" stop-color="#ffeef4"/>
    <stop offset="1" stop-color="#ffdbe7"/></linearGradient>
  <radialGradient id="blob" cx=".5" cy=".5" r=".5">
    <stop offset="0" stop-color="#ffc2d6" stop-opacity=".85"/>
    <stop offset="1" stop-color="#ffc2d6" stop-opacity="0"/></radialGradient>
  <linearGradient id="seal" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#f2373f"/><stop offset="1" stop-color="#c8101c"/></linearGradient>
  <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">
    <feDropShadow dx="0" dy="3" stdDeviation="3" flood-color="#c2185b" flood-opacity=".25"/></filter>
</defs>''')
    o.append(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')
    o.append('<circle cx="1730" cy="-40" r="330" fill="url(#blob)"/>')
    o.append('<circle cx="-40" cy="1320" r="380" fill="url(#blob)"/>')
    o.append('<circle cx="1820" cy="1260" r="240" fill="url(#blob)"/>')

    # 道路：先画所有描边，再画所有填充，交叉口自然连通
    for pts, (color, width) in ROADS:
        o.append(f'<polyline points="{pts_attr(pts)}" fill="none" stroke="{color}" '
                 f'stroke-width="{width + 10}" stroke-linejoin="round" stroke-linecap="butt"/>')
    for pts, (color, width) in ROADS:
        fill = "#eef1fa" if pts is G1 else ROAD_FILL
        o.append(f'<polyline points="{pts_attr(pts)}" fill="none" stroke="{fill}" '
                 f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="butt"/>')

    # 路名
    o.append(road_label((470, 371), TIANTAI, "303省道", side=-1, gap=44, size=26))
    o.append(shield(452, 318, "S303", "#ffd23f", "#333", rotate=4.9))
    o.append(road_label(J1, (1270, 466), "303省道", side=-1, gap=44, size=26))
    o.append(road_label((1178, 664), (1236, 732), "西环城路", side=1, gap=42))
    o.append(road_label(J3, (1220, 1068), "德农环路", side=1, gap=44, t=0.45))
    o.append(road_label(J4, (1460, 1150), "德农环路", side=-1, gap=38, t=0.66))
    o.append(shield(1530, 1147, "S001", "#ffd23f", "#333", rotate=-3.8))
    o.append(shield(1141, 492, "Y037", "#ffffff", "#333", rotate=58.5, border="#333"))
    o.append(shield(1294, 250, "G1", "#1f8f4e", "#fff"))
    o.append(road_label((1345, -10), (1252, 464), "京哈高速", side=-1, gap=34, t=0.7,
                        fill="#5d6f9c"))
    o.append(road_label((1112, 940), (1052, 1120), "京哈高速", side=1, gap=34,
                        fill="#5d6f9c"))
    o.append(road_label(J3, (1000, 960), "德农路", side=1, gap=36, t=0.72))
    o.append(road_label(J4, K, "G102国道", side=1, gap=46, size=26, t=0.48))
    o.append(shield(1121, 1235, "G102", "#e8232f", "#fff", rotate=-46))

    # 地标
    o.append(text(TIANTAI[0], 456, "天台镇", 28, TEXT, SANS, 500))
    o.append(text(70, 300, "万金塔乡", 24, "#777", SANS, 400, anchor="start"))
    o.append('<circle cx="1306" cy="744" r="13" fill="#2f7bf6"/>'
             + text(1306, 751, "站", 15, "#fff", SANS, 700))
    o.append(text(1326, 753, "德惠西站", 24, TEXT, SANS, 500, anchor="start"))
    o.append(text(1310, 905, "龙凤采摘园", 23, "#3a9b3f", SANS, 500))
    o.append(text(1395, 800, "德惠市区", 30, "#8a8aa8", SANS, 700, extra=' letter-spacing="4"'))
    o.append(poi(1356, 834, "红旗大市场", "#a03cc8", "市"))
    o.append(poi(1556, 698, "王三姐绿色生态园", "#3a9b3f", "园"))

    # 行车箭头
    for pts, color, phase in LEGS:
        o.extend(leg_arrows(pts, color, phase))

    # 地点标记
    o.append(pin(*HOME, BLUE))
    o.append(text(250, 246, "新郎家", 56, BLUE, DISPLAY, 400, anchor="start",
                  halo="#ffffff"))
    o.append(text(252, 288, "中国石油万金塔派出所北加油站", 24, "#2b3f9e", SANS, 500,
                  anchor="start", halo="#fff7fa"))
    o.append(f'<rect x="108" y="206" width="70" height="32" rx="16" fill="{PINK}"/>'
             + text(143, 229, "起·终", 19, "#fff", SANS, 700))

    o.append(pin(*BRIDE, PINK))
    o.append(text(1212, 1240, "新娘家", 58, "#e8202c", DISPLAY, 400, anchor="start",
                  halo="#ffffff"))
    o.append(text(1356, 1238, "腰周家", 32, "#c2185b", SANS, 700, anchor="start",
                  halo="#fff3f7"))

    o.append(pin(*GOV, ORANGE, "★"))
    o.append(text(1664, 970, "德惠市人民政府", 34, "#d35400", SANS, 900, halo="#ffffff"))

    # 标题与路线摘要
    o.append(heart(612, 86, 38, PINK, -18, .85))
    o.append(heart(1188, 86, 38, PINK, 18, .85))
    o.append(text(900, 136, "婚车路线图", 104, "#e8202c", DISPLAY, 400, halo="#ffffff",
                  extra=' letter-spacing="10" filter="url(#soft)"'))
    o.append(text(900, 194, "万金塔加油站 → 腰周家 → 德惠市人民政府 → 万金塔加油站", 26,
                  "#c2185b", SANS, 500))

    # 指北针
    cx, cy = 1615, 150
    o.append(text(cx, 78, "北", 36, "#333", SANS, 900))
    o.append(f'<g stroke="{PINK}" stroke-width="12" stroke-linecap="round">'
             f'<line x1="{cx}" y1="{cy - 50}" x2="{cx}" y2="{cy + 50}"/>'
             f'<line x1="{cx - 42}" y1="{cy}" x2="{cx + 42}" y2="{cy}"/></g>')
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        r = 50 if dx == 0 else 42
        tipx, tipy = cx + dx * (r + 14), cy + dy * (r + 14)
        bx, by = cx + dx * (r - 8), cy + dy * (r - 8)
        tri = [(tipx, tipy), (bx - dy * 17, by + dx * 17), (bx + dy * 17, by - dx * 17)]
        o.append(f'<polygon points="{pts_attr(tri)}" fill="{PINK}"/>')

    # 图例
    o.append(text(1604, 262, "图 例", 34, "#333", SANS, 900))
    o.append('<rect x="1436" y="280" width="336" height="182" rx="14" fill="#ffffff" '
             f'fill-opacity=".7" stroke="{PINK}" stroke-width="2.5"/>')
    for i, (label, color) in enumerate((("去新娘家", PINK), ("去德惠市人民政府", ORANGE),
                                        ("回新郎家", BLUE))):
        y = 326 + i * 56
        o.append(arrow(1490, y, 1, 0, color, length=78, shaft=14, head=30, half=17))
        o.append(text(1542, y + 9, label, 25, "#333", SANS, 700, anchor="start"))

    # 信息卡：地图以外的内容都收在这一张卡片里
    phone = INFO["phone"]
    top, bottom = 490, 1212 + (48 if phone else 0)
    o.append(f'<rect x="50" y="{top}" width="860" height="{bottom - top}" rx="28" '
             f'fill="#ffffff" fill-opacity=".8" stroke="#ffc1d4" stroke-width="2" '
             f'filter="url(#soft)"/>')

    # 左栏：囍、新人、日期
    ex, ey = 250, 662
    o.append(f'<circle cx="{ex}" cy="{ey}" r="80" fill="url(#seal)" stroke="#f6c453" '
             f'stroke-width="6"/>'
             f'<circle cx="{ex}" cy="{ey}" r="67" fill="none" stroke="#f6c453" '
             f'stroke-width="2" stroke-dasharray="5 5"/>')
    o.append(text(ex, ey + 36, "囍", 100, "#ffd96a", SANS, 900))
    for x, role, name, color in ((150, "新郎", INFO["groom"], BLUE),
                                 (350, "新娘", INFO["bride"], "#e8202c")):
        o.append(text(x, 796, role, 22, "#b07a8c", SANS, 500))
        o.append(text(x, 854, name, 46, color, BRUSH, 400))
    o.append(heart(ex, 840, 22, PINK))
    o.append(f'<line x1="170" y1="898" x2="330" y2="898" stroke="#ffc1d4" stroke-width="2"/>')
    o.append(text(ex, 970, INFO["date"], 58, "#e8202c", SANS, 900))
    o.append(text(ex, 1016, INFO["lunar"], 26, "#e8457a", SANS, 500))

    o.append('<line x1="470" y1="540" x2="470" y2="1080" stroke="#ffc1d4" stroke-width="2" '
             'stroke-dasharray="8 8"/>')

    # 右栏：时间安排（时间轴）
    o.append(text(690, 588, "时间安排", 46, "#e8202c", DISPLAY, 400,
                  extra=' letter-spacing="6"'))
    ys = [655 + i * 112 for i in range(len(INFO["schedule"]))]
    o.append(f'<line x1="522" y1="{ys[0]}" x2="522" y2="{ys[-1]}" stroke="#ffc1d4" '
             f'stroke-width="4"/>')
    for y, (t, what, note) in zip(ys, INFO["schedule"]):
        o.append(f'<circle cx="522" cy="{y}" r="11" fill="{PINK}" stroke="#fff" '
                 f'stroke-width="4"/>')
        o.append(text(552, y + 12, t, 34, "#e8202c", SANS, 900, anchor="start"))
        o.append(text(552, y + 54, what, 28, "#333", SANS, 500, anchor="start"))
        if note:
            o.append(text(552, y + 88, note, 22, "#9a7f88", SANS, 400, anchor="start"))

    # 底部：结束语
    o.append('<line x1="110" y1="1116" x2="850" y2="1116" stroke="#ffc1d4" stroke-width="2"/>')
    o.append(text(480, 1176, INFO["thanks"], 32, "#e8457a", SANS, 700))
    if phone:
        o.append(text(480, 1224, f"如有问题请联系：{phone}", 30, "#e8457a", SANS, 700))

    # 装饰爱心
    o.append(heart(1700, 1196, 84, "#ff9ab8", 14, .7))
    o.append(heart(1620, 1240, 46, "#ffb3c9", -10, .8))
    o.append(heart(60, 70, 54, "#ffb3c9", -12, .7))
    o.append(heart(120, 125, 30, "#ff9ab8", 10, .7))

    o.append("</svg>")
    return "\n".join(o)


def build_html(svg, fonts_dir):
    links = ""
    if fonts_dir:
        css = ["noto-sans-sc/400.css", "noto-sans-sc/500.css", "noto-sans-sc/700.css",
               "noto-sans-sc/900.css", "zcool-qingke-huangyou/400.css",
               "ma-shan-zheng/400.css"]
        links = "\n".join(f'<link rel="stylesheet" href="file://{os.path.join(fonts_dir, c)}">'
                          for c in css)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>婚车路线图</title>{links}
<style>html,body{{margin:0;padding:0;background:#fff}}svg{{display:block}}</style>
</head><body>{svg}</body></html>"""


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", help="@fontsource 目录（node_modules/@fontsource）")
    ap.add_argument("--png", action="store_true", help="用 Chromium 渲染 PNG")
    ap.add_argument("--chrome",
                    default="/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell")
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--out", default=here)
    args = ap.parse_args()

    svg = build_svg()
    svg_path = os.path.join(args.out, "wedding_route_map.svg")
    html_path = os.path.join(args.out, "wedding_route_map.html")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_html(svg, args.fonts and os.path.abspath(args.fonts)))
    print("wrote", svg_path)

    if args.png:
        png_path = os.path.join(args.out, "wedding_route_map.png")
        subprocess.run([args.chrome, "--no-sandbox", "--disable-gpu",
                        "--hide-scrollbars", "--allow-file-access-from-files",
                        f"--force-device-scale-factor={args.scale}",
                        f"--window-size={W},{H}", "--virtual-time-budget=15000",
                        f"--screenshot={png_path}", "file://" + html_path],
                       check=True, stderr=subprocess.DEVNULL)
        print("wrote", png_path)


if __name__ == "__main__":
    main()
