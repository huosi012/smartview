// v2 "大兴安岭秋林" backgrounds: layered forest ridges with mist, birch trunks
// and falling oak / birch / maple leaves. Reuses helpers from bg.js.
// All geometry in cm, (0,0) = top-left of the trim box.

// 五花山 palette: larch gold dominant, oak red-brown, maple red, birch yellow, pine green.
const SPECIES = {
  larch: '#dba634', birch: '#e6c454', orange: '#d27a2c',
  oak: '#9c4a22', maple: '#b8361f', pine: '#3a4f33',
};
const SPECIES_MIX = { larch: 0.32, birch: 0.15, orange: 0.16, oak: 0.15, maple: 0.1, pine: 0.12 };

const LEAF_COLORS = {
  maple: { base: '#cf4a26', mid: '#b5301c', tip: '#952214', spots: ['#e0883a', '#701a10'], vein: '#f2b878' },
  oak: { base: '#b8662c', mid: '#97431f', tip: '#7c3217', spots: ['#5e2a14', '#c98a40'], vein: '#e9bb80' },
  birch: { base: '#e6be4a', mid: '#d9a234', tip: '#c4822a', spots: ['#a8582a', '#f0d27a'], vein: '#f7e2a0' },
  larchGold: { base: '#e3ad3c', mid: '#d4932c', tip: '#bb7424', spots: ['#9a5a20', '#f2cf74'], vein: '#f8e3a6' },
};

// ---------------------------------------------------------------- forest shader
const FOREST_VS = `#version 300 es
in vec2 aPos;
void main(){ gl_Position = vec4(aPos, 0.0, 1.0); }`;

const FOREST_FS = `#version 300 es
precision highp float;
out vec4 o;
uniform vec2 uPx;
uniform float uS, uB, uSeed;
uniform float uRidge[64]; uniform float uRx0, uRx1;
uniform float uCrown, uSpike, uNoiseAmp, uShade;
uniform float uMist, uMistMax, uMistDepth; uniform vec3 uMistCol;
uniform vec3 uCols[6]; uniform float uWts[6];

vec2 hash2(vec2 p){ p = vec2(dot(p,vec2(127.1,311.7)), dot(p,vec2(269.5,183.3))); return fract(sin(p + uSeed)*43758.5453); }
float hash1(float n){ return fract(sin(n*91.345 + uSeed*1.7)*47453.5453); }
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

float ridgeAt(float x){
  float f = clamp((x-uRx0)/(uRx1-uRx0), 0.0, 1.0) * 63.0;
  int i = int(min(floor(f), 62.0));
  return mix(uRidge[i], uRidge[i+1], f - float(i));
}

void main(){
  float x = gl_FragCoord.x/uS - uB;
  float y = (uPx.y - gl_FragCoord.y)/uS - uB;
  float r = ridgeAt(x) + uNoiseAmp * fbm(vec2(x*0.035, uSeed*0.13));

  // skyline: larch spires mixed with rounded broadleaf crowns
  float sp = uCrown * 0.85;
  float k = floor(x/sp), fx = fract(x/sp);
  float h = hash1(k);
  float conifer = step(0.62, hash1(k + 31.0));
  float spire = uSpike * uCrown * (0.6 + h) * max(0.0, 1.0 - abs(fx-0.5)*2.0);
  float round_ = 0.45 * uCrown * (0.5 + 0.8*h) * sqrt(max(0.0, 1.0 - pow((fx-0.5)*2.0, 2.0)));
  float top = r - mix(round_, spire, conifer);
  float px = 1.0/uS;
  float a = smoothstep(top - px, top + px, y);
  if (a <= 0.0) { o = vec4(0.0); return; }

  // canopy: weighted voronoi crowns
  vec2 q = vec2(x, y*0.85) / uCrown;
  vec2 ci = floor(q);
  float d1 = 9.0, d2 = 9.0; vec2 best = ci, bestOff = vec2(0.0);
  for (int j=-1; j<=1; j++) for (int i=-1; i<=1; i++) {
    vec2 c = ci + vec2(float(i), float(j));
    vec2 ctr = c + 0.5 + 0.75*(hash2(c) - 0.5);
    float rr = 0.55 + 0.4*hash2(c + 3.1).x;
    vec2 off = (q - ctr) / rr;
    float d = length(off);
    if (d < d1) { d2 = d1; d1 = d; best = c; bestOff = off; } else if (d < d2) { d2 = d; }
  }
  // species: clustered patches (五花山) plus per-crown randomness
  float region = 0.5 + 0.5*fbm(vec2(x*0.045, y*0.07) + uSeed*0.37);
  float pick = fract(hash2(best + 7.7).x * 0.28 + region * 1.7);
  vec3 col = uCols[5]; float acc = 0.0;
  for (int s=0; s<6; s++) { acc += uWts[s]; if (pick < acc) { col = uCols[s]; break; } }
  col *= 0.86 + 0.24*hash2(best + 1.3).y;
  // crowns lit from above-left: darker lower edge, soft gaps, leafy speckle
  float lit = 0.85 + 0.3*dot(normalize(bestOff + 1e-4), normalize(vec2(-0.5, -0.86))) * min(d1, 1.0);
  float shade = mix(0.7, 1.0, 1.0 - smoothstep(0.5, 1.1, d1)) * lit;
  shade *= mix(0.78, 1.0, smoothstep(0.0, 0.35, d2 - d1));
  shade *= 0.9 + 0.2*snoise(vec2(x, y) * 3.0 / uCrown);
  col *= shade * uShade;
  // valley mist below the ridge line
  float m = uMist + uMistMax * smoothstep(0.0, uMistDepth, y - r);
  col = mix(col, uMistCol, clamp(m, 0.0, 1.0));
  o = vec4(col * a, a);
}`;

