import sys, numpy as np
from PIL import Image
C, O = sys.argv[1], sys.argv[2]
def clean(name, erase=(), maxh=1500):
    im = Image.open(f'{C}/{name}.png').convert('RGBA')
    a = np.array(im)
    for (x0, y0, x1, y1) in erase:
        a[y0:y1, x0:x1, 3] = 0
    al = a[..., 3]
    al[al < 10] = 0
    im = Image.fromarray(a, 'RGBA')
    bb = im.getchannel('A').point(lambda v: 255 if v > 24 else 0).getbbox()
    im = im.crop(bb)
    if im.height > maxh:
        im = im.resize((round(im.width * maxh / im.height), maxh), Image.LANCZOS)
    im.save(f'{O}/cut_{name}.png', optimize=True)
    print(name, im.size)
clean('p2', maxh=1600)
clean('p1', erase=[(0, 1000, 255, 2000)])
clean('p3')
clean('c1')
clean('c2')
clean('c5', erase=[(1072, 1090, 1299, 1732), (0, 1618, 270, 1732)])
