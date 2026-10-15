"""Solve camera pose + focal length for each site photo from hand-picked points/lines on known
site geometry (terrace 17.8 x 8.5 m, kerb, red-wall upstand, parapet coping).

    python calib_solve.py p_platform
    python calib_solve.py p_corr_across HC        # also solve corridor parapet height
    python calib_solve.py p_corr_far HC fixU
"""
import json, sys
import numpy as np, cv2
from scipy.optimize import least_squares
W = 8.5
import os
SP = os.path.dirname(os.path.abspath(__file__)) + '/'
# site unknowns: L, K (kerb height), U (red-wall upstand), HS (street parapet top)
site0 = dict(L=17.8, K=0.9, U=0.82, HS=1.35, HC=1.2)
SITE_KEYS = ([] if 'fixU' in sys.argv else ['U']) + (['HC'] if 'HC' in sys.argv else [])
# observations: per photo, list of (kind, spec, uv)
#  kind 'pt': spec = (x,y,z) with symbolic strings allowed
#  kind 'line': spec = (point_expr, dir) ; a free parameter t per observation
PH = {
 'p_platform': dict(size=(1080,1919), f0=1400, obs=[
   ('pt', ('L','W',0), (335,1125)),
   ('pt', ('L','W','U'), (338,1062)),
   ('pt', ('L',0,0), (905,1123)),
   ('line', (('L',0,0),(0,1,0)), (500,1121)),
   ('line', (('L',0,0),(0,1,0)), (780,1117)),
   ('line', (('L',0,'U'),(0,1,0)), (450,1062)),
   ('line', (('L',0,'U'),(0,1,0)), (780,1060)),
   ('line', ((0,0,'K'),(0,1,0)), (100,1558)),
   ('line', ((0,0,'K'),(0,1,0)), (500,1552)),
   ('line', ((0,0,'K'),(0,1,0)), (1000,1546)),
 ]),
 'p_corr_across': dict(size=(1707,1280), f0=800, obs=[
   ('pt', ('L','W',0), (1192,670)),
   ('pt', ('L','W','U'), (1192,638)),
   ('line', (('L',0,0),(0,1,0)), (1300,684)),
   ('line', (('L',0,0),(0,1,0)), (1410,699)),
   ('line', (('L',0,'U'),(0,1,0)), (1300,650)),
   ('line', (('L',0,'U'),(0,1,0)), (1410,662)),
   ('pt', (0,'W','K'), (348,607)),
   ('line', ((0,0,'K'),(0,1,0)), (300,642)),
   ('line', ((0,0,'K'),(0,1,0)), (200,720)),
   ('line', ((0,0,'K'),(0,1,0)), (100,800)),
   ('line', ((0,'W',0),(1,0,0)), (700,668)),
   ('line', ((0,'W',0),(1,0,0)), (1100,671)),
   ('line', ((0,-0.12,'HC'),(1,0,0)), (395,1088)),
   ('line', ((0,-0.12,'HC'),(1,0,0)), (958,930)),
   ('line', ((0,-0.12,'HC'),(1,0,0)), (1215,856)),
   ('line', ((0,-0.12,'HC'),(1,0,0)), (1365,815)),
 ]),
  'p_corr_far': dict(size=(1706,1279), f0=1232, obs=[
   ('pt', ('L','W',0), (940,741)),
   ('pt', ('L','W','U'), (940,682)),
   ('line', (('L',0,0),(0,1,0)), (1050,741)),
   ('line', (('L',0,0),(0,1,0)), (1190,741)),
   ('line', (('L',0,'U'),(0,1,0)), (1050,682)),
   ('line', (('L',0,'U'),(0,1,0)), (1190,682)),
   ('line', ((0,'W',0),(1,0,0)), (100,808)),
   ('line', ((0,'W',0),(1,0,0)), (500,778)),
   ('line', ((0,'W',0),(1,0,0)), (800,748)),
   ('pt', ('L',0,'U'), (1405,690)),
   ('line', ((0,-0.12,'HC'),(1,0,0)), (350,1100)),
   ('line', ((0,-0.12,'HC'),(1,0,0)), (812,940)),
   ('line', ((0,-0.12,'HC'),(1,0,0)), (1030,862)),
   ('line', ((0,-0.12,'HC'),(1,0,0)), (1160,820)),
 ]),
}
names = [n for n in sys.argv[1:] if n not in ('fixU', 'HC')] or list(PH)
PRIORS = {
 'p_platform': dict(f=(1442, 200), z=(1.35, 0.2), zrel=True),
 'p_corr_across': dict(f=(616, 80), z=(1.6, 2.0), y=(-1.3, 3.0)),
 'p_corr_far': dict(f=(1232, 150), z=(1.55, 0.2), y=(-1.5, 0.8), x=(9.0, 3.0)),
}