function renderForestGL(layer, Wpx, Hpx, S, seed) {
  const cv = document.createElement('canvas');
  cv.width = Wpx; cv.height = Hpx;
  const gl = cv.getContext('webgl2', { premultipliedAlpha: true, preserveDrawingBuffer: true });
  const prog = gl.createProgram();
  gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, FOREST_VS));
  gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, FOREST_FS));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
  gl.useProgram(prog);
  const vb = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, vb);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, 'aPos');
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

  // ridge: catmull-rom through control points, resampled to 64 evenly spaced x
  const x0 = -BLEED - 2, x1 = Wpx / S - BLEED + 2;
  const dense = catmull(layer.ridge, 600);
  const ridge = [];
  for (let i = 0; i < 64; i++) {
    const x = x0 + (x1 - x0) * i / 63;
    let k = dense.findIndex(p => p[0] >= x);
    if (k <= 0) k = k === 0 ? 1 : dense.length - 1;
    const [a, b] = [dense[k - 1], dense[k]];
    const f = Math.min(Math.max((x - a[0]) / ((b[0] - a[0]) || 1), 0), 1);
    ridge.push(a[1] + (b[1] - a[1]) * f);
  }
  const U = n => gl.getUniformLocation(prog, n);
  const mix = layer.mix ?? SPECIES_MIX;
  const names = Object.keys(SPECIES);
  const total = names.reduce((s, n) => s + (mix[n] ?? 0), 0);
  gl.uniform2f(U('uPx'), Wpx, Hpx);
  gl.uniform1f(U('uS'), S);
  gl.uniform1f(U('uB'), BLEED);
  gl.uniform1f(U('uSeed'), seed);
  gl.uniform1fv(U('uRidge'), ridge);
  gl.uniform1f(U('uRx0'), x0);
  gl.uniform1f(U('uRx1'), x1);
  gl.uniform1f(U('uCrown'), layer.crown);
  gl.uniform1f(U('uSpike'), layer.spike ?? 1.1);
  gl.uniform1f(U('uNoiseAmp'), layer.noise ?? 1.2);
  gl.uniform1f(U('uShade'), layer.shade ?? 1);
  gl.uniform1f(U('uMist'), layer.mist);
  gl.uniform1f(U('uMistMax'), layer.mistMax ?? 0.5);
  gl.uniform1f(U('uMistDepth'), layer.mistDepth ?? 8);
  gl.uniform3fv(U('uMistCol'), hex(layer.mistColor ?? '#efdcc6'));
  gl.uniform3fv(U('uCols'), names.flatMap(n => hex(SPECIES[n])));
  gl.uniform1fv(U('uWts'), names.map(n => (mix[n] ?? 0) / total));
  gl.viewport(0, 0, Wpx, Hpx);
  gl.clearColor(0, 0, 0, 0);
  gl.clear(gl.COLOR_BUFFER_BIT);
  gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  gl.finish();
  return cv;
}

function drawForest(ctx, layer, Wpx, Hpx, S, seed) {
  const cv = renderForestGL(layer, Wpx, Hpx, S, seed);
  ctx.drawImage(blurred(cv, (layer.blur ?? 0) * S), 0, 0);
}

// ---------------------------------------------------------------- random helpers
function rng(seed) {
  let s = (Math.floor(seed * 9973) ^ 0x9e3779b9) >>> 0 || 1;
  return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; };
}

