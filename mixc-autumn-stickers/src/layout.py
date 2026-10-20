"""Builds the layered SVG for each sticker: background image, outlined text, logo.

The SVGs open directly in Illustrator (File > Open, then Save As .ai). The
artboard is the trim size in mm; the background image runs 20 mm past every
edge as bleed, the same way the summer .ai file was set up.

usage: python3 layout.py <font_dir> <out_dir> [v1|v2]   (out_dir must contain backgrounds/)

v1 = red-brown macro leaf, v2 = 大兴安岭 autumn forest. Only the colours of a few
elements differ between them, depending on what sits behind.
"""
import re
import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
LOGO_DIR = ROOT / "assets" / "logo-preview"
BLEED = 20  # mm

INK = "#3b1a10"    # deep brown for text and logo on light areas
CREAM = "#f6e3c8"  # logo marks sitting on the leaf

# Screenshot of the summer file: trim box origins (px) and mm per px.
MM_PER_PX = 2.72
TRIM_ORIGIN = {"A": (144.5, 101.5), "B": (738.5, 101.5), "C": (144.5, 323.5), "D": (583.5, 323.5)}


class Font:
    def __init__(self, path: Path):
        self.tt = TTFont(path)
        self.upem = self.tt["head"].unitsPerEm
        self.cap = self.tt["OS/2"].sCapHeight / self.upem
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.hb = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))

    def shape(self, text, features=None):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, features or {})
        return [(self.order[i.codepoint], p.x_advance, p.x_offset, p.y_offset)
                for i, p in zip(buf.glyph_infos, buf.glyph_positions)]

    def path(self, text, size, x, baseline, anchor="start", tracking=0.0, features=None, sx=1.0):
        """Outline `text` as an SVG path. size in mm, tracking in em."""
        glyphs = self.shape(text, features)
        k = size / self.upem
        width = (sum(a for _, a, _, _ in glyphs) * k + tracking * size * (len(glyphs) - 1)) * sx
        x0 = {"start": x, "middle": x - width / 2, "end": x - width}[anchor]
        pen = SVGPathPen(self.glyphs, ntos=lambda v: f"{v:.2f}")
        cx = 0.0
        for name, adv, xo, yo in glyphs:
            t = (k * sx, 0, 0, -k, x0 + (cx + xo * k) * sx, baseline - yo * k)
            self.glyphs[name].draw(TransformPen(pen, t))
            cx += adv * k + tracking * size
        return pen.getCommands(), width


def logo(name, color, scale, ox, oy, opacity=1.0):
    """Place a traced logo SVG (units = screenshot px x 10) at mm offset."""
    svg = (LOGO_DIR / f"{name}.svg").read_text()
    d = svg.split(' d="', 1)[1].split('"', 1)[0]
    return dict(kind="path", id=name, d=d, fill=color, evenodd=True, opacity=opacity, tf=(scale, ox, oy))


def logo_at_crop(name, design, crop_x, crop_y, color, rel=1.0, ink_offset=(0, 0), opacity=1.0):
    """Place a trace whose crop started at screenshot px (crop_x, crop_y)."""
    tx, ty = TRIM_ORIGIN[design]
    s = MM_PER_PX / 10 * rel
    ox = (crop_x - tx) * MM_PER_PX - ink_offset[0] * s
    oy = (crop_y - ty) * MM_PER_PX - ink_offset[1] * s
    return logo(name, color, s, ox, oy, opacity)


def p(d, color=INK):
    return dict(kind="path", d=d, fill=color, evenodd=False, opacity=1.0, tf=None)


def rect(x, y, w, h, color=INK):
    return dict(kind="rect", x=x, y=y, w=w, h=h, fill=color)


