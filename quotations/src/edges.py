import sys, json, numpy as np
from PIL import Image, ImageDraw
rng = np.random.default_rng(0)

def ransac(u, v, thr=3.0, it=3000):
    """fit v = a*u + b robustly; returns (a, b, inlier_ratio)"""
    best = None
    n = len(u)
    for _ in range(it):
        i, j = rng.choice(n, 2, replace=False)
        if u[i] == u[j]: continue
        a = (v[j] - v[i]) / (u[j] - u[i]); b = v[i] - a * u[i]
        inl = np.abs(v - (a * u + b)) < thr
        c = inl.sum()
        if best is None or c > best[0]: best = (c, inl)
    inl = best[1]
    a, b = np.polyfit(u[inl], v[inl], 1)
    return float(a), float(b), float(inl.mean())

def profile(mask, side):
    H, W = mask.shape
    if side in ('top', 'bottom'):
        cols = np.where(mask.any(axis=0))[0]
        if side == 'top': vals = mask[:, cols].argmax(axis=0)
        else: vals = H - 1 - mask[::-1, cols].argmax(axis=0)
        return cols.astype(float), vals.astype(float)
    rows = np.where(mask.any(axis=1))[0]
    if side == 'left': vals = mask[rows, :].argmax(axis=1)
    else: vals = W - 1 - mask[rows, ::-1].argmax(axis=1)
    return rows.astype(float), vals.astype(float)

def fit(path, trim=None):
    im = Image.open(path).convert('RGBA')
    mask = np.array(im)[..., 3] > 128
    res = {}
    for side in ('top', 'bottom', 'left', 'right'):
        u, v = profile(mask, side)
        # ignore the outer 6% at either end (rounded corners, feet)
        lo, hi = np.percentile(u, 6), np.percentile(u, 94)
        k = (u > lo) & (u < hi)
        res[side] = ransac(u[k], v[k])
    return im, res

def inter(h, vline):
    # h: y = a x + b ; vline: x = c y + d
    a, b = h[:2]; c, d = vline[:2]
    y = (a * d + b) / (1 - a * c); x = c * y + d
    return x, y

if __name__ == '__main__':
    out = {}
    for n in sys.argv[3].split(','):
        im, r = fit(f'{sys.argv[1]}/{n}.png')
        q = [inter(r['top'], r['left']), inter(r['top'], r['right']), inter(r['bottom'], r['right']), inter(r['bottom'], r['left'])]
        out[n] = {'lines': r, 'quad': q}
        bg = Image.new('RGB', im.size, (255, 170, 210)); bg.paste(im, (0, 0), im)
        d = ImageDraw.Draw(bg)
        d.line(q + [q[0]], fill=(0, 90, 255), width=5)
        for p in q: d.ellipse([p[0]-12, p[1]-12, p[0]+12, p[1]+12], outline=(255, 0, 0), width=4)
        bg.thumbnail((700, 700)); bg.save(f'{sys.argv[2]}/{n}_fit.png')
        print(n, {k: tuple(round(x, 4) for x in v) for k, v in r.items()}, [tuple(round(x) for x in p) for p in q])
    json.dump(out, open(f'{sys.argv[2]}/fits.json', 'w'), indent=1)
