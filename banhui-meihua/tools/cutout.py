"""Cut the detective character out of the reference screenshot (cream bg + stray guide lines)."""
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageChops

src, out_full, out_head = sys.argv[1:4]
im = Image.open(src).convert('RGB')
w, h = im.size
px = im.load()


def near(c, ref, tol):
    return abs(c[0] - ref[0]) <= tol and abs(c[1] - ref[1]) <= tol and abs(c[2] - ref[2]) <= tol


mask = Image.new('L', (w, h), 0)
mp = mask.load()
for y in range(h):
    for x in range(w):
        c = px[x, y]
        bg = near(c, (255, 253, 247), 14)
        if not bg and 288 <= y <= 299 and near(c, (255, 204, 57), 45):
            bg = True  # yellow guide line
        if not bg and x <= 16 and near(c, (11, 75, 155), 60):
            bg = True  # blue guide line
        if bg:
            mp[x, y] = 255
# flood from the border: only background connected to the edge is removed
seeds = [(x, 0) for x in range(0, w, 3)] + [(x, h - 1) for x in range(0, w, 3)] + \
        [(0, y) for y in range(0, h, 3)] + [(w - 1, y) for y in range(0, h, 3)]
for s in seeds:
    if mp[s] == 255:
        ImageDraw.floodfill(mask, s, 128)
alpha = mask.point(lambda v: 0 if v == 128 else 255)
# soften the edge a little
alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.9))
rgba = im.convert('RGBA')
rgba.putalpha(alpha)
bbox = alpha.point(lambda v: 255 if v > 20 else 0).getbbox()
full = rgba.crop(bbox)
# upscale for print use
full = full.resize((full.width * 3, full.height * 3), Image.LANCZOS)
full.save(out_full)
print('full', full.size, bbox)

# head medallion source: square crop around cap + face
hx0, hy0, hx1, hy1 = 128, 22, 270, 164
head = im.crop((hx0, hy0, hx1, hy1)).resize((600, 600), Image.LANCZOS)
head.save(out_head)
print('head saved')
