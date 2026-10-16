"""2D graphics for the v2 science hall: red-wall timeline, photo-wall placeholders,
entrance totem, and the signage design board.

    python3 textures_v2.py
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "tex")
OUT = os.path.join(HERE, "renders")
CJK = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
LAT = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"

GREEN = (31, 77, 58)
GREEN_D = (20, 52, 39)
GOLD = (198, 160, 88)
CREAM = (247, 245, 238)
NAME = "智慧农业科普展厅"
NAME_EN = "SMART AGRICULTURE SCIENCE HALL"


def f(size, latin=False):
    return ImageFont.truetype(LAT if latin else CJK, size, index=0) if not latin else ImageFont.truetype(LAT, size)


def logo(d, cx, cy, r, col=GOLD, width=None):
    """Circle + sprout + three sensor dots."""
    w = width or max(2, r // 9)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=w)
    d.line((cx, cy + r * 0.62, cx, cy - r * 0.05), fill=col, width=w)
    d.chord((cx - r * 0.62, cy - r * 0.55, cx + r * 0.02, cy + r * 0.05), 200, 380, fill=col)
    d.chord((cx - r * 0.02, cy - r * 0.75, cx + r * 0.62, cy - r * 0.15), 160, 340, fill=col)
    for k, ang in enumerate((-35, 0, 35)):
        a = math.radians(ang + 90)
        px, py = cx + math.cos(a) * r * 0.62, cy + math.sin(a) * r * 0.62
        d.line((cx, cy + r * 0.62, px, py), fill=col, width=max(1, w // 2))
        d.ellipse((px - w, py - w, px + w, py + w), fill=col)


def stage_icon(d, cx, base, s, stage):
    soil = (120, 84, 52)
    d.rounded_rectangle((cx - s, base, cx + s, base + s * 0.5), radius=int(s * 0.12), fill=soil)
    leaf = (120, 200, 90)
    stem = (90, 160, 70)
    if stage == 0:
        d.ellipse((cx - s * 0.18, base + s * 0.12, cx + s * 0.18, base + s * 0.34), fill=(230, 200, 140))
    if stage >= 1:
        d.ellipse((cx - s * 0.18, base + s * 0.12, cx + s * 0.18, base + s * 0.34), fill=(210, 180, 120))
        d.line((cx, base + s * 0.2, cx - s * 0.1, base + s * 0.46), fill=(240, 235, 220), width=max(2, int(s * 0.04)))
    if stage >= 2:
        for dx in (-0.25, 0.0, 0.22):
            d.line((cx, base + s * 0.25, cx + dx * s, base + s * 0.48), fill=(245, 240, 225), width=max(2, int(s * 0.03)))
        h = s * (0.25 if stage == 2 else 0.5 if stage == 3 else 0.8)
        d.line((cx, base, cx, base - h), fill=stem, width=max(3, int(s * 0.06)))
    if stage >= 2:
        n = {2: 1, 3: 1, 4: 2, 5: 3}[stage]
        h = s * (0.25 if stage == 2 else 0.5 if stage == 3 else 0.8)
        for k in range(n):
            y = base - h + k * s * 0.22
            ls = s * (0.25 + 0.12 * k + (0.15 if stage >= 4 else 0))
            d.ellipse((cx - ls * 1.4, y - ls * 0.35, cx, y + ls * 0.35), fill=leaf)
            d.ellipse((cx, y - ls * 0.35, cx + ls * 1.4, y + ls * 0.35), fill=leaf)
    if stage == 5:
        d.ellipse((cx - s * 0.55, base - s * 1.05, cx + s * 0.55, base - s * 0.25), fill=(140, 210, 100))
        d.ellipse((cx - s * 0.35, base - s * 0.95, cx + s * 0.35, base - s * 0.35), fill=(170, 225, 120))


def timeline(path):
    W, H = 4200, 900
    img = Image.new("RGB", (W, H), GREEN)
    d = ImageDraw.Draw(img)
    for i in range(0, W, 14):
        d.line((i, 0, i, H), fill=(34, 82, 62), width=6)
    d.rectangle((0, 0, W, 170), fill=GREEN_D)
    logo(d, 120, 85, 58)
    d.text((220, 85), "从一粒种子到一棵菜", font=f(96), fill=CREAM, anchor="lm")
    d.text((W - 80, 85), "观察 · 记录 · 发现", font=f(56), fill=GOLD, anchor="rm")
    stages = [("种子", "第 1 天", "吸水膨胀"), ("萌发", "第 3 天", "胚根伸出"), ("生根", "第 5 天", "根系向下"),
              ("出苗", "第 7 天", "子叶展开"), ("长叶", "第 15 天", "真叶生长"), ("收获", "第 30 天", "成熟采收")]
    n = len(stages)
    xs = [int(W * (k + 0.5) / n) for k in range(n)]
    d.line((xs[0], 700, xs[-1], 700), fill=GOLD, width=8)
    for k, (a, b, c) in enumerate(stages):
        x = xs[k]
        d.ellipse((x - 150, 250, x + 150, 550), fill=(246, 243, 232))
        stage_icon(d, x, 430, 110, k)
        d.ellipse((x - 18, 682, x + 18, 718), fill=GOLD)
        d.text((x, 600), a, font=f(64), fill=CREAM, anchor="mm")
        d.text((x, 770), b, font=f(48), fill=GOLD, anchor="mm")
        d.text((x, 840), c, font=f(40), fill=(200, 220, 205), anchor="mm")
    img.save(path, quality=92)


def photo_placeholder(path, seed):
    random.seed(seed)
    W, H = 900, 640
    img = Image.new("RGB", (W, H))
    px = img.load()
    base = random.choice([(70, 130, 60), (90, 150, 80), (60, 110, 70), (120, 160, 90)])
    sky = random.random() < 0.5
    for y in range(H):
        for x in range(W):
            t = y / H
            if sky and t < 0.35:
                c = (190 + int(30 * t), 210, 225)
            else:
                n = math.sin(x * 0.03 + seed) * math.cos(y * 0.025 + seed * 2)
                c = (int(base[0] + 30 * n), int(base[1] + 40 * n), int(base[2] + 20 * n))
            px[x, y] = c
    d = ImageDraw.Draw(img)
    for k in range(random.randint(2, 4)):
        cx, cy = random.uniform(150, 750), random.uniform(330, 520)
        d.ellipse((cx - 40, cy - 120, cx + 40, cy - 40), fill=(235, 190, 150))
        d.rounded_rectangle((cx - 60, cy - 40, cx + 60, cy + 120), radius=30,
                            fill=random.choice([(230, 90, 70), (60, 120, 200), (240, 200, 60), (250, 250, 250)]))
    img = img.filter(ImageFilter.GaussianBlur(5))
    d = ImageDraw.Draw(img)
    d.rectangle((0, H - 70, W, H), fill=(0, 0, 0))
    d.text((W / 2, H - 35), "照片位 · 学校提供", font=f(34), fill=(235, 235, 235), anchor="mm")
    img.save(path, quality=88)


def totem(path):
    W, H = 600, 1800
    img = Image.new("RGB", (W, H), GREEN)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 560), fill=GREEN_D)
    logo(d, W // 2, 170, 110)
    d.text((W // 2, 360), "智慧农业", font=f(92), fill=CREAM, anchor="mm")
    d.text((W // 2, 470), "科普展厅", font=f(92), fill=CREAM, anchor="mm")
    d.text((W // 2, 610), "SCIENCE HALL", font=f(40, True), fill=GOLD, anchor="mm")
    d.rectangle((60, 680, W - 60, 684), fill=GOLD)
    d.text((W // 2, 770), "参观入口", font=f(72), fill=CREAM, anchor="mm")
    d.line((180, 870, 420, 870), fill=GOLD, width=10)
    d.polygon([(420, 845), (470, 870), (420, 895)], fill=GOLD)
    d.rectangle((40, 960, W - 40, 1640), fill=CREAM)
    d.text((W // 2, 1030), "参观须知", font=f(54), fill=GREEN_D, anchor="mm")
    for k, t in enumerate(["轻声慢行", "有序排队", "看护植物", "勿动设备", "爱护鱼儿"]):
        d.text((W // 2, 1130 + k * 95), t, font=f(46), fill=(60, 70, 60), anchor="mm")
    d.rectangle((0, 1700, W, H), fill=(150, 104, 72))
    img.save(path, quality=92)


def fascia(path):
    W, H = 2400, 400
    img = Image.new("RGB", (W, H), GREEN)
    d = ImageDraw.Draw(img)
    d.rectangle((0, H - 14, W, H), fill=GOLD)
    logo(d, 150, 190, 118)
    d.text((330, 160), NAME, font=f(170), fill=(250, 238, 210), anchor="lm")
    d.text((338, 300), NAME_EN, font=f(52, True), fill=GOLD, anchor="lm")
    img.save(path, quality=93)


def signage_board(path):
    """Design board: fascia sign + entrance totem + red-wall letters, with sizes."""
    W, H = 3000, 1900
    img = Image.new("RGB", (W, H), (246, 245, 240))
    d = ImageDraw.Draw(img)
    d.text((120, 110), "室外标识设计", font=f(88), fill=GREEN_D, anchor="lm")
    d.text((120, 190), f"{NAME} · 门头主标识 / 入口立牌 / 红墙大字", font=f(44), fill=(110, 110, 105), anchor="lm")
    d.rectangle((120, 240, 360, 248), fill=GOLD)

    def label(x, y, n, t):
        d.ellipse((x, y - 26, x + 52, y + 26), fill=(198, 110, 50))
        d.text((x + 26, y), str(n), font=f(34), fill="white", anchor="mm")
        d.text((x + 72, y), t, font=f(46), fill=(40, 40, 40), anchor="lm")

    # 1 fascia
    label(120, 340, 1, "门头主标识（走廊开门处上方，面向走廊）")
    fx0, fy0, fx1, fy1 = 120, 400, 1980, 700
    d.rectangle((fx0 + 10, fy0 + 14, fx1 + 10, fy1 + 14), fill=(210, 208, 200))
    d.rectangle((fx0, fy0, fx1, fy1), fill=GREEN)
    d.rectangle((fx0, fy1 - 18, fx1, fy1), fill=GOLD)
    logo(d, fx0 + 160, (fy0 + fy1) // 2 - 6, 105)
    d.text((fx0 + 320, fy0 + 125), NAME, font=f(150), fill=(250, 238, 210), anchor="lm")
    d.text((fx0 + 326, fy0 + 235), NAME_EN, font=f(46, True), fill=GOLD, anchor="lm")
    d.line((fx0, fy1 + 60, fx1, fy1 + 60), fill=(90, 90, 90), width=3)
    for x in (fx0, fx1):
        d.line((x, fy1 + 45, x, fy1 + 75), fill=(90, 90, 90), width=3)
    d.text(((fx0 + fx1) // 2, fy1 + 100), "3600", font=f(40), fill=(90, 90, 90), anchor="mm")
    d.line((fx1 + 50, fy0, fx1 + 50, fy1), fill=(90, 90, 90), width=3)
    d.text((fx1 + 80, (fy0 + fy1) // 2), "600", font=f(40), fill=(90, 90, 90), anchor="lm")
    notes = ["底板：2 mm 铝板折边，墨绿色氟碳烤漆", "主字：不锈钢背发光字，暖白 LED（夜间可见）",
             "英文/线条：钛金拉丝不锈钢", "安装：门洞上方钢架，底边距地约 2.4 m"]
    for k, t in enumerate(notes):
        d.text((fx0, 880 + k * 62), "· " + t, font=f(40), fill=(70, 70, 70), anchor="lm")

    # 2 totem
    label(2150, 340, 2, "入口立牌（走廊侧，门旁）")
    t = Image.open(os.path.join(TEX, "totem.jpg")).resize((420, 1260))
    img.paste(t, (2260, 420))
    d.rectangle((2240, 1680, 2700, 1700), fill=(60, 60, 60))
    d.text((2470, 1740), "600 × 1800", font=f(40), fill=(90, 90, 90), anchor="mm")

    # 3 red wall letters
    label(120, 1180, 3, "红墙大字（展厅屋顶上方，远处和平台上都能看到）")
    rx0, ry0, rx1, ry1 = 120, 1240, 1980, 1700
    d.rectangle((rx0, ry0, rx1, ry1), fill=(140, 42, 38))
    d.rectangle((rx0, ry0 + 300, rx1, ry0 + 330), fill=(236, 230, 225))
    d.text(((rx0 + rx1) // 2, ry0 + 150), NAME, font=f(160), fill=(250, 250, 248), anchor="mm")
    d.text(((rx0 + rx1) // 2, ry0 + 400), "白色亚克力立体字 · 单字约 0.8 m · 打在原红墙上", font=f(40),
           fill=(250, 235, 230), anchor="mm")
    d.text((120, 1820), "标准色：墨绿 #1F4D3A ｜ 香槟金 #C6A058 ｜ 米白 #F7F5EE ｜ 木纹 #967048", font=f(38),
           fill=(110, 110, 105), anchor="lm")
    img.save(path, quality=92)


def germ_face(path):
    """Soil cross-section behind the glass of the kerb window: 6 stages, seeds to roots."""
    random.seed(11)
    W, H = 6000, 760
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        for x in range(W):
            t = y / H
            n = random.random()
            base = (92 - 25 * t, 62 - 18 * t, 40 - 12 * t)
            k = 0.85 + 0.3 * n
            px[x, y] = (int(base[0] * k), int(base[1] * k), int(base[2] * k))
    d = ImageDraw.Draw(img)
    for _ in range(2500):
        x, y = random.uniform(0, W), random.uniform(0, H)
        r = random.uniform(2, 6)
        c = random.choice([(150, 140, 120), (60, 40, 28), (170, 160, 140), (110, 80, 55)])
        d.ellipse((x - r, y - r, x + r, y + r), fill=c)
    cw = W / 6
    root = (238, 232, 214)
    for k in range(6):
        x0 = k * cw
        for j in range(4):
            sx = x0 + cw * (0.15 + 0.23 * j)
            sy = 140 + random.uniform(-15, 15)
            d.ellipse((sx - 16, sy - 10, sx + 16, sy + 10), fill=(214, 182, 120), outline=(150, 120, 70))
            if k >= 1:
                depth = [0, 60, 230, 380, 560, 700][k]
                for b in range(1 + k * 2):
                    px0, py0 = sx, sy + 8
                    ang = random.uniform(-0.5, 0.5)
                    length = depth * random.uniform(0.55, 1.0) if b else depth
                    steps = 12
                    for st in range(steps):
                        ang += random.uniform(-0.25, 0.25)
                        nx = px0 + math.sin(ang) * length / steps
                        ny = py0 + math.cos(ang) * length / steps
                        d.line((px0, py0, nx, ny), fill=root, width=max(1, int(5 - st * 0.35)))
                        px0, py0 = nx, ny
            if k >= 2:
                d.line((sx, sy - 8, sx + 3, 0), fill=(150, 190, 110), width=5)
        d.rectangle((x0 + cw - 6, 0, x0 + cw, H), fill=(230, 230, 225))
    img.save(path, quality=90)


def station_led(path):
    """Double-sided LED screen of the platform weather station: P10 red dot matrix, 160 x 80 dots (1.6 x 0.8 m)."""
    cols, rows, pitch = 160, 80, 12
    m = Image.new("L", (cols, rows), 0)
    d = ImageDraw.Draw(m)
    d.text((cols / 2, 9), "智慧农业气象站", font=f(16), fill=255, anchor="mm")
    d.line((6, 19, cols - 7, 19), fill=150)
    for k, (a, b) in enumerate((("温度", "26.5℃"), ("湿度", "62%RH"), ("风速", "1.8m/s"))):
        y = 32 + k * 17
        d.text((8, y), a, font=f(16), fill=255, anchor="lm")
        d.text((cols - 8, y), b, font=f(16), fill=255, anchor="rm")
    dots = m.point(lambda v: 255 if v > 110 else 0)
    img = Image.new("RGB", (cols * pitch, rows * pitch), (14, 8, 8))
    dd = ImageDraw.Draw(img)
    px = dots.load()
    r = pitch * 0.36
    for j in range(rows):
        for i in range(cols):
            cx, cy = (i + 0.5) * pitch, (j + 0.5) * pitch
            col = (255, 40, 22) if px[i, j] else (46, 14, 12)
            dd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    img.save(path)


if __name__ == "__main__":
    os.makedirs(TEX, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    timeline(os.path.join(TEX, "wall_timeline.jpg"))
    for i in range(6):
        photo_placeholder(os.path.join(TEX, f"photo{i}.jpg"), i + 3)
    totem(os.path.join(TEX, "totem.jpg"))
    germ_face(os.path.join(TEX, "germ_face.jpg"))
    fascia(os.path.join(TEX, "fascia.jpg"))
    station_led(os.path.join(TEX, "station_led.png"))
    signage_board(os.path.join(OUT, "signage_board.jpg"))
    print("ok")
