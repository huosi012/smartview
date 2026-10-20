// Autumn/winter background generator for the MixC cabinet stickers.
// Leaves are rendered as WebGL ribbons with procedural veins, then composited
// on a 2D canvas with depth-of-field blur, warm glow and film grain.
// All geometry is in centimetres, with (0,0) at the top-left of the trim box.

const BLEED = 2; // cm on every side

// ---------------------------------------------------------------- palettes
// Two ramps (dark -> light) mixed by a low-frequency noise so that the leaves
// read as red-brown with patches of crimson, like a real autumn leaf.
const RAMP_BROWN = ['#1c0705', '#3f1209', '#68200f', '#8e3418', '#b2552b', '#d68c5b', '#f1d3b0'];
const RAMP_RED = ['#220707', '#4a0f0e', '#761a14', '#9c2b1a', '#c04f2f', '#e08a64', '#f6d6bd'];

function hex(c) {
  const n = parseInt(c.slice(1), 16);
  return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

// ---------------------------------------------------------------- designs
// leaf: centreline points (Catmull-Rom), half widths on the left (wl) and
// right (wr) of the direction of travel as [t, cm] keys, shading params.
const DESIGNS = {
  // 150x45 – "Herbs. Inherent warmth." top-left, 中文 bottom-right
  A: {
    w: 150, h: 45,
    bg: {
      linear: [[0, 0], [150, 45], ['#f3e3d2', '#e9cbb2', '#d39d7b', '#9c5032']],
      blobs: [
        { x: 140, y: 2, rx: 34, ry: 12, rot: -0.3, c: '#9c3d1d', a: 0.7, blur: 6 },
        { x: 150, y: 50, rx: 44, ry: 12, rot: -0.2, c: '#5e1d10', a: 0.7, blur: 7 },
        { x: 20, y: 12, rx: 36, ry: 15, rot: 0, c: '#f8e9d9', a: 0.95, blur: 6 },
        { x: 126, y: 32, rx: 25, ry: 9, rot: -0.15, c: '#f4dfca', a: 0.85, blur: 4.5 },
        { x: -8, y: 50, rx: 24, ry: 10, rot: 0.3, c: '#7a2814', a: 0.6, blur: 6 },
        { x: 62, y: 2, rx: 14, ry: 5, rot: -0.2, c: '#f0c99a', a: 0.35, blur: 4 },
      ],
    },
    leaves: [
      // far leaf, top right, heavily blurred
      {
        pts: [[92, -32], [118, -7], [148, 3], [176, 5]],
        wl: [[0, 7], [1, 3]], wr: [[0, 10], [0.6, 8], [1, 2]],
        base: 0.36, side: 0.12, glow: [0.6, 0.4, 0.1], red: 0.6,
        veins: 1.6, blur: 1.5, alpha: 0.9,
      },
      // soft leaf along the bottom-left, out of focus
      {
        pts: [[-26, 66], [2, 48], [26, 41], [48, 44], [66, 56]],
        wl: [[0, 5], [0.5, 6.5], [1, 4]], wr: [[0, 7], [0.5, 8], [1, 5]],
        base: 0.34, side: 0.14, glow: [0.45, 0.3, 0.12], red: 0.6,
        veins: 1.4, blur: 1.4, alpha: 0.95,
      },
      // hero leaf: diagonal blade from bottom-left, tapering off the top-right
      {
        pts: [[-12, 92], [20, 66], [56, 46], [94, 26], [127, 10], [152, -1], [172, -8]],
        wl: [[0, 12], [0.4, 10.5], [0.75, 7], [1, 0]],
        wr: [[0, 22], [0.4, 17], [0.75, 8.5], [1, 0]],
        base: 0.37, side: 0.28, twist: -0.5, curl: 0.06, rim: 0.2,
        glow: [0.5, 0.22, 0.22], sheen: [0.5, 0.2, 0.17],
        red: 0.55, veins: 1, midrib: 0.7, shadow: [1.2, 2, 2.5, 0.35],
        focus: { x: 84, y: 28, r0: 16, r1: 70, sy: 0.55 }, blur: 0.03, farBlur: 0.9,
      },
    ],
    glow: [{ x: 24, y: 8, r: 40, c: '#fff1df', a: 0.3 }, { x: 128, y: 34, r: 24, c: '#fff0dc', a: 0.22 }],
  },

  // 150x45 – knot icons top-left, logo lockup bottom-right
  B: {
    w: 150, h: 45,
    bg: {
      linear: [[0, 45], [150, 0], ['#6e2412', '#bd7650', '#ead0b6', '#f4e4d2']],
      blobs: [
        { x: 132, y: 33, rx: 40, ry: 12.5, rot: -0.12, c: '#faeee0', a: 0.95, blur: 5 },
        { x: 152, y: -4, rx: 26, ry: 8, rot: 0, c: '#a5482a', a: 0.5, blur: 5 },
        { x: 92, y: 50, rx: 30, ry: 6, rot: 0, c: '#b86a44', a: 0.4, blur: 5 },
      ],
    },
    leaves: [
      // hero leaf filling the left two thirds, tip pointing right
      {
        pts: [[-34, 72], [-8, 47], [22, 28], [60, 15], [100, 9], [126, 9], [147, 12]],
        wl: [[0, 26], [0.35, 22], [0.62, 13.5], [0.82, 6.5], [1, 0]],
        wr: [[0, 28], [0.35, 22], [0.62, 12], [0.82, 5.5], [1, 0]],
        base: 0.35, side: 0.26, twist: 0.5, curl: 0.06, rim: 0.2,
        glow: [0.6, 0.26, 0.24], sheen: [0.5, 0.2, 0.17],
        red: 0.55, veins: 1, midrib: 0.75, shadow: [1, 2, 2.5, 0.35],
        focus: { x: 66, y: 18, r0: 18, r1: 75, sy: 0.6 }, blur: 0.03, farBlur: 0.8,
      },
      // curled-back margin catching the light along the top edge
      {
        pts: [[22, -9], [50, -4.5], [76, -0.5], [92, 0.5], [104, -1.5]],
        wl: [[0, 0.6], [0.5, 1.6], [0.85, 1.2], [1, 0]], wr: [[0, 0.8], [0.5, 2.3], [0.85, 1.6], [1, 0]],
        base: 0.76, side: 0.08, rim: -0.08, glow: [0.7, 0.3, 0.1], red: 0.25,
        veins: 0.5, midrib: 0, blur: 0.15, alpha: 0.95,
      },
    ],
    glow: [{ x: 128, y: 30, r: 34, c: '#fff4e4', a: 0.28 }, { x: 72, y: 14, r: 32, c: '#ffcf96', a: 0.16 }],
  },

  // 110x50 – 秋收/冬藏/温养 top-right, "Foci health" bottom-left
  C: {
    w: 110, h: 50,
    bg: {
      linear: [[0, 50], [110, 0], ['#d6a585', '#eed7c2', '#f6e8da', '#ecd2b9']],
      blobs: [
        { x: 84, y: 15, rx: 30, ry: 13, rot: 0, c: '#f9ecde', a: 0.95, blur: 5 },
        { x: 13, y: 45, rx: 25, ry: 11, rot: 0, c: '#f0d9c4', a: 0.85, blur: 4.5 },
        { x: 116, y: -6, rx: 22, ry: 9, rot: 0.5, c: '#8a3519', a: 0.55, blur: 4.5 },
        { x: 114, y: 52, rx: 28, ry: 12, rot: -0.4, c: '#7f2c16', a: 0.6, blur: 5 },
        { x: -4, y: -4, rx: 18, ry: 8, rot: 0.4, c: '#6a2212', a: 0.5, blur: 4 },
      ],
    },
    leaves: [
      // far leaf bottom-right
      {
        pts: [[60, 76], [83, 54], [104, 39], [132, 30]],
        wl: [[0, 7], [1, 3]], wr: [[0, 9], [1, 3]],
        base: 0.36, side: 0.14, glow: [0.5, 0.4, 0.12], red: 0.6,
        veins: 1.4, blur: 1.1, alpha: 0.95,
      },
      // hero leaf hanging from the top-left, tip curling towards the bottom-centre
      {
        pts: [[-30, -12], [-4, -1], [20, 9], [40, 22], [52, 35], [58, 46], [60, 53]],
        wl: [[0, 12], [0.35, 14], [0.7, 10], [0.92, 3], [1, 0]],
        wr: [[0, 12], [0.35, 13], [0.7, 9], [0.92, 3], [1, 0]],
        base: 0.37, side: -0.26, twist: 0.4, curl: 0.06, rim: 0.2,
        glow: [0.42, 0.22, 0.22], sheen: [-0.5, 0.2, 0.17],
        red: 0.55, veins: 1, midrib: 0.65, shadow: [1.5, 1.5, 2, 0.3],
        focus: { x: 30, y: 20, r0: 12, r1: 50, sy: 0.8 }, blur: 0.03, farBlur: 0.7,
      },
    ],
    glow: [{ x: 84, y: 13, r: 32, c: '#fff5e6', a: 0.28 }],
  },

  // 110x50 – 慈 seal centred inside a curled leaf
  D: {
    w: 110, h: 50,
    bg: {
      radial: [55, 19, 62, ['#f8eadb', '#ebcdb2', '#c3825c', '#6e2814']],
      blobs: [
        { x: 55, y: 19, rx: 27, ry: 13, rot: 0, c: '#faefe2', a: 0.9, blur: 5 },
      ],
    },
    leaves: [
      // second sweep behind, out of focus
      {
        pts: [[-24, 26], [6, 44], [40, 58], [80, 54], [108, 38], [134, 18]],
        wl: [[0, 6], [1, 5]], wr: [[0, 8], [1, 6]],
        base: 0.3, side: 0.1, glow: [0.5, 0.4, 0.12], red: 0.6,
        veins: 1.3, blur: 1.1, alpha: 0.95,
      },
      // hero leaf: from the top-left corner down past the bottom, tip curling up on the right
      {
        pts: [[-22, -24], [-2, -3], [18, 21], [40, 39], [62, 43], [82, 35], [96, 20], [104, 7]],
        wl: [[0, 13], [0.45, 10.5], [0.8, 6], [0.95, 1.8], [1, 0]],
        wr: [[0, 15], [0.45, 12], [0.8, 7], [0.95, 2.2], [1, 0]],
        base: 0.37, side: 0.26, twist: -0.8, curl: 0.06, rim: 0.2,
        glow: [0.42, 0.22, 0.22], sheen: [0.5, 0.2, 0.17],
        red: 0.55, veins: 1, midrib: 0.65, shadow: [1, 1.8, 2, 0.3],
        focus: { x: 40, y: 37, r0: 14, r1: 60, sy: 0.7 }, blur: 0.03, farBlur: 0.75,
      },
    ],
    glow: [{ x: 55, y: 19, r: 30, c: '#fff6e8', a: 0.32 }],
  },
};

// ---------------------------------------------------------------- geometry
function catmull(pts, n) {
  // uniform Catmull-Rom through pts, n samples
  const P = [pts[0], ...pts, pts[pts.length - 1]];
  const segs = pts.length - 1;
  const out = [];
  for (let i = 0; i < n; i++) {
    const g = (i / (n - 1)) * segs;
    const k = Math.min(Math.floor(g), segs - 1);
    const t = g - k;
    const [p0, p1, p2, p3] = [P[k], P[k + 1], P[k + 2], P[k + 3]];
    const t2 = t * t, t3 = t2 * t;
    out.push([0, 1].map(d => 0.5 * (2 * p1[d] + (-p0[d] + p2[d]) * t +
      (2 * p0[d] - 5 * p1[d] + 4 * p2[d] - p3[d]) * t2 + (-p0[d] + 3 * p1[d] - 3 * p2[d] + p3[d]) * t3)));
  }
  return out;
}

function keyed(keys, t) {
  // smooth interpolation of [t, value] keys
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    if (t <= keys[i][0]) {
      const [t0, v0] = keys[i - 1], [t1, v1] = keys[i];
      const x = (t - t0) / (t1 - t0);
      return v0 + (v1 - v0) * x * x * (3 - 2 * x);
    }
  }
  return keys[keys.length - 1][1];
}