let NOISE_TILE = null;
function noiseTile() {
  // grayscale value-noise tile used as leaf / bark texture
  if (NOISE_TILE) return NOISE_TILE;
  const n = 512;
  const [c, x] = canvas2d(n, n);
  const img = x.createImageData(n, n);
  const r = rng(0.77);
  const grid = (g) => { const a = []; for (let i = 0; i < (g + 1) * (g + 1); i++) a.push(r()); return a; };
  const octaves = [[8, 0.5], [16, 0.25], [32, 0.15], [96, 0.1]].map(([g, w]) => [g, w, grid(g)]);
  for (let yy = 0; yy < n; yy++) for (let xx = 0; xx < n; xx++) {
    let v = 0;
    for (const [g, w, a] of octaves) {
      const fx = xx / n * g, fy = yy / n * g;
      const ix = Math.floor(fx), iy = Math.floor(fy), tx = fx - ix, ty = fy - iy;
      const sx = tx * tx * (3 - 2 * tx), sy = ty * ty * (3 - 2 * ty);
      const at = (i, j) => a[(j % (g + 1)) * (g + 1) + (i % (g + 1))];
      v += w * ((at(ix, iy) * (1 - sx) + at(ix + 1, iy) * sx) * (1 - sy) + (at(ix, iy + 1) * (1 - sx) + at(ix + 1, iy + 1) * sx) * sy);
    }
    const k = (yy * n + xx) * 4;
    img.data[k] = img.data[k + 1] = img.data[k + 2] = Math.max(0, Math.min(255, v * 255));
    img.data[k + 3] = 255;
  }
  x.putImageData(img, 0, 0);
  NOISE_TILE = c;
  return c;
}

// ---------------------------------------------------------------- leaf outlines (unit leaf: base (0,0), tip (0,-1))
function pinnateOutline(widthAt, n = 240) {
  const L = [], R = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const w = widthAt(t);
    L.push([-w, -t]);
    R.push([w, -t]);
  }
  return L.concat(R.reverse());
}

const OUTLINES = {
  oak: (r) => {
    const lobes = 6 + Math.floor(r() * 2);
    return pinnateOutline(t => {
      const w0 = 0.34 * Math.pow(Math.sin(Math.PI * Math.pow(t, 1.4)), 0.85) * (0.55 + 0.45 * t);
      return w0 * (0.8 + 0.2 * Math.pow(0.5 + 0.5 * Math.cos(2 * Math.PI * lobes * Math.pow(t, 0.85)), 0.6)) + 0.02 * (1 - t) * (t < 0.08 ? 1 : 0);
    });
  },
  birch: () => pinnateOutline(t => {
    const w0 = 0.4 * Math.pow(Math.sin(Math.PI * Math.pow(t, 0.72)), 0.9) * (t < 0.06 ? 0.6 + t * 6 : 1);
    const tooth = 1 + 0.045 * ((t * 22) % 1) + 0.02 * ((t * 11) % 1);
    return w0 * tooth;
  }),
  maple: (r) => {
    // five lobes (Acer mono): angles from the tip direction, lengths
    const lobes = [[-124, 0.6], [-62, 0.92], [0, 1], [62, 0.92], [124, 0.6]];
    const sinusR = 0.46 + r() * 0.05;
    const P = (deg, rad) => { const a = (deg - 90) * Math.PI / 180; return [Math.cos(a) * rad, Math.sin(a) * rad]; };
    const pts = [P(-180, 0.06)];
    const keys = [];
    lobes.forEach(([deg, len], i) => {
      const prev = i === 0 ? -165 : (lobes[i - 1][0] + deg) / 2;
      keys.push([prev, i === 0 ? 0.12 : sinusR, false]);
      keys.push([deg, len, true]);
    });
    keys.push([165, 0.12, false]);
    let last = [-180, 0.06];
    for (const [deg, rad, tip] of keys) {
      // quadratic from last to this point, bulging outward to make convex lobe edges
      const cDeg = tip ? deg - (deg - last[0]) * 0.42 : last[0] + (deg - last[0]) * 0.42;
      const cRad = (tip ? rad : last[1]) * 0.86;
      const a = P(...last), b = P(deg, rad), c = P(cDeg, cRad);
      for (let k = 1; k <= 24; k++) {
        const t = k / 24, u = 1 - t;
        pts.push([u * u * a[0] + 2 * u * t * c[0] + t * t * b[0], u * u * a[1] + 2 * u * t * c[1] + t * t * b[1]]);
      }
      last = [deg, rad];
    }
    pts.push(P(180, 0.06));
    // shift so the leaf spans roughly 0..-1 like the pinnate ones
    return pts.map(([x, y]) => [x * 0.62, y * 0.62 - 0.36]);
  },
};

function veinsFor(type, r) {
  // list of polylines in unit leaf space; [points, width]
  const V = [];
  if (type === 'maple') {
    const lobes = [-124, -62, 0, 62, 124];
    const base = [0, -0.36 + 0.02];
    for (const deg of lobes) {
      const a = (deg - 90) * Math.PI / 180;
      const len = deg === 0 ? 0.6 : Math.abs(deg) < 90 ? 0.54 : 0.33;
      const tip = [base[0] + Math.cos(a) * len, base[1] + Math.sin(a) * len];
      V.push([[base, tip], 0.011]);
      for (let k = 1; k <= 4; k++) {
        const f = k / 5;
        const p = [base[0] + (tip[0] - base[0]) * f, base[1] + (tip[1] - base[1]) * f];
        for (const s of [-1, 1]) {
          const b = a + s * 0.75;
          V.push([[p, [p[0] + Math.cos(b) * 0.12 * (1 - f * 0.5), p[1] + Math.sin(b) * 0.12 * (1 - f * 0.5)]], 0.004]);
        }
      }
    }
    return V;
  }
  V.push([[[0, 0.02], [0.01, -0.5], [0, -0.97]], 0.014]);
  const pairs = type === 'oak' ? 7 : 9;
  for (let k = 1; k <= pairs; k++) {
    const t = 0.06 + 0.86 * k / (pairs + 1) + (r() - 0.5) * 0.02;
    for (const s of [-1, 1]) {
      const reach = type === 'oak' ? 0.3 : 0.34;
      const w = reach * Math.sin(Math.PI * Math.pow(Math.min(t + 0.08, 1), type === 'oak' ? 1.4 : 0.72));
      V.push([[[0, -t], [s * w * 0.5, -t - 0.05], [s * w * 0.92, -t - 0.11]], 0.0055]);
    }
  }
  return V;
}

