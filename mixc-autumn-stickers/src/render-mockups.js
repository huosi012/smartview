// Renders each layered SVG to a flat preview PNG, plus an overview sheet laid
// out like the summer file.
// usage: node render-mockups.js <layeredDir> <outDir> <fontDir> [pxPerMm=2] [title]
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ITEMS = [
  { file: 'A_150x45cm.svg', w: 1500, h: 450 },
  { file: 'B_150x45cm.svg', w: 1500, h: 450 },
  { file: 'C_110x50cm.svg', w: 1100, h: 500 },
  { file: 'D_110x50cm.svg', w: 1100, h: 500 },
];

const url = p => 'file://' + path.resolve(p);

async function shoot(page, html, w, h, out) {
  // load from a file:// URL so the page may reach the local SVGs, images and fonts
  const tmp = out.replace(/\.png$/, '.tmp.html');
  fs.writeFileSync(tmp, html);
  await page.setViewportSize({ width: Math.round(w), height: Math.round(h) });
  await page.goto(url(tmp), { waitUntil: 'load' });
  fs.unlinkSync(tmp);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(500);
  await page.screenshot({ path: out });
}

(async () => {
  const [layered, outDir, fontDir, S = '2', title = '万象城车贴 · 秋冬 · 每个×2'] = process.argv.slice(2);
  const k = +S;
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage();

  for (const it of ITEMS) {
    const html = `<body style="margin:0"><object type="image/svg+xml" data="${url(path.join(layered, it.file))}"
      style="display:block;width:${it.w * k}px;height:${it.h * k}px"></object></body>`;
    const out = path.join(outDir, it.file.replace('.svg', '.png'));
    await shoot(page, html, it.w * k, it.h * k, out);
    console.log(out);
  }

  // overview sheet: 1 px = 1 mm * scale
  const s = 0.62;
  const obj = it => `<object type="image/svg+xml" data="${url(path.join(layered, it.file))}"
    style="width:${it.w * s}px;height:${it.h * s}px;display:block;box-shadow:0 6px 18px rgba(0,0,0,.35)"></object>`;
  const html = `<!doctype html><meta charset="utf-8"><style>
    @font-face{font-family:Cn;src:url('${url(path.join(fontDir, 'NotoSansSC-500.ttf'))}')}
    body{margin:0;background:#5f5f5f;font-family:Cn;color:#f3f3f3}
    h1{font-weight:500;font-size:56px;margin:40px 0 34px 230px;letter-spacing:2px}
    .row{display:flex;align-items:center;gap:44px;margin:0 0 56px 0}
    .lab{width:186px;text-align:right;font-size:26px;color:#e8e8e8}
    .note{margin:-20px 0 0 230px;font-size:20px;color:#cfcfcf}
  </style>
  <h1>${title}</h1>
  <div class="row"><div class="lab">150×45cm</div>${obj(ITEMS[0])}${obj(ITEMS[1])}</div>
  <div class="row"><div class="lab">110×50cm</div>${obj(ITEMS[2])}${obj(ITEMS[3])}</div>
  <div class="note">效果预览 · logo 为截图描摹示意，制作请使用源文件矢量 logo</div>`;
  const W = 230 + 1500 * s * 2 + 44 + 80, H = 40 + 56 + 34 + 450 * s + 500 * s + 56 * 2 + 70;
  const out = path.join(outDir, 'overview.png');
  await shoot(page, html, W, H, out);
  console.log(out);
  await browser.close();
})();
