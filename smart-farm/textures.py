"""Generate image textures used by the Blender scene (dashboard screen, bulletin boards).

Run with any Python that has Pillow:  python3 textures.py
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "tex")
CJK = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"


def font(size):
    return ImageFont.truetype(CJK, size, index=0)


def rounded(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def dashboard(path):
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / H
        c = (int(6 + 8 * t), int(20 + 26 * t), int(42 + 40 * t))
        for x in range(W):
            px[x, y] = c
    d = ImageDraw.Draw(img)

    # Title bar
    d.polygon([(0, 0), (W, 0), (W, 96), (1260, 96), (1220, 120), (700, 120), (660, 96), (0, 96)], fill=(10, 52, 90))
    d.text((W // 2, 58), "智慧农场 · 环境监测与智能控制平台", font=font(52), fill=(225, 245, 255), anchor="mm")
    d.text((40, 48), "2026-10-14  星期三  10:30", font=font(28), fill=(140, 200, 235), anchor="lm")
    d.text((W - 40, 48), "多云  22°C  东南风2级", font=font(28), fill=(140, 200, 235), anchor="rm")

    def panel(x0, y0, x1, y1, title):
        rounded(d, (x0, y0, x1, y1), 14, fill=(9, 38, 70), outline=(40, 140, 210), width=2)
        d.rectangle((x0 + 18, y0 + 22, x0 + 26, y0 + 50), fill=(60, 220, 160))
        d.text((x0 + 40, y0 + 36), title, font=font(30), fill=(210, 238, 255), anchor="lm")

    # Left KPI panel
    panel(30, 150, 610, 1050, "实时环境数据")
    kpis = [
        ("空气温度", "24.6", "°C", (255, 170, 80)),
        ("空气湿度", "68", "%RH", (90, 190, 255)),
        ("光照强度", "32580", "lux", (255, 225, 90)),
        ("CO₂ 浓度", "465", "ppm", (150, 230, 140)),
        ("基质湿度", "42", "%", (120, 220, 255)),
        ("营养液 EC", "1.8", "mS/cm", (200, 160, 255)),
        ("营养液 pH", "6.2", "", (110, 240, 200)),
    ]
    for i, (name, val, unit, col) in enumerate(kpis):
        y = 220 + i * 118
        rounded(d, (55, y, 585, y + 100), 10, fill=(12, 50, 88))
        d.ellipse((75, y + 22, 131, y + 78), outline=col, width=5)
        d.text((150, y + 50), name, font=font(30), fill=(170, 210, 235), anchor="lm")
        d.text((470, y + 50), val, font=font(48), fill=col, anchor="rm")
        d.text((480, y + 54), unit, font=font(24), fill=(150, 190, 215), anchor="lm")

    # Center chart
    panel(640, 150, 1300, 640, "24小时温湿度曲线")
    cx0, cy0, cx1, cy1 = 690, 230, 1270, 600
    for i in range(6):
        y = cy0 + i * (cy1 - cy0) / 5
        d.line((cx0, y, cx1, y), fill=(30, 70, 110), width=1)
    random.seed(3)
    temps = [18 + 7 * math.sin((h - 8) / 24 * 2 * math.pi) + random.uniform(-0.6, 0.6) for h in range(25)]
    hums = [70 - 14 * math.sin((h - 8) / 24 * 2 * math.pi) + random.uniform(-2, 2) for h in range(25)]

    def series(vals, lo, hi, col):
        pts = [(cx0 + i * (cx1 - cx0) / 24, cy1 - (v - lo) / (hi - lo) * (cy1 - cy0)) for i, v in enumerate(vals)]
        poly = pts + [(cx1, cy1), (cx0, cy1)]
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).polygon(poly, fill=col + (60,))
        img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))
        d2 = ImageDraw.Draw(img)
        d2.line(pts, fill=col, width=5, joint="curve")

    series(hums, 30, 100, (80, 180, 255))
    series(temps, 0, 40, (255, 160, 70))
    d = ImageDraw.Draw(img)
    for i, lab in enumerate(["0时", "6时", "12时", "18时", "24时"]):
        d.text((cx0 + i * (cx1 - cx0) / 4, cy1 + 22), lab, font=font(22), fill=(140, 180, 210), anchor="mm")

    # Center bottom: crop growth
    panel(640, 670, 1300, 1050, "作物生长进度")
    crops = [("生菜（一年级）", 0.78, "第21天"), ("草莓（二年级）", 0.55, "开花期"),
             ("小白菜（三年级）", 0.64, "第18天"), ("罗勒（四年级）", 0.42, "第12天"),
             ("气雾栽培塔", 0.86, "可采收")]
    for i, (n, p, s) in enumerate(crops):
        y = 750 + i * 60
        d.text((670, y), n, font=font(26), fill=(200, 230, 250), anchor="lm")
        rounded(d, (900, y - 12, 1180, y + 12), 12, fill=(20, 60, 100))
        rounded(d, (900, y - 12, 900 + int(280 * p), y + 12), 12, fill=(60, 210, 150))
        d.text((1275, y), s, font=font(24), fill=(120, 230, 180), anchor="rm")

    # Right: device status + camera tiles
    panel(1330, 150, 1890, 640, "设备运行状态")
    devs = [("水肥一体机", "运行中"), ("电动顶窗", "开启 30%"), ("环流风机", "运行中"),
            ("LED 补光灯", "定时 18:00"), ("喷雾降温", "待机"), ("视频监控", "4路在线")]
    for i, (n, s) in enumerate(devs):
        y = 235 + i * 66
        d.ellipse((1360, y - 10, 1380, y + 10), fill=(60, 230, 140))
        d.text((1400, y), n, font=font(28), fill=(200, 230, 250), anchor="lm")
        d.text((1860, y), s, font=font(26), fill=(120, 230, 180), anchor="rm")
    panel(1330, 670, 1890, 1050, "实时监控画面")
    random.seed(7)
    for i in range(4):
        x0 = 1355 + (i % 2) * 265
        y0 = 735 + (i // 2) * 155
        tile = Image.new("RGB", (250, 140))
        tp = tile.load()
        g0 = random.uniform(0.6, 1.0)
        for yy in range(140):
            for xx in range(250):
                n = math.sin(xx * 0.09 + i) * math.cos(yy * 0.12 + i * 2)
                tp[xx, yy] = (int(40 + 30 * n), int((110 + 50 * n) * g0), int(50 + 20 * n))
        img.paste(tile.filter(ImageFilter.GaussianBlur(2)), (x0, y0))
        d.text((x0 + 8, y0 + 8), f"CAM-0{i + 1}", font=font(18), fill=(255, 255, 255))
    img.save(path, quality=92)


def board(path, title, subtitle, accent, seed):
    W, H = 2400, 900
    img = Image.new("RGB", (W, H), (248, 248, 242))
    d = ImageDraw.Draw(img)
    random.seed(seed)
    d.rectangle((0, 0, W, 170), fill=accent)
    d.text((70, 88), title, font=font(96), fill=(255, 255, 255), anchor="lm")
    d.text((W - 70, 92), subtitle, font=font(48), fill=(255, 255, 230), anchor="rm")
    cols = 4
    cw = (W - 100) / cols
    for c in range(cols):
        x0 = 50 + c * cw + 20
        x1 = x0 + cw - 40
        hue = [(110, 180, 90), (240, 170, 60), (90, 160, 220), (220, 110, 100)][c]
        rounded(d, (x0, 220, x1, 520), 18, fill=tuple(int(v * 0.85 + 30) for v in hue))
        for k in range(5):
            cx = x0 + random.uniform(40, x1 - x0 - 40)
            cy = 260 + random.uniform(20, 220)
            r = random.uniform(25, 70)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=tuple(min(255, int(v * 1.15)) for v in hue))
        for k in range(7):
            y = 560 + k * 44
            w = random.uniform(0.6, 1.0) * (x1 - x0)
            d.rounded_rectangle((x0, y, x0 + w, y + 16), radius=8, fill=(150, 150, 150))
    img.save(path, quality=90)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    dashboard(os.path.join(OUT, "dashboard.jpg"))
    board(os.path.join(OUT, "board1.jpg"), "智慧农业科普长廊", "认识无土栽培", (46, 140, 80), 1)
    board(os.path.join(OUT, "board2.jpg"), "劳动教育 · 快乐成长", "种植日记展示", (34, 120, 170), 2)
    board(os.path.join(OUT, "board3.jpg"), "二十四节气与农事", "春种 · 夏长 · 秋收 · 冬藏", (200, 110, 40), 3)
    print("textures written to", OUT)