function ribbonMesh(leaf, S) {
  const N = 700, M = 64;
  const c = catmull(leaf.pts, N);
  // arc length
  const len = [0];
  for (let i = 1; i < N; i++) len.push(len[i - 1] + Math.hypot(c[i][0] - c[i - 1][0], c[i][1] - c[i - 1][1]));
  const total = len[N - 1];
  const verts = []; // x, y (px), u, v (cm), s, t, w
  for (let i = 0; i < N; i++) {
    const a = c[Math.max(i - 1, 0)], b = c[Math.min(i + 1, N - 1)];
    let tx = b[0] - a[0], ty = b[1] - a[1];
    const tl = Math.hypot(tx, ty); tx /= tl; ty /= tl;
    const nx = ty, ny = -tx; // left normal in y-down space
    const t = len[i] / total;
    const wl = keyed(leaf.wl, t), wr = keyed(leaf.wr, t);
    for (let j = 0; j <= M; j++) {
      const s = -1 + (2 * j) / M; // -1 = right edge, +1 = left edge
      const w = s >= 0 ? wl : wr;
      const off = s * w;
      const x = c[i][0] + nx * off, y = c[i][1] + ny * off;
      verts.push((x + BLEED) * S, (y + BLEED) * S, len[i], off, s, t, Math.max(w, 0.001));
    }
  }
  const idx = [];
  for (let i = 0; i < N - 1; i++) {
    for (let j = 0; j < M; j++) {
      const a = i * (M + 1) + j, b = a + 1, d = a + M + 1, e = d + 1;
      idx.push(a, d, b, b, d, e);
    }
  }
  return { verts: new Float32Array(verts), idx: new Uint32Array(idx) };
}

