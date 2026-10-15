"""Finish the v2 images: title badges, callouts (montages, placed by projecting 3D anchors
through the calibrated cameras) and the annotated plan.

    python annotate_v2.py
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.environ.get("V2_RENDERS", os.path.join(HERE, "renders"))
FINAL = os.path.join(R, "final")
CJK = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
CAL = json.load(open(os.path.join(HERE, "calib.json")))
GREEN = (24, 58, 44)
GOLD = (198, 160, 88)
ORANGE = (214, 110, 50)
NAME = "智慧农业科普展厅"
L, W = 17.8, 8.5
PHASE1_X = 11.8


def font(s):
    return ImageFont.truetype(CJK, int(s), index=0)


def project(name, X):
    c = CAL["cams"][name]
    rv = np.array(c["rv"])
    th = np.linalg.norm(rv)
    k = rv / th
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    Rm = np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K
    Xc = Rm @ np.array(X, float) + np.array(c["tv"])
    w, h = c["size"]
    return c["f"] * Xc[0] / Xc[2] + w / 2, c["f"] * Xc[1] / Xc[2] + h / 2


def badge(im, title, sub):
    d = ImageDraw.Draw(im, "RGBA")
    W_, H_ = im.size
    s = max(W_, H_) / 1900
    x0, y0 = int(28 * s), int(28 * s)
    ft, fs = font(44 * s), font(24 * s)
    tw = max(d.textlength(title, font=ft), d.textlength(sub, font=fs))
    d.rounded_rectangle((x0, y0, x0 + tw + 56 * s, y0 + 122 * s), radius=int(10 * s), fill=GREEN + (235,))
    d.rectangle((x0, y0, x0 + 8 * s, y0 + 122 * s), fill=GOLD)
    d.text((x0 + 30 * s, y0 + 44 * s), title, font=ft, fill=(250, 246, 236), anchor="lm")
    d.text((x0 + 30 * s, y0 + 92 * s), sub, font=fs, fill=(220, 226, 218), anchor="lm")


def footer(im, text):
    d = ImageDraw.Draw(im, "RGBA")
    W_, H_ = im.size
    s = max(W_, H_) / 1900
    f = font(20 * s)
    tw = d.textlength(text, font=f)
    x1, y1 = W_ - 24 * s, H_ - 24 * s
    d.rounded_rectangle((x1 - tw - 28 * s, y1 - 40 * s, x1, y1), radius=int(8 * s), fill=(255, 255, 255, 215))
    d.text((x1 - 14 * s, y1 - 20 * s), text, font=f, fill=(70, 70, 70), anchor="rm")


def callout(im, anchor, label, sub, off):
    d = ImageDraw.Draw(im, "RGBA")
    W_, H_ = im.size
    s = max(W_, H_) / 1900
    ax, ay = anchor
    bx, by = ax + off[0] * W_, ay + off[1] * H_
    fl, fs = font(28 * s), font(19 * s)
    tw = max(d.textlength(label, font=fl), d.textlength(sub, font=fs) if sub else 0)
    bw, bh = tw + 40 * s, (78 if sub else 50) * s
    bx = min(max(bx, 12 * s), W_ - bw - 12 * s)
    by = min(max(by, 170 * s), H_ - bh - 80 * s)
    ex = bx if ax < bx else bx + bw
    d.line((ax, ay, ex, by + bh / 2), fill=(255, 255, 255, 230), width=max(2, int(2.5 * s)))
    r = 7 * s
    d.ellipse((ax - r, ay - r, ax + r, ay + r), fill=(255, 255, 255, 255), outline=GOLD, width=max(2, int(3 * s)))
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=int(8 * s), fill=(255, 255, 255, 238))
    d.rectangle((bx, by, bx + 6 * s, by + bh), fill=GOLD)
    d.text((bx + 20 * s, by + 25 * s), label, font=fl, fill=(25, 35, 30), anchor="lm")
    if sub:
        d.text((bx + 20 * s, by + 58 * s), sub, font=fs, fill=(95, 100, 95), anchor="lm")


def grade(im):
    im = ImageEnhance.Contrast(im).enhance(1.03)
    return im.filter(ImageFilter.UnsharpMask(radius=1.0, percent=35, threshold=2))


MONTAGES = {
    "p_platform": ("实景效果图 · 视角一（站在抬高平台上看）", [
        ((0.25, 5.0, 0.95), "种子萌发观察窗", "坎内玻璃封面，与坎齐平", (-0.30, 0.10)),
        ((7.0, 8.45, 2.0), "沿街推拉玻璃窗", "可开启通风", (-0.05, -0.20)),
        ((9.0, 4.25, 3.0), "单坡屋面", "走廊侧高 3.35 m，沿街侧低 2.6 m", (0.05, -0.15)),
        ((17.8, 4.7, 9.0), "红墙大字", "白色立体字", (-0.40, -0.13)),
        ((2.7, 5.4, 1.4), "气雾栽培塔", "", (0.05, 0.12)),
        ((4.0, 7.8, 0.75), "班级种植箱", "按年级认领", (-0.10, 0.10)),
        ((17.6, 4.25, 2.1), "红墙展示墙", "数据大屏 · 成长时间轴 · 照片墙", (0.10, 0.03)),
    ], "示意效果，基于现场照片合成，尺寸以实测为准"),
    "p_corr_across": ("实景效果图 · 视角二（走廊看展厅）", [
        ((3.5, 0.04, 1.5), "栏杆外玻璃封闭", "保留原不锈钢栏杆", (0.05, 0.16)),
        ((7.0, 0.65, 1.3), "立体水培架", "LED 补光，走廊可直接看到", (0.03, -0.12)),
        ((5.5, 1.0, 3.25), "单坡屋面", "走廊侧高、沿街侧低", (0.02, -0.20)),
        ((0.3, 4.2, 0.92), "种子萌发观察窗", "", (0.02, -0.25)),
    ], "示意效果，基于现场照片合成，尺寸以实测为准"),
    "p_corr_far": ("实景效果图 · 视角三（走廊看入口方向）", [
        ((14.0, -0.36, 2.9), "门头主标识 + 入口", "走廊最后一跨开门，紧挨百叶格栅", (-0.25, 0.30)),
        ((16.6, -0.12, 1.4), "百叶格栅植物观察窗", "朝展厅一侧封玻璃，灯带 + 盆栽", (-0.02, 0.22)),
        ((5.0, 0.65, 1.5), "立体水培架", "", (0.05, -0.20)),
        ((2.0, 0.04, 1.0), "栏杆外玻璃封闭", "", (0.06, 0.12)),
    ], "示意效果，基于现场照片合成，尺寸以实测为准"),
}

VIEWS3D = {
    "corridor": "效果图 · 走廊入口（右侧为百叶格栅植物观察窗）",
    "interior_in": "室内效果图 · 从入口看向坎边",
    "interior_wall": "室内效果图 · 红墙展示墙与讲解区",
    "germ": "室内效果图 · 种子萌发观察窗",
    "aerial": "鸟瞰效果图",
    "louver_corner": "实景效果图 · 走廊尽头百叶窗（植物观察窗）",
}

ORDER = [("p_platform", "01"), ("p_corr_across", "02"), ("p_corr_far", "03"), ("corridor", "04"),
         ("interior_in", "05"), ("interior_wall", "06"), ("germ", "07"), ("louver_corner", "08"),
         ("aerial", "09")]


LEGEND = [
    ((14.3, -0.45), "入口：走廊最后一跨开门（紧挨格栅），双开玻璃门 + 门头标识"),
    ((12.95, -0.95), "入口立牌（走廊侧）"),
    ((16.6, -0.12), "百叶格栅：朝展厅一侧封玻璃，灯带 + 盆栽观察"),
    ((4.0, 0.0), "走廊栏杆外加玻璃，封到屋面"),
    ((6.0, W + 0.15), "沿街推拉玻璃窗"),
    ((0.2, 4.25), "种子萌发观察窗（坎内玻璃封面，与坎齐平）"),
    ((6.45, 0.65), "立体水培架 ×4（LED 补光）"),
    ((2.7, 4.25), "气雾栽培塔 ×4"),
    ((12.75, 4.25), "气雾栽培塔 ×2"),
    ((6.1, 4.25), "鱼菜共生展示缸"),
    ((10.6, 4.25), "研学操作台 ×2（12 座）"),
    ((6.8, 7.8), "班级种植箱 ×8（每箱 1.4 × 0.9 m）"),
    ((15.1, 4.35), "科普讲解区（20 座）"),
    ((17.45, 2.0), "红墙展示墙：大屏 · 时间轴 · 照片墙 · 植物墙"),
    ((12.6, 0.6), "育苗架（三层 LED）"),
    ((16.9, 7.85), "水肥一体机 + 营养液罐"),
]


def plan():
    src = os.path.join(R, "plan.png")
    if not os.path.exists(src):
        return
    im = Image.open(src).convert("RGB")
    Wp, Hp = im.size
    scale = Wp / 20.5                      # px per metre (ortho_scale = 20.5)
    cx, cy = L / 2 - 0.6, W / 2 - 0.3

    def w2p(x, y):
        return (Wp / 2 + (x - cx) * scale, Hp / 2 - (y - cy) * scale)

    pad_top, pad_bot = 260, 120
    side = 1250
    sheet = Image.new("RGB", (Wp + side, Hp + pad_top + pad_bot), (247, 246, 241))
    sheet.paste(im, (0, pad_top))
    d = ImageDraw.Draw(sheet, "RGBA")

    def P(x, y):
        a, b = w2p(x, y)
        return a, b + pad_top

    d.text((60, 80), NAME, font=font(76), fill=GREEN, anchor="lm")
    d.text((60, 160), "平面布置图 · 展厅 17.8 m × 8.5 m，单坡屋面（走廊侧高、沿街侧低）", font=font(36),
           fill=(110, 110, 105), anchor="lm")
    d.rectangle((60, 200, 300, 207), fill=GOLD)
    # dimensions
    def dim(p0, p1, label, vertical=False):
        d.line((p0, p1), fill=(60, 60, 60), width=3)
        for p in (p0, p1):
            if vertical:
                d.line((p[0] - 14, p[1], p[0] + 14, p[1]), fill=(60, 60, 60), width=3)
            else:
                d.line((p[0], p[1] - 14, p[0], p[1] + 14), fill=(60, 60, 60), width=3)
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        f = font(34)
        tw = d.textlength(label, font=f)
        d.rounded_rectangle((mx - tw / 2 - 14, my - 26, mx + tw / 2 + 14, my + 26), radius=8, fill=(255, 255, 255, 240))
        d.text((mx, my), label, font=f, fill=(40, 40, 40), anchor="mm")
    dim(P(0.0, W + 0.75), P(L, W + 0.75), "17.8 m（坎 → 红墙）")
    dim(P(-1.0, 0.0), P(-1.0, W), "8.5 m", vertical=True)
    # numbered markers
    for i, ((x, y), _) in enumerate(LEGEND, 1):
        px, py = P(x, y)
        r = 24
        d.ellipse((px - r, py - r, px + r, py + r), fill=ORANGE + (255,), outline=(255, 255, 255), width=4)
        d.text((px, py), str(i), font=font(26), fill="white", anchor="mm")
    d.text(P(8.5, -0.6), "教学楼走廊", font=font(30), fill=(70, 70, 70), anchor="mm")
    d.text(P(-0.95, 7.4), "抬高平台", font=font(30), fill=(70, 70, 70), anchor="mm")
    d.text(P(8.5, W + 0.35), "沿街围墙（保留原宣传栏）", font=font(26), fill=(70, 70, 70), anchor="mm")
    # legend column
    lx = Wp + 60
    d.text((lx, pad_top + 10), "功能分区", font=font(48), fill=GREEN, anchor="lm")
    y = pad_top + 90
    step = (Hp - 120) / len(LEGEND)
    for i, (_, label) in enumerate(LEGEND, 1):
        d.ellipse((lx, y - 22, lx + 44, y + 22), fill=ORANGE)
        d.text((lx + 22, y), str(i), font=font(24), fill="white", anchor="mm")
        d.text((lx + 66, y), label, font=font(30), fill=(40, 40, 40), anchor="lm")
        y += step
    d.text((60, Hp + pad_top + 60), "示意图，尺寸以现场实测为准",
           font=font(30), fill=(110, 110, 105), anchor="lm")
    os.makedirs(FINAL, exist_ok=True)
    sheet.save(os.path.join(FINAL, "10_plan.jpg"), quality=92)


def main():
    os.makedirs(FINAL, exist_ok=True)
    for name, num in ORDER:
        if name in MONTAGES:
            src = os.path.join(R, f"comp_{name}.jpg")
        elif name == "louver_corner":
            src = os.path.join(R, "louver_corner.jpg")
        else:
            src = os.path.join(R, f"{name}.png")
        if not os.path.exists(src):
            print("skip", name)
            continue
        im = grade(Image.open(src).convert("RGB"))
        if name in MONTAGES:
            sub, calls, note = MONTAGES[name]
            sx = im.size[0] / CAL["cams"][name]["size"][0]
            for X, lab, s2, off in calls:
                u, v = project(name, X)
                callout(im, (u * sx, v * sx), lab, s2, off)
            badge(im, NAME, sub)
            footer(im, note)
        else:
            badge(im, NAME, VIEWS3D[name])
            footer(im, "示意效果，尺寸以实测为准" if name != "louver_corner" else "示意效果，基于现场照片合成")
        im.save(os.path.join(FINAL, f"{num}_{name}.jpg"), quality=92)
    plan()
    sb = os.path.join(R, "signage_board.jpg")
    if os.path.exists(sb):
        Image.open(sb).save(os.path.join(FINAL, "11_signage.jpg"), quality=92)
    print("done:", sorted(os.listdir(FINAL)))


if __name__ == "__main__":
    main()
