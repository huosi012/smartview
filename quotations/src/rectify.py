import sys, json, numpy as np, cv2
from PIL import Image
sys.path.insert(0, sys.argv[4])
from edges import fit, inter  # noqa

C, O = sys.argv[1], sys.argv[2]
fits = json.load(open(sys.argv[3]))

def warp(rgba, H):
    a = rgba[..., 3:4].astype(np.float32) / 255
    pm = np.concatenate([rgba[..., :3].astype(np.float32) * a, a * 255], axis=2)
    ys, xs = np.where(rgba[..., 3] > 8)
    pts = np.float32([[xs.min(), ys.min()], [xs.max(), ys.min()], [xs.max(), ys.max()], [xs.min(), ys.max()]]).reshape(-1, 1, 2)
    t = cv2.perspectiveTransform(pts, H).reshape(-1, 2)
    x0, y0 = np.floor(t.min(0)) - 20; x1, y1 = np.ceil(t.max(0)) + 20
    T = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]], dtype=np.float64)
    size = (int(x1 - x0), int(y1 - y0))
    out = cv2.warpPerspective(pm, T @ H, size, flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    al = np.clip(out[..., 3], 0, 255)
    rgb = np.where(al[..., None] > 0.5, out[..., :3] / np.maximum(al[..., None] / 255, 1e-3), 0)
    res = np.dstack([np.clip(rgb, 0, 255), al]).astype(np.uint8)
    im = Image.fromarray(res, 'RGBA')
    bb = im.getchannel('A').point(lambda v: 255 if v > 24 else 0).getbbox()
    return im.crop(bb)

def frontal(name, erase=()):
    rgba = np.array(Image.open(f'{C}/{name}.png').convert('RGBA'))
    for (x0, y0, x1, y1) in erase:
        rgba[y0:y1, x0:x1, 3] = 0
    q = np.float32(fits[name]['quad'])  # TL TR BR BL
    w = (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / 2
    h = (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1])) / 2
    dst = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    im = warp(rgba, cv2.getPerspectiveTransform(q, dst))
    im.save(f'{O}/{name}.png'); print(name, 'frontal', im.size, f'face {w:.0f}x{h:.0f}')

def upright(name):
    """only make the outer vertical edges vertical (keeps a 3/4 view)"""
    rgba = np.array(Image.open(f'{C}/{name}.png').convert('RGBA'))
    _, r = fit(f'{C}/{name}.png')
    ys, xs = np.where(rgba[..., 3] > 128)
    yt, yb = float(ys.min()), float(ys.max())
    L, R = r['left'], r['right']
    src = np.float32([[L[0]*yt+L[1], yt], [R[0]*yt+R[1], yt], [R[0]*yb+R[1], yb], [L[0]*yb+L[1], yb]])
    xl = (src[0, 0] + src[3, 0]) / 2; xr = (src[1, 0] + src[2, 0]) / 2
    dst = np.float32([[xl, yt], [xr, yt], [xr, yb], [xl, yb]])
    im = warp(rgba, cv2.getPerspectiveTransform(src, dst))
    im.save(f'{O}/{name}.png'); print(name, 'upright', im.size, 'left slope', round(L[0], 4), 'right slope', round(R[0], 4))

frontal('p2')
frontal('p1', erase=[(0, 1000, 255, 2000)])
frontal('p3')
frontal('c2')
frontal('c5', erase=[(1072, 1090, 1299, 1732), (0, 1618, 270, 1732)])
upright('c1')