function strokePoly(ctx, pts) {
  ctx.beginPath();
  ctx.moveTo(...pts[0]);
  if (pts.length === 3) ctx.quadraticCurveTo(...pts[1], ...pts[2]);
  else pts.slice(1).forEach(p => ctx.lineTo(...p));
  ctx.stroke();
}

// Draws one leaf (spec in cm) onto ctx with its own depth-of-field blur.
function drawFallingLeaf(ctx, spec, S) {
  const r = rng(spec.seed ?? spec.x * 0.37 + spec.y);
  const C = LEAF_COLORS[spec.color ?? spec.type];
  const size = spec.len * S;
  const blurPx = (spec.blur ?? 0) * S;
  const dim = Math.ceil(size * 1.5 + blurPx * 6);
  const [off, x] = canvas2d(dim, dim);
  x.translate(dim / 2, dim / 2);
  x.rotate((spec.rot ?? 0) * Math.PI / 180);
  x.scale(size * Math.cos(spec.tilt ?? 0), size);
  x.translate(0, 0.5);

  const outline = OUTLINES[spec.type](r);
  const path = new Path2D();
  outline.forEach((p, i) => (i ? path.lineTo(...p) : path.moveTo(...p)));
  path.closePath();

  // petiole
  x.strokeStyle = C.tip;
  x.lineWidth = 0.016;
  x.lineCap = 'round';
  const stem = spec.type === 'maple' ? -0.33 : 0;
  strokePoly(x, [[0, stem], [0.015, stem + 0.08], [0.04, stem + 0.16]]);

  x.save();
  x.clip(path);
  const g = x.createLinearGradient(0, 0, 0, -1);
  g.addColorStop(0, C.base); g.addColorStop(0.55, C.mid); g.addColorStop(1, C.tip);
  x.fillStyle = g;
  x.fillRect(-1, -1.2, 2, 1.5);
  // autumn mottling
  for (let i = 0; i < 14; i++) {
    const cx = (r() - 0.5) * 0.7, cy = -r() * 0.95, rad = 0.04 + r() * 0.16;
    const col = C.spots[i % 2];
    const rg = x.createRadialGradient(cx, cy, 0, cx, cy, rad);
    const [R, G, B] = hex(col).map(v => Math.round(v * 255));
    rg.addColorStop(0, `rgba(${R},${G},${B},${0.25 + r() * 0.35})`);
    rg.addColorStop(1, `rgba(${R},${G},${B},0)`);
    x.fillStyle = rg;
    x.fillRect(cx - rad, cy - rad, rad * 2, rad * 2);
  }
  // one half catches the light
  const side = x.createLinearGradient(-0.45, 0, 0.45, 0);
  side.addColorStop(0, 'rgba(255,240,205,0.22)');
  side.addColorStop(0.5, 'rgba(255,240,205,0)');
  side.addColorStop(0.52, 'rgba(50,15,0,0.06)');
  side.addColorStop(1, 'rgba(50,15,0,0.22)');
  x.fillStyle = side;
  x.fillRect(-1, -1.2, 2, 1.5);
  // fine texture
  x.globalCompositeOperation = 'overlay';
  x.globalAlpha = 0.75;
  x.drawImage(noiseTile(), -0.6 + r() * 0.1, -1.15, 1.2, 1.2);
  x.globalAlpha = 1;
  x.globalCompositeOperation = 'source-over';
  // veins: thin shadow line + light line
  x.lineCap = 'round';
  for (const [pts, w] of veinsFor(spec.type, r)) {
    x.strokeStyle = 'rgba(60,20,5,0.22)';
    x.lineWidth = w * 1.8;
    x.save(); x.translate(0.004, 0.003); strokePoly(x, pts); x.restore();
    x.strokeStyle = C.vein;
    x.globalAlpha = 0.55;
    x.lineWidth = w;
    strokePoly(x, pts);
    x.globalAlpha = 1;
  }
  // darker, slightly dried margin
  x.filter = `blur(${Math.max(size * 0.006, 0.5)}px)`;
  x.strokeStyle = 'rgba(70,25,8,0.55)';
  x.lineWidth = 0.035;
  x.stroke(path);
  x.filter = 'none';
  x.restore();

  ctx.save();
  ctx.globalAlpha = spec.alpha ?? 1;
  ctx.filter = blurPx > 0.3 ? `blur(${blurPx}px)` : 'none';
  ctx.drawImage(off, (spec.x + BLEED) * S - dim / 2, (spec.y + BLEED) * S - dim / 2);
  ctx.restore();
}