def ev(v, s):
    if isinstance(v, str):
        return W if v == 'W' else s[v]
    return float(v)

def unpack(p):
    s = dict(site0); s['W'] = W
    for i, k in enumerate(SITE_KEYS): s[k] = p[i]
    off = len(SITE_KEYS)
    cams = {}
    for n in names:
        rv = p[off:off+3]; tv = p[off+3:off+6]; f = p[off+6]; off += 7
        nt = sum(1 for o in PH[n]['obs'] if o[0] == 'line')
        ts = p[off:off+nt]; off += nt
        cams[n] = (rv, tv, f, ts)
    return s, cams

def proj(X, rv, tv, f, size):
    R, _ = cv2.Rodrigues(np.array(rv, float))
    Xc = R @ np.array(X) + tv
    return np.array([f*Xc[0]/Xc[2] + size[0]/2, f*Xc[1]/Xc[2] + size[1]/2]), Xc[2]

def resid(p):
    s, cams = unpack(p)
    r = []
    for n in names:
        rv, tv, f, ts = cams[n]
        ti = 0
        for kind, spec, uv in PH[n]['obs']:
            if kind == 'pt':
                X = [ev(v, s) for v in spec]
            else:
                P0 = np.array([ev(v, s) for v in spec[0]]); d = np.array(spec[1], float)
                X = P0 + d * ts[ti]; ti += 1
            q, z = proj(X, rv, tv, f, PH[n]['size'])
            r += list(q - np.array(uv))
            r.append(max(0.0, 0.5 - z) * 1e3)
    # priors
    r.append((s['K'] - 0.9) * 20)
    for n in names:
        rv, tv, f, ts = cams[n]
        R, _ = cv2.Rodrigues(np.array(rv)); pos = -R.T @ tv
        pr = PRIORS[n]
        r.append((f - pr['f'][0]) / pr['f'][1] * 3)
        r.append((pos[2] - pr['z'][0] - (s['K'] if pr.get('zrel') else 0)) / pr['z'][1] * 3)
        if 'y' in pr: r.append((pos[1] - pr['y'][0]) / pr['y'][1] * 3)
        if 'x' in pr: r.append((pos[0] - pr['x'][0]) / pr['x'][1] * 3)
    return np.array(r)

def init_cam(n):
    # camera roughly: platform: at (-2.5, 7, 1.9) looking +x ; across: corridor at (2,-1.5,2.2) looking toward (+x,+y)
    if n == 'p_platform':
        pos = np.array([-2.5, 7.0, 1.9]); look = np.array([1, 0, -0.05])
    elif n == 'p_corr_far':
        pos = np.array([8.0, -1.5, 1.55]); look = np.array([1.0, 0.45, -0.05])
    else:
        pos = np.array([1.5, -1.8, 2.3]); look = np.array([1.0, 1.1, -0.25])
    fwd = look/np.linalg.norm(look); right = np.cross(fwd, [0,0,1]); right/=np.linalg.norm(right); down = np.cross(fwd, right)
    R = np.stack([right, down, fwd])  # world->cam rows (x right, y down, z fwd)
    rv, _ = cv2.Rodrigues(R); tv = -R @ pos
    return list(rv.ravel()) + list(tv) + [PH[n]['f0']]

p0 = [site0[k] for k in SITE_KEYS]
for n in names:
    p0 += init_cam(n)
    p0 += [4.0] * sum(1 for o in PH[n]['obs'] if o[0] == 'line')
res = least_squares(resid, np.array(p0, float), method='trf', max_nfev=20000)
s, cams = unpack(res.x)
print('rms px', np.sqrt(np.mean(res.fun[:-1]**2)))
print({k: round(s[k], 3) for k in SITE_KEYS})
out = {'site': {k: s[k] for k in ['L','K','U','HS','W','HC']}, 'cams': {}}
for n in names:
    rv, tv, f, ts = cams[n]
    R, _ = cv2.Rodrigues(np.array(rv)); pos = -R.T @ tv
    print(n, 'f', round(f,1), 'pos', np.round(pos,2), 'fwd', np.round(R[2],3))
    out['cams'][n] = dict(rv=list(map(float,rv)), tv=list(map(float,tv)), f=float(f), size=PH[n]['size'])
json.dump(out, open(SP + f"calib_{'_'.join(names)}.json", 'w'), indent=1)