// ---------------------------------------------------------------- shaders
const VS = `#version 300 es
in vec2 aPos; in vec4 aUV; in float aW;
uniform vec2 uRes;
out vec4 vUV; out float vW;
void main(){
  vUV = aUV; vW = aW;
  vec2 p = aPos / uRes * 2.0 - 1.0;
  gl_Position = vec4(p.x, -p.y, 0.0, 1.0);
}`;

const FS = `#version 300 es
precision highp float;
in vec4 vUV; in float vW;
out vec4 outColor;
uniform vec3 uBrown[7]; uniform vec3 uRed[7];
uniform float uBase, uSide, uTwist, uCurl, uRim, uRedness, uVeins, uMidrib, uSeed, uAlpha, uS;
uniform vec3 uGlow;   // t centre, width, strength
uniform vec3 uSheen;  // s centre, width, strength

vec3 mod289(vec3 x){return x-floor(x*(1.0/289.0))*289.0;}
vec2 mod289(vec2 x){return x-floor(x*(1.0/289.0))*289.0;}
vec3 permute(vec3 x){return mod289(((x*34.0)+1.0)*x);}
float snoise(vec2 v){
  const vec4 C=vec4(0.211324865405187,0.366025403784439,-0.577350269189626,0.024390243902439);
  vec2 i=floor(v+dot(v,C.yy)); vec2 x0=v-i+dot(i,C.xx);
  vec2 i1=(x0.x>x0.y)?vec2(1.0,0.0):vec2(0.0,1.0);
  vec4 x12=x0.xyxy+C.xxzz; x12.xy-=i1; i=mod289(i);
  vec3 p=permute(permute(i.y+vec3(0.0,i1.y,1.0))+i.x+vec3(0.0,i1.x,1.0));
  vec3 m=max(0.5-vec3(dot(x0,x0),dot(x12.xy,x12.xy),dot(x12.zw,x12.zw)),0.0);
  m=m*m; m=m*m;
  vec3 x=2.0*fract(p*C.www)-1.0; vec3 h=abs(x)-0.5; vec3 ox=floor(x+0.5); vec3 a0=x-ox;
  m*=1.79284291400159-0.85373472095314*(a0*a0+h*h);
  vec3 g; g.x=a0.x*x0.x+h.x*x0.y; g.yz=a0.yz*x12.xz+h.yz*x12.yw;
  return 130.0*dot(m,g);
}
float fbm(vec2 p){ float f=0.0, a=0.5; for(int i=0;i<5;i++){ f+=a*snoise(p); p*=2.03; a*=0.5; } return f; }

vec3 ramp(vec3 c[7], float x){
  x = clamp(x, 0.0, 1.0) * 6.0;
  int i = int(min(floor(x), 5.0));
  float f = x - float(i);
  f = f*f*(3.0-2.0*f);
  return mix(c[i], c[i+1], f);
}
// anti-aliased periodic line; x is in cycles, wcm is the line width in cm and
// period the cycle length in cm (so widths stay physical at any resolution)
float lines(float x, float wcm, float period){
  float d = (0.5 - abs(fract(x) - 0.5)) / max(fwidth(x), 1e-5); // px from line centre
  float wpx = max(wcm * uS, 0.6);
  float fade = clamp(wcm * uS / 0.6, 0.0, 1.0);          // sub-pixel lines fade instead of aliasing
  return fade * (1.0 - smoothstep(wpx*0.5, wpx*0.5 + 1.0, d));
}

void main(){
  float u = vUV.x, v = vUV.y, s = vUV.z, t = vUV.w;
  float as = abs(s);
  vec2 sp = vec2(u, v) + uSeed;

  // silhouette with a slightly irregular margin
  float edge = 1.0 - 0.012 * (0.5 + 0.5*snoise(vec2(u*0.9, s*3.0) + uSeed));
  float fw = fwidth(s);
  float alpha = 1.0 - smoothstep(edge - fw*1.2, edge + fw*0.3, as);

  // shading
  float L = uBase;
  L += uSide * (1.0 + uTwist * (t - 0.5) * 2.0) * s;  // one half faces the light (twisting along the leaf)
  L += uCurl * (1.0 - as*as) - uCurl*0.5;       // blade curvature
  L += uRim * smoothstep(0.8, 0.99, as);        // backlit translucent margin
  L += uGlow.z * exp(-pow((t - uGlow.x)/uGlow.y, 2.0)) * (1.0 - 0.4*as);
  L += uSheen.z * exp(-pow((s - uSheen.x)/uSheen.y, 2.0)) * (0.5 + 0.5*exp(-pow((t - uGlow.x)/(uGlow.y*1.6), 2.0)));
  L += 0.07 * fbm(sp * 0.09);                   // mottling
  L += 0.025 * fbm(sp * 0.6);

  // midrib
  float mr = 0.45 * uMidrib * (1.0 - 0.6*t) + 0.05;
  float mid = 1.0 - smoothstep(mr*0.35, mr, abs(v));
  L += 0.13 * uMidrib * mid - 0.05 * uMidrib * (smoothstep(mr, mr*2.2, abs(v)) - smoothstep(mr*2.2, mr*4.0, abs(v)));

  // lateral veins curving from the midrib towards the tip
  float q = u - 0.5 * vW * pow(as, 1.25);
  q += 0.5 * snoise(vec2(u*0.02, t*1.5) + uSeed*1.7) + 0.08 * snoise(vec2(u*0.3, as*1.2));
  float fd = 3.2 * uVeins, md = 0.42 * uVeins;    // veins per cm
  float fine = lines(q * fd, 0.028, 1.0/fd);
  float major = lines(q * md, 0.07, 1.0/md);
  float fade = smoothstep(0.02, 0.15, as) * (1.0 - smoothstep(0.88, 1.0, as));
  float tert = 0.5 + 0.5*snoise(sp * vec2(1.4, 2.2));
  L += fade * (0.035 * fine * (0.5 + 0.5*tert) + 0.06 * major);
  // the blade puckers slightly between major veins
  L += fade * 0.015 * sin(q * md * 6.2832 + 1.2);

  float redMix = clamp(uRedness + 0.35*fbm(sp * 0.035 + 7.0), 0.0, 1.0);
  vec3 col = mix(ramp(uBrown, L), ramp(uRed, L), redMix);
  // golden backlight where the glow is strongest
  float hot = exp(-pow((t - uGlow.x)/uGlow.y, 2.0)) * (1.0 - as*0.6) * uGlow.z * 3.0;
  col = mix(col, col * vec3(1.08, 0.98, 0.8) + vec3(0.06, 0.035, 0.0), clamp(hot, 0.0, 1.0) * 0.5);
  // veins pick up a golden tint
  col = mix(col, col * vec3(1.06, 1.0, 0.86) + vec3(0.04, 0.03, 0.0), fade * major * 0.6);

  float a = alpha * uAlpha;
  outColor = vec4(col * a, a);
}`;