// ---------------------------------------------------------------- birch trunks
function drawBirch(ctx, b, S) {
  const r = rng(b.x * 1.31 + 0.5);
  const top = b.top ?? -BLEED - 1, bottom = b.bottom ?? 100;
  const wTop = b.w * 0.85, wBot = b.w;
  const lean = b.lean ?? 0;
  const pad = 2;
  const minX = Math.min(b.x - wBot, b.x + lean - wTop) - pad, maxX = Math.max(b.x + wBot, b.x + lean + wTop) + pad;
  const Wc = Math.ceil((maxX - minX) * S), Hc = Math.ceil((bottom - top) * S);
  const [off, x] = canvas2d(Wc, Hc);
  x.scale(S, S);
  x.translate(-minX, -top);
  const path = new Path2D();
  path.moveTo(b.x + lean - wTop / 2, top);
  path.lineTo(b.x + lean + wTop / 2, top);
  path.lineTo(b.x + wBot / 2, bottom);
  path.lineTo(b.x - wBot / 2, bottom);
  path.closePath();
  x.save();
  x.clip(path);
  // cylinder shading across the trunk
  const g = x.createLinearGradient(b.x - wBot / 2, 0, b.x + wBot / 2, 0);
  g.addColorStop(0, '#d8cbbb'); g.addColorStop(0.3, '#f6efe4'); g.addColorStop(0.65, '#e4d7c6'); g.addColorStop(1, '#9d8a78');
  x.fillStyle = g;
  x.fillRect(minX, top, maxX - minX, bottom - top);
  // lenticels and branch scars
  for (let i = 0; i < (bottom - top) * 3; i++) {
    const yy = top + r() * (bottom - top);
    const cx = b.x + lean * (1 - (yy - top) / (bottom - top)) + (r() - 0.5) * b.w;
    const len = b.w * (0.1 + r() * 0.45);
    x.fillStyle = `rgba(40,28,22,${0.45 + r() * 0.5})`;
    x.fillRect(cx - len / 2, yy, len, 0.08 + r() * 0.3);
  }
  for (let i = 0; i < (bottom - top) / 5; i++) {
    const yy = top + r() * (bottom - top);
    const cx = b.x + lean * (1 - (yy - top) / (bottom - top)) + (r() - 0.5) * b.w * 0.5;
    x.fillStyle = 'rgba(30,22,18,0.85)';
    x.beginPath();
    x.moveTo(cx - b.w * 0.35, yy);
    x.quadraticCurveTo(cx, yy + 0.5 + r() * 0.6, cx + b.w * 0.35, yy);
    x.quadraticCurveTo(cx, yy + 0.25, cx - b.w * 0.35, yy);
    x.fill();
  }
  x.globalCompositeOperation = 'multiply';
  x.globalAlpha = 0.35;
  x.drawImage(noiseTile(), minX, top, maxX - minX, bottom - top);
  x.restore();

  ctx.save();
  ctx.filter = `blur(${(b.blur ?? 0) * S}px)`;
  ctx.globalAlpha = b.alpha ?? 1;
  ctx.drawImage(off, (minX + BLEED) * S, (top + BLEED) * S);
  ctx.restore();
}

// A twig entering from the frame edge with leaves along it (foreground framing).
function drawBranch(ctx, br, Wpx, Hpx, S) {
  const pts = catmull(br.pts, 120);
  const [off, x] = canvas2d(Wpx, Hpx);
  x.lineCap = 'round';
  for (let i = 1; i < pts.length; i++) {
    const t = i / (pts.length - 1);
    x.strokeStyle = '#4a2c1c';
    x.lineWidth = br.width * (1 - 0.75 * t) * S;
    x.beginPath();
    x.moveTo((pts[i - 1][0] + BLEED) * S, (pts[i - 1][1] + BLEED) * S);
    x.lineTo((pts[i][0] + BLEED) * S, (pts[i][1] + BLEED) * S);
    x.stroke();
  }
  ctx.save();
  ctx.filter = `blur(${(br.blur ?? 0) * S}px)`;
  ctx.drawImage(off, 0, 0);
  ctx.restore();
  for (const lf of br.leaves) {
    const i = Math.round(lf.t * (pts.length - 1));
    const a = pts[Math.max(i - 1, 0)], b = pts[Math.min(i + 1, pts.length - 1)];
    const ang = Math.atan2(b[1] - a[1], b[0] - a[0]) + lf.side * (lf.angle ?? 50) * Math.PI / 180;
    const d = [Math.cos(ang), Math.sin(ang)];
    const reach = lf.len * (lf.type === 'maple' ? 0.52 : 0.66);
    drawFallingLeaf(ctx, {
      ...lf, x: pts[i][0] + d[0] * reach, y: pts[i][1] + d[1] * reach,
      rot: Math.atan2(d[0], -d[1]) * 180 / Math.PI, blur: lf.blur ?? br.blur, seed: lf.t * 13 + br.width,
    }, S);
  }
}