def build(fonts, variant="v1"):
    v2 = variant == "v2"
    en, en_semi, cn, cn_med = fonts["Outfit-700"], fonts["Outfit-600"], fonts["NotoSansSC-700"], fonts["NotoSansSC-500"]
    en_size = 73 / en.cap  # cap height 73 mm, as in the summer file
    designs = {}

    # ---- A 150x45: headline + 中文
    text = [
        # slightly smaller than summer's 73 mm cap height: "warmth" is longer than "cool"
        p(en.path("Herbs.", 66 / en.cap, 72, 163)[0]),
        p(en.path("Inherent warmth.", 66 / en.cap, 72, 241)[0]),
        p(cn.path("本草之间，", 58, 1440, 306, anchor="end", features={"halt": True})[0]),
        p(cn.path("自有暖意。", 58, 1440, 374, anchor="end", features={"halt": True})[0]),
    ]
    designs["A"] = (1500, 450, text, [])

    # ---- B 150x45: knot icons + brand lockup
    logos = [
        # v1: icons sit on the leaf; v2: on the sky
        logo_at_crop("icons", "B", 774, 122, INK if v2 else CREAM, opacity=1 if v2 else 0.92),
        logo_at_crop("callig", "B", 1072, 210, INK),
        p(cn_med.path("®", 22, 1083, 333)[0]),
        # small seal: same trace as the big one at 0.385x, ink box starts at (60, 29) units
        logo_at_crop("seal", "B", 1152, 217.75, INK, rel=0.385, ink_offset=(60, 29)),
    ]
    # 佛|慈|康|选 with thin dividers, FOCI HEALTH underneath
    x, size = 1226, 34
    for i, ch in enumerate("佛慈康选"):
        d, w = cn.path(ch, size, x, 358)
        logos.append(p(d))
        x += w
        if i < 3:
            logos.append(rect(round(x + 6.5, 2), 331, 2.2, 24))
            x += 15.2
    d, w = en_semi.path("FOCI HEALTH", 22.5, 1258, 388, tracking=0.04)
    logos.append(p(d))
    designs["B"] = (1500, 450, [], logos)

    # ---- C 110x50: three stacked phrases on rules + Foci health
    text = [
        # v2: on the dark hillside, so cream
        p(en.path("Foci", en_size, 50, 371)[0], CREAM if v2 else INK),
        p(en.path("health", en_size, 50, 456)[0], CREAM if v2 else INK),
    ]
    for word, right, rule_x0, rule_x1, base, rule_y in [
        ("秋收", 970, 279, 1000, 182, 189.5),
        ("冬藏", 1000, 309, 1029, 255, 262.5),
        ("温养", 1029, 341, 1062, 328, 335.5),
    ]:
        text.append(p(cn.path(word, 48, right, base, anchor="end", tracking=0.42)[0]))
        text.append(rect(rule_x0, rule_y, rule_x1 - rule_x0, 2))
    designs["C"] = (1100, 500, text, [])

    # ---- D 110x50: big 慈 seal centred
    designs["D"] = (1100, 500, [], [logo_at_crop("seal", "D", 740, 375, INK)])
    return designs


SIZES = {"A": "150x45", "B": "150x45", "C": "110x50", "D": "110x50"}


# ---------------------------------------------------------------- SVG
def svg_el(e):
    if e["kind"] == "rect":
        return f'<rect fill="{e["fill"]}" x="{e["x"]}" y="{e["y"]}" width="{e["w"]}" height="{e["h"]}"/>'
    attrs = f' id="{e["id"]}"' if "id" in e else ""
    if e["evenodd"]:
        attrs += ' fill-rule="evenodd"'
    if e["opacity"] < 1:
        attrs += f' opacity="{e["opacity"]}"'
    if e["tf"]:
        sc, ox, oy = e["tf"]
        attrs += f' transform="translate({ox:.2f} {oy:.2f}) scale({sc:.5f})"'
    return f'<path fill="{e["fill"]}"{attrs} d="{e["d"]}"/>'


def write_svg(out: Path, key, w, h, text, logos, bg_href):
    body = lambda els: "\n    ".join(svg_el(e) for e in els)
    out.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">
  <title>MixC autumn sticker {key} {SIZES[key]}cm</title>
  <g id="Background">
    <image x="{-BLEED}" y="{-BLEED}" width="{w + 2 * BLEED}" height="{h + 2 * BLEED}" preserveAspectRatio="none" xlink:href="{bg_href}"/>
  </g>
  <g id="Text">
    {body(text)}
  </g>
  <g id="Logo">
    {body(logos)}
  </g>