function compile(gl, type, src) {
  const sh = gl.createShader(type);
  gl.shaderSource(sh, src);
  gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(sh));
  return sh;
}

function renderLeafGL(leaf, Wpx, Hpx, S, seed) {
  const cv = document.createElement('canvas');
  cv.width = Wpx; cv.height = Hpx;
  const gl = cv.getContext('webgl2', { premultipliedAlpha: true, preserveDrawingBuffer: true, antialias: true });
  const prog = gl.createProgram();
  gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VS));
  gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, FS));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
  gl.useProgram(prog);

  const { verts, idx } = ribbonMesh(leaf, S);
  const vb = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, vb);
  gl.bufferData(gl.ARRAY_BUFFER, verts, gl.STATIC_DRAW);
  const stride = 7 * 4;
  const loc = n => gl.getAttribLocation(prog, n);
  gl.enableVertexAttribArray(loc('aPos')); gl.vertexAttribPointer(loc('aPos'), 2, gl.FLOAT, false, stride, 0);
  gl.enableVertexAttribArray(loc('aUV')); gl.vertexAttribPointer(loc('aUV'), 4, gl.FLOAT, false, stride, 8);
  gl.enableVertexAttribArray(loc('aW')); gl.vertexAttribPointer(loc('aW'), 1, gl.FLOAT, false, stride, 24);
  const ib = gl.createBuffer();
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib);
  gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, idx, gl.STATIC_DRAW);

  const U = n => gl.getUniformLocation(prog, n);
  gl.uniform2f(U('uRes'), Wpx, Hpx);
  gl.uniform3fv(U('uBrown'), RAMP_BROWN.flatMap(hex));
  gl.uniform3fv(U('uRed'), RAMP_RED.flatMap(hex));
  gl.uniform1f(U('uBase'), leaf.base);
  gl.uniform1f(U('uSide'), leaf.side ?? 0);
  gl.uniform1f(U('uTwist'), leaf.twist ?? 0);
  gl.uniform1f(U('uS'), S);
  gl.uniform1f(U('uCurl'), leaf.curl ?? 0);
  gl.uniform1f(U('uRim'), leaf.rim ?? 0);
  gl.uniform1f(U('uRedness'), leaf.red ?? 0.4);
  gl.uniform1f(U('uVeins'), leaf.veins ?? 1);
  gl.uniform1f(U('uMidrib'), leaf.midrib ?? 0.6);
  gl.uniform1f(U('uSeed'), seed);
  gl.uniform1f(U('uAlpha'), leaf.alpha ?? 1);
  gl.uniform3fv(U('uGlow'), leaf.glow ?? [0.5, 0.3, 0]);
  gl.uniform3fv(U('uSheen'), leaf.sheen ?? [0, 0.2, 0]);

  gl.viewport(0, 0, Wpx, Hpx);
  gl.clearColor(0, 0, 0, 0);
  gl.clear(gl.COLOR_BUFFER_BIT);
  gl.drawElements(gl.TRIANGLES, idx.length, gl.UNSIGNED_INT, 0);
  gl.finish();
  return cv;
}

