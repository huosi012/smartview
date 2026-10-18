"""Remove white background from generated character images (rembg).

Blanks the generator watermark corner first. Optional keep-regions (x0,y0,x1,y1 in source px)
add back non-white props the model drops (floor clue line, dominoes) using a whiteness-based alpha.
"""
import sys, json
import numpy as np
from PIL import Image, ImageDraw
from rembg import remove, new_session

model, jobs = sys.argv[1], json.loads(sys.argv[2])
sess = new_session(model)
for job in jobs:
    im = Image.open(job['src']).convert('RGB')
    w, h = im.size
    ImageDraw.Draw(im).rectangle([int(w * 0.80), int(h * 0.94), w, h], fill=(255, 255, 255))
    cut = remove(im, session=sess, post_process_mask=True)
    a = np.array(cut.split()[3]).astype(np.float32)
    rgb = np.array(im).astype(np.float32)
    for x0, y0, x1, y1 in job.get('keep', []):
        dist = 255 - rgb[y0:y1, x0:x1].min(axis=2)
        extra = np.clip((dist - 12) * 7, 0, 255)
        a[y0:y1, x0:x1] = np.maximum(a[y0:y1, x0:x1], extra)
    out = Image.fromarray(np.dstack([rgb, a]).astype(np.uint8), 'RGBA')
    bbox = Image.fromarray((a > 10).astype(np.uint8) * 255).getbbox()
    out = out.crop(bbox)
    out.save(job['dst'])
    print(job['dst'], out.size)
