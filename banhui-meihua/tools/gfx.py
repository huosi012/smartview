"""Shared drawing helpers and palette for the 队伍侦探社 design assets."""
import math, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONTS = os.path.expanduser('~/.fonts')
F_KUAILE = f'{FONTS}/ZCOOLKuaiLe-Regular.ttf'
F_SANS = f'{FONTS}/NotoSansSC-Regular.otf'
F_SANS_B = f'{FONTS}/NotoSansSC-Bold.otf'
F_SANS_K = f'{FONTS}/NotoSansSC-Black.otf'
F_KAI = f'{FONTS}/LXGWWenKai-Regular.ttf'
F_EMOJI = '/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf'

# palette (taken from the character reference: navy vest line + yellow cap line)
NAVY = (11, 75, 155)
NAVY_D = (16, 46, 100)
YELLOW = (255, 204, 57)
YELLOW_L = (255, 238, 176)
YELLOW_BG = (255, 233, 160)
ORANGE = (240, 138, 36)
ORANGE_D = (214, 110, 20)
SKY = (220, 234, 251)
SKY_L = (236, 244, 253)
CREAM = (255, 253, 247)
WHITE = (255, 255, 255)
INK = (43, 43, 43)
# 知 情 意 行 stage colours
ST_BLUE = (61, 139, 224)
ST_ORANGE = (242, 153, 74)
ST_GREEN = (52, 179, 126)
ST_CORAL = (238, 106, 95)
STAGES = [ST_BLUE, ST_ORANGE, ST_GREEN, ST_CORAL]


def font(path, size):
    return ImageFont.truetype(path, int(size))


FALLBACK = F_SANS_B
FORCE_FALLBACK = set('—')
_glyph_cache = {}


def has_glyph(path, ch):
    key = (path, ch)
    if key not in _glyph_cache:
        f = font(path, 40)
        if ch.isspace():
            _glyph_cache[key] = True
        else:
            m = f.getmask(ch)
            nd = f.getmask('\ue000')
            _glyph_cache[key] = not (m.size == nd.size and bytes(m) == bytes(nd))
    return _glyph_cache[key]


def tint(c, k):
    """mix colour c with white; k=0 -> c, k=1 -> white"""
    return tuple(int(c[i] + (255 - c[i]) * k) for i in range(3))


def shade(c, k):
    return tuple(int(c[i] * (1 - k)) for i in range(3))


def rgba(c, a=255):
    return (c[0], c[1], c[2], a)