// ---------------------------------------------------------------- 2D compositing
function canvas2d(w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  return [c, c.getContext('2d')];
}

function blurred(src, px) {
  const [c, x] = canvas2d(src.width, src.height);
  x.filter = px > 0.3 ? `blur(${px}px)` : 'none';
  x.drawImage(src, 0, 0);
  return c;
}

function focusMask(ctx, f, S) {
  // radial alpha: 1 inside r0, 0 beyond r1, squashed vertically by sy
  const cx = (f.x + BLEED) * S, cy = (f.y + BLEED) * S;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(1, f.sy ?? 1);
  const g = ctx.createRadialGradient(0, 0, f.r0 * S, 0, 0, f.r1 * S);
  g.addColorStop(0, 'rgba(0,0,0,1)');
  g.addColorStop(0.5, 'rgba(0,0,0,0.45)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.fillRect(-1e5, -1e5, 2e5, 2e5);
  ctx.restore();
}

function drawLeaf(ctx, leaf, Wpx, Hpx, S, seed) {
  const gl = renderLeafGL(leaf, Wpx, Hpx, S, seed);
  if (leaf.shadow) {
    // soft cast shadow on whatever is behind the leaf
    const [dx, dy, blur, a] = leaf.shadow;
    ctx.save();
    ctx.filter = `blur(${blur * S}px) brightness(0.25) sepia(1) saturate(2)`;
    ctx.globalAlpha = a;
    ctx.globalCompositeOperation = 'multiply';
    ctx.drawImage(gl, dx * S, dy * S);
    ctx.restore();
  }
  const near = blurred(gl, (leaf.blur ?? 0) * S);
  if (!leaf.focus) { ctx.drawImage(near, 0, 0); return; }
  const far = blurred(gl, leaf.farBlur * S);
  // far * (1 - mask) + near * mask
  const fx = far.getContext('2d');
  fx.globalCompositeOperation = 'destination-out';
  focusMask(fx, leaf.focus, S);
  const nx = near.getContext('2d');
  nx.globalCompositeOperation = 'destination-in';
  focusMask(nx, leaf.focus, S);
  const [sum, sx] = canvas2d(Wpx, Hpx);
  sx.drawImage(far, 0, 0);
  sx.globalCompositeOperation = 'lighter';
  sx.drawImage(near, 0, 0);
  ctx.drawImage(sum, 0, 0);
}

function drawBackground(ctx, bg, Wpx, Hpx, S) {
  const P = (x, y) => [(x + BLEED) * S, (y + BLEED) * S];
  let g;
  if (bg.linear) {
    const [[x0, y0], [x1, y1], stops] = bg.linear;
    g = ctx.createLinearGradient(...P(x0, y0), ...P(x1, y1));
    stops.forEach((c, i) => g.addColorStop(i / (stops.length - 1), c));
  } else {
    const [x, y, r, stops] = bg.radial;
    g = ctx.createRadialGradient(...P(x, y), 0, ...P(x, y), r * S);
    stops.forEach((c, i) => g.addColorStop(i / (stops.length - 1), c));
  }
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, Wpx, Hpx);
  for (const b of bg.blobs ?? []) {
    ctx.save();
    ctx.filter = `blur(${b.blur * S}px)`;
    ctx.globalAlpha = b.a;
    ctx.fillStyle = b.c;
    ctx.beginPath();
    ctx.ellipse(...P(b.x, b.y), b.rx * S, b.ry * S, b.rot, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
}

function drawGlow(ctx, glows, S) {
  for (const gl of glows ?? []) {
    const x = (gl.x + BLEED) * S, y = (gl.y + BLEED) * S;
    const g = ctx.createRadialGradient(x, y, 0, x, y, gl.r * S);
    const [r, gg, b] = hex(gl.c).map(v => Math.round(v * 255));
    g.addColorStop(0, `rgba(${r},${gg},${b},${gl.a})`);
    g.addColorStop(1, `rgba(${r},${gg},${b},0)`);
    ctx.save();
    ctx.globalCompositeOperation = 'screen';
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    ctx.restore();
  }
}

function grain(ctx, Wpx, Hpx, amount, seed) {
  const img = ctx.getImageData(0, 0, Wpx, Hpx);
  const d = img.data;
  let s = seed * 1e6 | 0 || 1;
  for (let i = 0; i < d.length; i += 4) {
    s ^= s << 13; s ^= s >>> 17; s ^= s << 5;
    const n = ((s >>> 0) / 4294967296 - 0.5) * amount;
    d[i] += n; d[i + 1] += n; d[i + 2] += n;
  }
  ctx.putImageData(img, 0, 0);
}

// Renders design `id` at `S` px per cm (trim + bleed) and returns the canvas.
function render(id, S) {
  const D = DESIGNS[id];
  const Wpx = Math.round((D.w + 2 * BLEED) * S), Hpx = Math.round((D.h + 2 * BLEED) * S);
  const [cv, ctx] = canvas2d(Wpx, Hpx);
  drawBackground(ctx, D.bg, Wpx, Hpx, S);
  D.leaves.forEach((leaf, i) => drawLeaf(ctx, leaf, Wpx, Hpx, S, 3.7 + i * 11.3 + id.charCodeAt(0)));
  drawGlow(ctx, D.glow, S);
  grain(ctx, Wpx, Hpx, 7, 0.123 + id.charCodeAt(0));
  return cv;
}

window.BLEED = BLEED;
window.DESIGNS = DESIGNS;
window.renderBackground = (id, S) => render(id, S).toDataURL('image/png');
