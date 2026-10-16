import sys, numpy as np
from PIL import Image, ImageOps, ImageFilter
I, O = sys.argv[1], sys.argv[2]
# logo: upscale 3x, color-to-alpha (white)
lg = Image.open(f'{I}/d2/image1.jpeg').convert('RGB')
lg = lg.resize((lg.width*3, lg.height*3), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
a = np.asarray(lg).astype(float)
alpha = (255 - a.min(axis=2)) / 255.0
alpha = np.clip((alpha - 0.06) / 0.94, 0, 1)          # kill JPEG off-white haze
rgb = np.where(alpha[..., None] > 0, (a - 255 * (1 - alpha[..., None])) / np.maximum(alpha[..., None], 1e-3), 255)
rgba = np.dstack([np.clip(rgb, 0, 255), alpha * 255]).astype(np.uint8)
Image.fromarray(rgba, 'RGBA').save(f'{O}/logo.png', optimize=True)
# white-on-dark variant: dark parts -> white, teal stays teal
w = rgba.copy()
gray = (np.abs(rgb[..., 0] - rgb[..., 2]) < 40) & (rgb.max(axis=2) < 140)
w[gray, 0:3] = 255
Image.fromarray(w, 'RGBA').save(f'{O}/logo_white.png', optimize=True)
# seal
Image.open(f'{I}/ov/image1.png').save(f'{O}/seal.png', optimize=True)
# photos
def photo(src, name, rot=0, crop=None, maxside=2000, q=84):
    im = ImageOps.exif_transpose(Image.open(src)).convert('RGB')
    if rot: im = im.rotate(rot, expand=True)
    if crop:
        l, t, r, b = crop; W, H = im.size
        im = im.crop((int(l*W), int(t*H), int(r*W), int(b*H)))
    im.thumbnail((maxside, maxside), Image.LANCZOS)
    im.save(f'{O}/{name}.jpg', quality=q, optimize=True, progressive=True)
    print(name, im.size)
photo(f'{I}/d1/image1.jpeg', 'p1', crop=(0, 0, 1, 0.915))   # remove "Meitu" watermark strip
photo(f'{I}/d1/image2.jpeg', 'p2')
photo(f'{I}/d1/image3.jpeg', 'p3')
photo(f'{I}/d1/image4.jpeg', 'p4', maxside=2400)
photo(f'{I}/d2/image2.jpeg', 'c1')
photo(f'{I}/d2/image3.jpeg', 'c2', rot=-90)
photo(f'{I}/d2/image4.jpeg', 'c3')
photo(f'{I}/d2/image5.jpeg', 'c4', rot=180)
photo(f'{I}/d2/image6.jpeg', 'c5', rot=-90)