class Canvas:
    """Draw at K x resolution, export downsampled for antialiasing."""

    def __init__(self, w, h, bg=(0, 0, 0, 0), k=2):
        self.w, self.h, self.k = w, h, k
        self.im = Image.new('RGBA', (w * k, h * k), bg)
        self.d = ImageDraw.Draw(self.im)

    def s(self, v):
        return int(round(v * self.k))

    def box(self, b):
        return [self.s(v) for v in b]

    # ---------- shapes
    def rrect(self, b, r, fill=None, outline=None, width=0):
        self.d.rounded_rectangle(self.box(b), radius=self.s(r), fill=fill, outline=outline, width=self.s(width))

    def ellipse(self, b, fill=None, outline=None, width=0):
        self.d.ellipse(self.box(b), fill=fill, outline=outline, width=self.s(width))

    def circle(self, cx, cy, r, **kw):
        self.ellipse([cx - r, cy - r, cx + r, cy + r], **kw)

    def line(self, pts, fill, width, joint='curve'):
        self.d.line([(self.s(x), self.s(y)) for x, y in pts], fill=fill, width=self.s(width), joint=joint)

    def poly(self, pts, fill=None, outline=None, width=0):
        self.d.polygon([(self.s(x), self.s(y)) for x, y in pts], fill=fill, outline=outline, width=self.s(width) if width else 1)

    def dashed(self, pts, fill, width, dash=14, gap=10, round_cap=True):
        """dashed polyline through pts"""
        seg = []
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            seg.append((x1, y1, x2, y2))
        on, left = True, dash
        for x1, y1, x2, y2 in seg:
            L = math.hypot(x2 - x1, y2 - y1)
            if L == 0:
                continue
            pos = 0
            while pos < L:
                step = min(left, L - pos)
                ax, ay = x1 + (x2 - x1) * pos / L, y1 + (y2 - y1) * pos / L
                bx, by = x1 + (x2 - x1) * (pos + step) / L, y1 + (y2 - y1) * (pos + step) / L
                if on:
                    self.line([(ax, ay), (bx, by)], fill, width)
                    if round_cap:
                        for px, py in ((ax, ay), (bx, by)):
                            self.circle(px, py, width / 2, fill=fill)
                pos += step
                left -= step
                if left <= 0:
                    on = not on
                    left = dash if on else gap

    def dashed_rrect(self, b, r, fill, width, dash=16, gap=10):
        x0, y0, x1, y1 = b
        pts = []
        n = 6
        corners = [(x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)]
        pts.append((x0 + r, y0))
        for cx, cy, a0 in corners:
            if a0 == -90:
                pts.append((x1 - r, y0))
            elif a0 == 0:
                pts.append((x1, y1 - r))
            elif a0 == 90:
                pts.append((x0 + r, y1))
            else:
                pts.append((x0, y0 + r))
            for i in range(1, n + 1):
                a = math.radians(a0 + 90 * i / n)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        pts.append((x0 + r, y0))
        self.dashed(pts, fill, width, dash, gap)

    def star(self, cx, cy, r, fill, outline=None, width=0, rot=-90, inner=0.48):
        pts = []
        for i in range(10):
            rr = r if i % 2 == 0 else r * inner
            a = math.radians(rot + i * 36)
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        if outline:
            self.poly(pts, fill=fill)
            self.line(pts + [pts[0]], outline, width)
        else:
            self.poly(pts, fill=fill)

    def plus(self, cx, cy, r, fill, width):
        self.line([(cx - r, cy), (cx + r, cy)], fill, width)
        self.line([(cx, cy - r), (cx, cy + r)], fill, width)
        for px, py in ((cx - r, cy), (cx + r, cy), (cx, cy - r), (cx, cy + r)):
            self.circle(px, py, width / 2, fill=fill)

    def sparkle(self, cx, cy, r, fill):
        pts = []
        for i in range(8):
            rr = r if i % 2 == 0 else r * 0.22
            a = math.radians(-90 + i * 45)
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        self.poly(pts, fill=fill)

    def footprint(self, cx, cy, size, angle, fill):
        """one small shoe print, angle in degrees (0 = pointing up)"""
        layer = Canvas(int(size * 1.4), int(size * 2.2), k=self.k)
        u = size
        layer.ellipse([0.25 * u, 0.15 * u, 1.15 * u, 1.35 * u], fill=fill)  # sole
        layer.ellipse([0.38 * u, 1.45 * u, 1.02 * u, 2.05 * u], fill=fill)  # heel
        img = layer.im.rotate(-angle, resample=Image.BICUBIC, expand=True)
        self.im.alpha_composite(img, (self.s(cx) - img.width // 2, self.s(cy) - img.height // 2))

    # ---------- text
    def runs(self, s, fnt_path):
        """split text into (chunk, font) runs, falling back for glyphs the font lacks"""
        out = []
        for ch in s:
            fp = fnt_path if (has_glyph(fnt_path, ch) and ch not in FORCE_FALLBACK) else FALLBACK
            if out and out[-1][1] == fp:
                out[-1][0] += ch
            else:
                out.append([ch, fp])
        return out

    def text(self, xy, s, fnt_path, size, fill, anchor='la', stroke=0, stroke_fill=None, spacing=0):
        rs = self.runs(s, fnt_path)
        if len(rs) > 1 and not spacing:
            tw = sum(self.text_w(t, fp, size) for t, fp in rs)
            x, y = xy
            if anchor[0] == 'm':
                x -= tw / 2
            elif anchor[0] == 'r':
                x -= tw
            for t, fp in rs:
                self.text((x, y), t, fp, size, fill, anchor='l' + anchor[1], stroke=stroke, stroke_fill=stroke_fill)
                x += self.text_w(t, fp, size)
            return
        f = font(fnt_path, self.s(size))
        x, y = xy
        if spacing:
            # manual letter spacing
            tw = self.text_w(s, fnt_path, size, spacing)
            if anchor[0] == 'm':
                x -= tw / 2
            elif anchor[0] == 'r':
                x -= tw
            a2 = 'l' + anchor[1]
            for ch in s:
                self.d.text((self.s(x), self.s(y)), ch, font=f, fill=fill, anchor=a2,
                            stroke_width=self.s(stroke), stroke_fill=stroke_fill)
                x += self.text_w(ch, fnt_path, size) + spacing
            return
        self.d.text((self.s(x), self.s(y)), s, font=f, fill=fill, anchor=anchor,
                    stroke_width=self.s(stroke), stroke_fill=stroke_fill)

    def text_w(self, s, fnt_path, size, spacing=0):
        rs = self.runs(s, fnt_path)
        if len(rs) > 1:
            return sum(self.text_w(t, fp, size) for t, fp in rs) + spacing * max(0, len(s) - 1)
        fnt_path = rs[0][1] if rs else fnt_path
        f = font(fnt_path, self.s(size))
        return self.d.textlength(s, font=f) / self.k + spacing * max(0, len(s) - 1)

    def wrap(self, s, fnt_path, size, maxw):
        """greedy CJK wrap keeping closing punctuation off line starts"""
        lines, cur = [], ''
        no_start = '，。、；：！？）”’》」'
        for ch in s:
            if self.text_w(cur + ch, fnt_path, size) > maxw and cur:
                if ch in no_start:
                    cur += ch
                    lines.append(cur)
                    cur = ''
                    continue
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        return lines

    def emoji(self, ch, cx, cy, size):
        f = ImageFont.truetype(F_EMOJI, 109)
        tmp = Image.new('RGBA', (150, 150), (0, 0, 0, 0))
        ImageDraw.Draw(tmp).text((10, 10), ch, font=f, embedded_color=True)
        tmp = tmp.crop(tmp.getbbox())
        sc = self.s(size) / max(tmp.size)
        tmp = tmp.resize((max(1, int(tmp.width * sc)), max(1, int(tmp.height * sc))), Image.LANCZOS)
        self.im.alpha_composite(tmp, (self.s(cx) - tmp.width // 2, self.s(cy) - tmp.height // 2))

    # ---------- compositing
    def paste(self, img, x, y, w=None, h=None):
        """paste an RGBA image at final-res coords, optional resize (final-res)"""
        if w or h:
            if w and not h:
                h = img.height * w / img.width
            if h and not w:
                w = img.width * h / img.height
            img = img.resize((self.s(w), self.s(h)), Image.LANCZOS)
        self.im.alpha_composite(img, (self.s(x), self.s(y)))

    def shadow(self, b, r, color=(0, 0, 0, 60), blur=12, off=(0, 6)):
        layer = Image.new('RGBA', self.im.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle(
            [self.s(b[0] + off[0]), self.s(b[1] + off[1]), self.s(b[2] + off[0]), self.s(b[3] + off[1])],
            radius=self.s(r), fill=color)
        layer = layer.filter(ImageFilter.GaussianBlur(self.s(blur)))
        self.im.alpha_composite(layer)

    def export(self):
        return self.im.resize((self.w, self.h), Image.LANCZOS)

    def save(self, path, rgb_bg=None, **kw):
        out = self.export()
        if rgb_bg is not None:
            bg = Image.new('RGB', out.size, rgb_bg)
            bg.paste(out, mask=out.split()[3])
            out = bg
        out.save(path, **kw)
        return out


def magnifier(c, cx, cy, r, ring=NAVY, lens=(214, 233, 252), handle=YELLOW, angle=45, ring_w=None):
    """magnifying glass icon centered on the lens"""
    ring_w = ring_w or r * 0.28
    a = math.radians(angle)
    hx0, hy0 = cx + (r + ring_w * 0.3) * math.cos(a), cy + (r + ring_w * 0.3) * math.sin(a)
    hx1, hy1 = cx + (r * 2.15) * math.cos(a), cy + (r * 2.15) * math.sin(a)
    c.line([(hx0, hy0), (hx1, hy1)], ring, ring_w * 1.25)
    c.circle(hx1, hy1, ring_w * 0.62, fill=ring)
    mx0, my0 = cx + (r * 1.35) * math.cos(a), cy + (r * 1.35) * math.sin(a)
    c.line([(mx0, my0), (hx1, hy1)], handle, ring_w * 0.95)
    c.circle(hx1, hy1, ring_w * 0.47, fill=handle)
    c.circle(cx, cy, r, fill=lens)
    c.circle(cx, cy, r, outline=ring, width=ring_w)
    # glint
    c.d.arc(c.box([cx - r * 0.62, cy - r * 0.62, cx + r * 0.62, cy + r * 0.62]), 200, 260,
            fill=WHITE, width=c.s(ring_w * 0.45))


def person(c, cx, base_y, h, color, tilt=0):
    """little queue-person magnet: head + rounded body, base at base_y"""
    w = h * 0.62
    body_top = base_y - h * 0.62
    layer = Canvas(int(w * 1.6) + 4, int(h * 1.3) + 4, k=c.k)
    ox, oy = (w * 1.6 + 4) / 2, h * 1.3 + 2
    layer.rrect([ox - w / 2, oy - h * 0.62, ox + w / 2, oy], w * 0.42, fill=rgba(color))
    layer.circle(ox, oy - h * 0.62 - h * 0.2, h * 0.2, fill=rgba(color))
    layer.circle(ox - h * 0.07, oy - h * 0.84, h * 0.03, fill=(255, 255, 255, 230))
    layer.circle(ox + h * 0.07, oy - h * 0.84, h * 0.03, fill=(255, 255, 255, 230))
    img = layer.im
    if tilt:
        img = img.rotate(tilt, resample=Image.BICUBIC, expand=True)
    c.im.alpha_composite(img, (c.s(cx) - img.width // 2, c.s(base_y) - img.height + c.s(2)))


def bead_line(c, x0, x1, y, n=9, line_c=NAVY, r=12, lw=5):
    cols = [ST_CORAL, YELLOW, ST_BLUE, ST_GREEN, ORANGE]
    c.line([(x0, y), (x1, y)], line_c, lw)
    for i in range(n):
        x = x0 + (x1 - x0) * (i + 0.5) / n
        c.circle(x, y, r + 4, fill=WHITE)
        c.circle(x, y, r, fill=cols[i % len(cols)])