</svg>
''')


# ---------------------------------------------------------------- PDF
TOKEN = re.compile(r"[MLHVCQZ]|-?[\d.]+(?:e-?\d+)?")


def pdf_path(c, d, tf):
    """Absolute M/L/H/V/C/Q/Z SVG path -> reportlab path (quadratics become cubics)."""
    sc, ox, oy = tf or (1, 0, 0)
    P = lambda x, y: (ox + x * sc, oy + y * sc)
    path = c.beginPath()
    toks = TOKEN.findall(d)
    i, cmd, cur, start = 0, None, (0, 0), (0, 0)
    num = lambda: float(toks[i])
    while i < len(toks):
        if toks[i].isalpha():
            cmd = toks[i]
            i += 1
            if cmd == "Z":
                path.close()
                cur = start
                continue
        vals = []
        need = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "Q": 4}[cmd]
        for _ in range(need):
            vals.append(float(toks[i]))
            i += 1
        if cmd == "M":
            cur = start = (vals[0], vals[1])
            path.moveTo(*P(*cur))
            cmd = "L"  # implicit lineto after moveto
        elif cmd in "LHV":
            cur = (vals[0], vals[1]) if cmd == "L" else ((vals[0], cur[1]) if cmd == "H" else (cur[0], vals[0]))
            path.lineTo(*P(*cur))
        elif cmd == "C":
            path.curveTo(*P(vals[0], vals[1]), *P(vals[2], vals[3]), *P(vals[4], vals[5]))
            cur = (vals[4], vals[5])
        elif cmd == "Q":
            (qx, qy), (ex, ey) = (vals[0], vals[1]), (vals[2], vals[3])
            c1 = (cur[0] + 2 / 3 * (qx - cur[0]), cur[1] + 2 / 3 * (qy - cur[1]))
            c2 = (ex + 2 / 3 * (qx - ex), ey + 2 / 3 * (qy - ey))
            path.curveTo(*P(*c1), *P(*c2), *P(ex, ey))
            cur = (ex, ey)
    return path


def write_pdf(out: Path, key, w, h, text, logos, bg_jpg: Path):
    """Print PDF: page = trim + 20 mm bleed, TrimBox = trim, vectors stay vectors."""
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    W, H = (w + 2 * BLEED) * mm, (h + 2 * BLEED) * mm
    c = canvas.Canvas(str(out), pagesize=(W, H))
    c.setTitle(f"MixC autumn sticker {key} {SIZES[key]}cm")
    c.setTrimBox((BLEED * mm, BLEED * mm, (BLEED + w) * mm, (BLEED + h) * mm))
    c.setBleedBox((0, 0, W, H))
    c.drawImage(str(bg_jpg), 0, 0, width=W, height=H)
    # switch to the SVG coordinate system: mm, origin at the trim's top-left, y down
    c.transform(mm, 0, 0, -mm, BLEED * mm, (BLEED + h) * mm)
    for e in text + logos:
        c.setFillColor(HexColor(e["fill"]), alpha=e.get("opacity", 1))
        if e["kind"] == "rect":
            c.rect(e["x"], e["y"], e["w"], e["h"], stroke=0, fill=1)
        else:
            c.drawPath(pdf_path(c, e["d"], e["tf"]), stroke=0, fill=1, fillMode=0 if e["evenodd"] else 1)
    c.showPage()
    c.save()


def main(font_dir, out_dir, variant="v1"):
    fonts = {n: Font(Path(font_dir) / f"{n}.ttf") for n in ["Outfit-700", "Outfit-600", "NotoSansSC-700", "NotoSansSC-500"]}
    out = Path(out_dir)
    (out / "layered").mkdir(parents=True, exist_ok=True)
    (out / "pdf").mkdir(parents=True, exist_ok=True)
    for key, (w, h, text, logos) in build(fonts, variant).items():
        name = f"{key}_{SIZES[key]}cm"
        bg = f"bg_{name}.jpg"
        write_svg(out / "layered" / f"{name}.svg", key, w, h, text, logos, f"../backgrounds/{bg}")
        write_pdf(out / "pdf" / f"{name}.pdf", key, w, h, text, logos, out / "backgrounds" / bg)
        print(name)


if __name__ == "__main__":
    main(*sys.argv[1:4])
