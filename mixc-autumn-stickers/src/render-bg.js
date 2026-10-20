// Renders the four backgrounds to PNG.
// usage: node render-bg.js <outDir> [pxPerCm=40] [ids=ABCD] [variant=v1|v2]
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const [outDir, S = '40', ids = 'ABCD', variant = 'v1'] = process.argv.slice(2);
  const fn = variant === 'v2' ? 'renderForestBackground' : 'renderBackground';
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage();
  page.on('console', m => console.log('[page]', m.text()));
  page.on('pageerror', e => console.error('[page error]', e.message));
  await page.goto('file://' + path.join(__dirname, 'bg.html'));
  for (const id of ids) {
    const t0 = Date.now();
    const url = await page.evaluate(([fn, id, S]) => window[fn](id, S), [fn, id, +S]);
    const file = path.join(outDir, `bg_${id}.png`);
    fs.writeFileSync(file, Buffer.from(url.split(',')[1], 'base64'));
    console.log(id, file, ((Date.now() - t0) / 1000).toFixed(1) + 's');
  }
  await browser.close();
})();