function drawBokeh(ctx, dots, S) {
  for (const d of dots ?? []) {
    const x = (d.x + BLEED) * S, y = (d.y + BLEED) * S, rad = d.r * S;
    const [R, G, B] = hex(d.c ?? '#fff1d6').map(v => Math.round(v * 255));
    const g = ctx.createRadialGradient(x, y, rad * 0.6, x, y, rad);
    g.addColorStop(0, `rgba(${R},${G},${B},${d.a})`);
    g.addColorStop(1, `rgba(${R},${G},${B},0)`);
    ctx.save();
    ctx.globalCompositeOperation = 'screen';
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(x, y, rad, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }
}

function drawShade(ctx, shades, S) {
  // soft darkening behind light-coloured text
  for (const s of shades ?? []) {
    ctx.save();
    ctx.filter = `blur(${s.blur * S}px)`;
    ctx.globalCompositeOperation = 'multiply';
    ctx.globalAlpha = s.a;
    ctx.fillStyle = s.c;
    ctx.beginPath();
    ctx.ellipse((s.x + BLEED) * S, (s.y + BLEED) * S, s.rx * S, s.ry * S, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
}

// ---------------------------------------------------------------- v2 designs
const SKY = { linear: [[0, -2], [0, 40], ['#d9e3e4', '#ecebe2', '#f5e6d2', '#f1dcc0']] };

const FOREST_DESIGNS = {
  // 150x45: English over the sky top-left, 中文 over the misty valley on the right
  A: {
    w: 150, h: 45, bg: { ...SKY, blobs: [{ x: 30, y: 6, rx: 40, ry: 14, rot: 0, c: '#fff7ea', a: 0.8, blur: 6 }] },
    forest: [
      { ridge: [[-5, 27], [20, 24], [45, 26], [70, 21], [95, 24], [120, 27], [155, 26]], crown: 0.38, mist: 0.6, mistMax: 0.35, mistDepth: 5, blur: 0.3, noise: 1.0 },
      { ridge: [[-5, 32], [18, 29.5], [40, 31], [65, 27.5], [88, 30], [108, 36], [130, 38.5], [155, 37.5]], crown: 0.62, mist: 0.22, mistMax: 0.4, mistDepth: 6, blur: 0.35 },
      { ridge: [[-5, 37], [22, 35], [50, 38.5], [80, 37], [104, 40.5], [130, 42], [155, 41]], crown: 1.0, mist: 0.06, mistMax: 0.25, mistDepth: 8, blur: 0.36, spike: 1.3 },
    ],
    birch: [],
    leaves: [
      { type: 'oak', x: 3, y: 44, len: 16, rot: 35, tilt: 0.2, blur: 0.8 },
      { type: 'maple', x: 90, y: 13, len: 8, rot: -25, tilt: 0.35, blur: 0.02 },
      { type: 'birch', x: 103, y: 24, len: 5, rot: 70, tilt: 0.5, blur: 0.04 },
      { type: 'oak', x: 78, y: 4, len: 5.5, rot: 140, tilt: 0.2, blur: 0.1 },
      { type: 'birch', x: 112, y: 8, len: 3.4, rot: -60, tilt: 0.3, blur: 0.2 },
      { type: 'maple', x: 66, y: 30, len: 4, rot: 15, tilt: 0.5, blur: 0.15 },
      { type: 'oak', x: 118, y: 16, len: 4.5, rot: 200, tilt: 0.4, blur: 0.06 },
      { type: 'birch', x: 55, y: 9, len: 3, rot: 30, tilt: 0.3, blur: 0.25 },
      { type: 'maple', x: 149, y: 44, len: 12, rot: 60, tilt: 0.3, blur: 0.7 },
    ],
    branches: [{
      pts: [[160, -6], [148, -1], [136, 2], [126, 2]], width: 1.4, blur: 0.3,
      leaves: [
        { t: 0.15, side: 1, type: 'maple', len: 18, tilt: 0.2 },
        { t: 0.45, side: -1, type: 'maple', len: 14, tilt: 0.35, angle: 40 },
        { t: 0.7, side: 1, type: 'maple', len: 13, tilt: 0.25, angle: 70 },
        { t: 0.99, side: 0, type: 'maple', len: 10, tilt: 0.3 },
      ],
    }],
    bokeh: [{ x: 60, y: 6, r: 2.2, a: 0.25 }, { x: 128, y: 14, r: 1.6, a: 0.2 }, { x: 140, y: 30, r: 2.6, a: 0.15 }],
    glow: [{ x: 18, y: 2, r: 60, c: '#fff4de', a: 0.35 }],
  },

  // 150x45: forest high on the left with birches, misty valley bottom-right for the logo
  B: {
    w: 150, h: 45, bg: { ...SKY, blobs: [{ x: 128, y: 30, rx: 40, ry: 12, rot: 0, c: '#fbf1e4', a: 0.85, blur: 6 }] },
    forest: [
      { ridge: [[-5, 18], [20, 16], [45, 20], [70, 22], [95, 25], [125, 27], [155, 28]], crown: 0.38, mist: 0.58, mistMax: 0.35, mistDepth: 5, blur: 0.3 },
      { ridge: [[-5, 23], [18, 21.5], [42, 25], [66, 29], [86, 33], [104, 40], [130, 47], [155, 50]], crown: 0.62, mist: 0.2, mistMax: 0.4, mistDepth: 6, blur: 0.35 },
      { ridge: [[-5, 30], [16, 31], [38, 35], [58, 40], [78, 46], [100, 52], [155, 56]], crown: 1.0, mist: 0.04, mistMax: 0.2, mistDepth: 8, blur: 0.36, spike: 1.3 },
    ],
    birch: [
      { x: 2, w: 5, lean: 0.6, blur: 0.35 },
    ],
    leaves: [
      { type: 'maple', x: 70, y: 8, len: 6, rot: 20, tilt: 0.3, blur: 0.02 },
      { type: 'birch', x: 86, y: 18, len: 4, rot: -40, tilt: 0.45, blur: 0.05 },
      { type: 'oak', x: 58, y: 16, len: 4.4, rot: 160, tilt: 0.3, blur: 0.1 },
      { type: 'birch', x: 100, y: 7, len: 3, rot: 90, tilt: 0.2, blur: 0.2 },
      { type: 'maple', x: 152, y: 44, len: 15, rot: -30, tilt: 0.25, blur: 0.8 },
      { type: 'oak', x: 31, y: -2, len: 13, rot: 210, tilt: 0.3, blur: 0.75 },
      { type: 'maple', x: 112, y: 17, len: 4.5, rot: -70, tilt: 0.4, blur: 0.06 },
      { type: 'oak', x: 44, y: 9, len: 3.2, rot: 40, tilt: 0.3, blur: 0.2 },
      { type: 'birch', x: 128, y: 6, len: 3.6, rot: 150, tilt: 0.3, blur: 0.1 },
    ],
    bokeh: [{ x: 112, y: 10, r: 2, a: 0.22 }, { x: 76, y: 28, r: 1.4, a: 0.18 }],
    glow: [{ x: 120, y: 4, r: 55, c: '#fff4de', a: 0.32 }],
  },

  // 110x50: 秋收/冬藏/温养 over the sky; "Foci health" (cream) on a dark hillside bottom-left
  C: {
    w: 110, h: 50, bg: { ...SKY, blobs: [{ x: 80, y: 12, rx: 32, ry: 14, rot: 0, c: '#fff7ea', a: 0.8, blur: 5 }] },
    forest: [
      { ridge: [[-5, 30], [20, 28], [45, 33], [70, 31], [95, 34], [115, 33]], crown: 0.38, mist: 0.6, mistMax: 0.35, mistDepth: 5, blur: 0.3 },
      { ridge: [[-5, 24], [10, 22], [26, 23.5], [42, 31], [60, 37.5], [88, 37], [115, 39]], crown: 0.62, mist: 0.24, mistMax: 0.35, mistDepth: 6, blur: 0.35 },
      { ridge: [[-5, 26], [8, 24.5], [22, 25.5], [34, 28.5], [46, 37], [58, 43], [76, 45], [100, 43.5], [115, 44]], crown: 1.0, mist: 0.0, mistMax: 0.12, mistDepth: 10, blur: 0.36, spike: 1.3, shade: 0.8 },
    ],
    birch: [],
    leaves: [
      { type: 'oak', x: 50, y: 8, len: 6, rot: -30, tilt: 0.35, blur: 0.02 },
      { type: 'birch', x: 64, y: 4, len: 3.8, rot: 60, tilt: 0.3, blur: 0.08 },
      { type: 'maple', x: 38, y: 13, len: 3.6, rot: 100, tilt: 0.4, blur: 0.16 },
      { type: 'birch', x: 96, y: 46, len: 9, rot: -120, tilt: 0.3, blur: 0.6 },
      { type: 'oak', x: 82, y: 6, len: 4, rot: 110, tilt: 0.4, blur: 0.06 },
      { type: 'maple', x: 106, y: 9, len: 4.6, rot: -40, tilt: 0.3, blur: 0.12 },
    ],
    shade: [{ x: 20, y: 38, rx: 27, ry: 13, c: '#3a1608', a: 0.5, blur: 4 }],
    branches: [{
      pts: [[-8, -5], [2, 0], [12, 2.5], [22, 2]], width: 1.3, blur: 0.3,
      leaves: [
        { t: 0.18, side: -1, type: 'maple', len: 16, tilt: 0.25 },
        { t: 0.48, side: 1, type: 'maple', len: 12, tilt: 0.3, angle: 45 },
        { t: 0.75, side: -1, type: 'maple', len: 11, tilt: 0.2, angle: 65 },
        { t: 0.99, side: 0, type: 'maple', len: 8.5, tilt: 0.35 },
      ],
    }],
    bokeh: [{ x: 88, y: 4, r: 1.8, a: 0.2 }],
    glow: [{ x: 95, y: 0, r: 45, c: '#fff4de', a: 0.32 }],
  },

  // 110x50: seal centred in a clearing framed by birches and falling leaves
  D: {
    w: 110, h: 50, bg: { ...SKY, blobs: [{ x: 55, y: 22, rx: 30, ry: 16, rot: 0, c: '#fff8ec', a: 0.85, blur: 5 }] },
    forest: [
      { ridge: [[-5, 30], [20, 32], [45, 34], [60, 33.5], [85, 31], [115, 29]], crown: 0.38, mist: 0.62, mistMax: 0.35, mistDepth: 5, blur: 0.3 },
      { ridge: [[-5, 32], [18, 35], [40, 39], [55, 40.5], [72, 39], [92, 34.5], [115, 32]], crown: 0.62, mist: 0.2, mistMax: 0.38, mistDepth: 6, blur: 0.35 },
      { ridge: [[-5, 38], [20, 42], [42, 46], [58, 47.5], [76, 45.5], [96, 41], [115, 38]], crown: 1.0, mist: 0.03, mistMax: 0.18, mistDepth: 8, blur: 0.36, spike: 1.3 },
    ],
    birch: [
      { x: 3, w: 5, lean: 0.7, blur: 0.35 },
      { x: 106, w: 5.4, lean: -0.8, blur: 0.35 },
    ],
    leaves: [
      { type: 'maple', x: 30, y: 12, len: 5.5, rot: -20, tilt: 0.3, blur: 0.02 },
      { type: 'oak', x: 79, y: 10, len: 5, rot: 30, tilt: 0.35, blur: 0.03 },
      { type: 'birch', x: 26, y: 31, len: 3.6, rot: 120, tilt: 0.4, blur: 0.08 },
      { type: 'birch', x: 84, y: 28, len: 3.4, rot: -80, tilt: 0.3, blur: 0.12 },
      { type: 'maple', x: 66, y: 3, len: 2.8, rot: 70, tilt: 0.3, blur: 0.2 },
      { type: 'oak', x: 45, y: 44, len: 3, rot: 200, tilt: 0.5, blur: 0.25 },
      { type: 'maple', x: 20, y: 22, len: 4, rot: 40, tilt: 0.4, blur: 0.1 },
      { type: 'birch', x: 90, y: 16, len: 3.2, rot: 20, tilt: 0.3, blur: 0.18 },
      { type: 'maple', x: 0, y: 47, len: 13, rot: 30, tilt: 0.3, blur: 0.7 },
      { type: 'oak', x: 112, y: 2, len: 12, rot: 230, tilt: 0.3, blur: 0.7 },
    ],
    bokeh: [{ x: 38, y: 6, r: 1.8, a: 0.2 }, { x: 72, y: 20, r: 1.3, a: 0.15 }],
    glow: [{ x: 55, y: 8, r: 45, c: '#fff4de', a: 0.35 }],
  },
};

function renderForest(id, S) {
  const D = FOREST_DESIGNS[id];
  const Wpx = Math.round((D.w + 2 * BLEED) * S), Hpx = Math.round((D.h + 2 * BLEED) * S);
  const [cv, ctx] = canvas2d(Wpx, Hpx);
  const seed = id.charCodeAt(0);
  drawBackground(ctx, D.bg, Wpx, Hpx, S);
  drawBokeh(ctx, D.bokeh, S);
  D.forest.forEach((layer, i) => drawForest(ctx, layer, Wpx, Hpx, S, seed * 0.17 + i * 3.1));
  // far (thin) trunks first, near ones last
  [...D.birch].sort((a, b) => a.w - b.w).forEach(b => drawBirch(ctx, b, S));
  drawShade(ctx, D.shade, S);
  // leaves: most blurred (closest) last
  [...D.leaves].sort((a, b) => (a.blur ?? 0) - (b.blur ?? 0)).forEach(l => drawFallingLeaf(ctx, l, S));
  (D.branches ?? []).forEach(br => drawBranch(ctx, br, Wpx, Hpx, S));
  drawGlow(ctx, D.glow, S);
  grain(ctx, Wpx, Hpx, 6, 0.321 + seed);
  return cv;
}

window.FOREST_DESIGNS = FOREST_DESIGNS;
window.renderForestBackground = (id, S) => renderForest(id, S).toDataURL('image/png');
