"""Post-process renders: annotate the plan view and export finished JPGs.

    python annotate.py            # reads renders/*.png, writes renders/final/*.jpg
"""
import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "renders")
OUT = os.path.join(SRC, "final")
CJK = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"

# must match scene.py
PLAN_C, PLAN_SCALE = (1.85, 1.95), 15.6
GX0, GY0, GW, GL = -0.8, -2.0, 5.6, 9.0

CAPTIONS = {
    "hero": "智慧农场 · 走廊开口入口透视",
    "terrace": "智慧农场 · 西南角人视",
    "terrace_e": "智慧农场 · 东南角人视",
    "aerial": "智慧农场 · 整体鸟瞰",
    "interior": "智慧农场 · 室内效果",
    "dusk": "智慧农场 · 夜景效果",
    "hero_dusk": "智慧农场 · 入口夜景",
}

LEGEND = [
    ((2.0, -2.35), "入口门头（发光字“智慧农场”）+ 推拉玻璃门"),
    ((2.0, -4.75), "走廊栏杆开口 + 防滑木塑台阶（3级）+ 不锈钢扶手/护栏门"),
    ((-0.9, -2.6), "木塑栈道 / 入口平台"),
    ((4.05, -2.75), "黄杨球景观花箱 ×2"),
    ((3.4, -3.9), "观赏草花箱 ×2"),
    ((0.2, 0.15), "气雾栽培立柱 ×6（约 250 株）"),
    ((0.25, 3.75), "A 字形管道水培架 ×2（约 130 株）"),
    ((3.55, 2.4), "班级责任田种植箱 ×4（1.6 m × 1.2 m）"),
    ((2.0, 2.5), "中央通道 1.8 m（可容一个小组）"),
    ((2.0, 6.35), "智慧大屏 55\" + 教学台"),
    ((0.2, 6.55), "育苗架（三层 + LED 补光）"),
    ((3.8, 6.55), "水肥一体机 + 营养液罐"),
    ((-2.4, 2.3), "小型气象站（温湿度/光照/风速）"),
    ((-3.45, 5.5), "户外花箱 ×3（自然课观察区）"),
    ((-2.95, -0.4), "户外课堂木塑长凳 ×2"),
    ((7.0, 4.5), "人造草坪（保护原屋面防水）"),
    ((5.05, 1.0), "白色鹅卵石排水带"),
    ((-3.0, 8.85), "原有展板 → 更新为科普展板"),
]


def font(size):
    return ImageFont.truetype(CJK, size, index=0)


def w2p(x, y, W, H):
    return ((x - PLAN_C[0]) / PLAN_SCALE * W + W / 2, H / 2 - (y - PLAN_C[1]) / PLAN_SCALE * W)


def dim_line(d, p0, p1, label, f, offset=(0, 0)):
    d.line([p0, p1], fill=(255, 255, 255), width=4)
    for p in (p0, p1):
        d.ellipse((p[0] - 7, p[1] - 7, p[0] + 7, p[1] + 7), fill=(255, 255, 255))
    mx, my = (p0[0] + p1[0]) / 2 + offset[0], (p0[1] + p1[1]) / 2 + offset[1]
    tw = d.textlength(label, font=f)
    d.rounded_rectangle((mx - tw / 2 - 12, my - 24, mx + tw / 2 + 12, my + 24), 10, fill=(20, 60, 40))
    d.text((mx, my), label, font=f, fill=(255, 255, 255), anchor="mm")


def plan():
    src = os.path.join(SRC, "plan.png")
    if not os.path.exists(src):
        return
    im = Image.open(src).convert("RGB")
    W, H = im.size
    pw = int(W * 0.8)
    sheet = Image.new("RGB", (W + pw, H), (250, 250, 247))
    sheet.paste(im, (0, 0))
    d = ImageDraw.Draw(sheet)
    fs = max(18, W // 60)
    # numbered markers
    for i, ((x, y), _) in enumerate(LEGEND, 1):
        px, py = w2p(x, y, W, H)
        r = fs * 0.85
        d.ellipse((px - r, py - r, px + r, py + r), fill=(214, 92, 40), outline=(255, 255, 255), width=3)
        d.text((px, py), str(i), font=font(int(fs * 1.0)), fill=(255, 255, 255), anchor="mm")
    # dimensions of the greenhouse
    f = font(int(fs * 1.05))
    dim_line(d, w2p(GX0, GY0 + GL + 0.75, W, H), w2p(GX0 + GW, GY0 + GL + 0.75, W, H), "5.6 m", f)
    dim_line(d, w2p(GX0 + GW + 0.85, GY0, W, H), w2p(GX0 + GW + 0.85, GY0 + GL, W, H), "9.0 m", f)

    # legend panel: pick the largest font that fits the longest line
    x0 = W + 60
    avail = pw - 120
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    lf = 60
    longest = max([lab for _, lab in LEGEND], key=len)
    while lf > 12 and probe.textlength(longest, font=font(lf)) + lf * 2.6 > avail:
        lf -= 1
    nf = 60
    note = ["顶部（平面未示）：电动天窗 ×4、LED 补光灯带、喷雾降温管线、监控摄像头",
            "现场无尺寸，平面为示意；施工前需现场复尺并复核屋面荷载与防水"]
    while nf > 10 and probe.textlength(max(note, key=len), font=font(nf)) > avail:
        nf -= 1
    d.text((x0, 95), "智慧农场  平面布置图", font=font(int(fs * 2.1)), fill=(25, 60, 40), anchor="lm")
    d.text((x0, 95 + fs * 2.6), "温室 5.6 m × 9.0 m ≈ 50 ㎡ ｜ 檐高 2.8 m ｜ 脊高 4.1 m", font=font(lf),
           fill=(90, 90, 90), anchor="lm")
    top = 95 + fs * 4.0
    d.line((x0, top, W + pw - 60, top), fill=(200, 200, 195), width=2)
    y = top + lf * 2.0
    step = (H - 230 - y) / (len(LEGEND) - 0.5)
    for i, (_, label) in enumerate(LEGEND, 1):
        r = lf * 0.75
        d.ellipse((x0, y - r, x0 + 2 * r, y + r), fill=(214, 92, 40))
        d.text((x0 + r, y), str(i), font=font(int(lf * 0.85)), fill=(255, 255, 255), anchor="mm")
        d.text((x0 + 2 * r + lf * 0.8, y), label, font=font(lf), fill=(40, 40, 40), anchor="lm")
        y += step
    d.line((x0, H - 170, W + pw - 60, H - 170), fill=(200, 200, 195), width=2)
    for k, t in enumerate(note):
        d.text((x0, H - 130 + k * nf * 1.8), t, font=font(nf), fill=(110, 110, 110), anchor="lm")
    # scale bar (5 m)
    sx0, sy0 = fs * 3, H - fs * 3
    sx1 = sx0 + 5 / PLAN_SCALE * W
    d.rounded_rectangle((sx0 - fs, sy0 - fs * 2.6, sx1 + fs * 1.6, sy0 + fs * 1.2), fs // 2, fill=(255, 255, 255))
    for k in range(5):
        a = sx0 + k / 5 * (sx1 - sx0)
        b = sx0 + (k + 1) / 5 * (sx1 - sx0)
        d.rectangle((a, sy0 - fs * 0.35, b, sy0 + fs * 0.35), fill=(30, 30, 30) if k % 2 == 0 else (255, 255, 255),
                    outline=(30, 30, 30), width=2)
    d.text((sx0, sy0 - fs * 1.4), "0", font=font(fs), fill=(30, 30, 30), anchor="mm")
    d.text((sx1, sy0 - fs * 1.4), "5 m", font=font(fs), fill=(30, 30, 30), anchor="mm")
    d.text(w2p(5.6, -5.45, W, H), "教学楼走廊", font=font(fs), fill=(60, 60, 60), anchor="mm")
    os.makedirs(OUT, exist_ok=True)
    sheet.save(os.path.join(OUT, "06_plan.jpg"), quality=92)


def finish(name, out_name):
    src = os.path.join(SRC, f"{name}.png")
    if not os.path.exists(src):
        return
    im = Image.open(src).convert("RGB")
    im = ImageEnhance.Contrast(im).enhance(1.04)
    im = ImageEnhance.Color(im).enhance(1.08)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=45, threshold=2))
    W, H = im.size
    # subtle vignette
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse((-W * 0.25, -H * 0.3, W * 1.25, H * 1.3), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(W // 8))
    dark = ImageEnhance.Brightness(im).enhance(0.86)
    im = Image.composite(im, dark, mask)
    cap = CAPTIONS.get(name)
    if cap:
        d = ImageDraw.Draw(im, "RGBA")
        fs = max(16, W // 70)
        f = font(fs)
        tw = d.textlength(cap, font=f)
        pad = fs * 0.6
        x, y = fs * 1.2, H - fs * 2.6
        d.rounded_rectangle((x, y, x + tw + 2 * pad, y + fs + 2 * pad), radius=fs // 2, fill=(0, 0, 0, 110))
        d.text((x + pad, y + pad + fs / 2), cap, font=f, fill=(255, 255, 255, 235), anchor="lm")
    os.makedirs(OUT, exist_ok=True)
    im.save(os.path.join(OUT, out_name), quality=92)


if __name__ == "__main__":
    order = ["hero", "terrace", "terrace_e", "aerial", "interior", "dusk", "hero_dusk"]
    num = {"hero": "01", "terrace": "02", "terrace_e": "03", "aerial": "04", "interior": "05",
           "dusk": "07", "hero_dusk": "08"}
    for n in order:
        finish(n, f"{num[n]}_{n}.jpg")
    plan()
    print("written to", OUT)
