// 导出海报：印刷 JPG（约 100dpi）、矢量 PDF、预览 PNG
// 用法：./fetch-fonts.sh && node render.js
const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');

const W = 800, H = 1800;            // 1px = 1mm → 80 × 180 cm
const PRINT_SCALE = 4;              // 3200 × 7200 px ≈ 102 dpi
const out = path.join(__dirname, 'output');
const name = 'xingjue-xbanner-80x180cm';

(async () => {
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const url = 'file://' + path.join(__dirname, 'index.html');

  const shoot = async (scale, file, type) => {
    const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: scale });
    await page.goto(url);
    await page.evaluate(() => document.fonts.ready);
    await page.locator('#poster').screenshot({ path: path.join(out, file), type, ...(type === 'jpeg' ? { quality: 92 } : {}) });
    return page;
  };

  const page = await shoot(1, `${name}-preview.png`, 'png');
  // 版面检查：内容不能压到底部联系栏
  const gap = await page.evaluate(() => {
    const end = document.querySelector('.end').getBoundingClientRect().bottom;
    const foot = document.querySelector('.foot').getBoundingClientRect().top;
    return Math.round(foot - end);
  });
  console.log(`活动二底部到联系栏的间距: ${gap}px${gap < 10 ? '  ⚠ 太挤' : ''}`);

  await shoot(PRINT_SCALE, `${name}-print.jpg`, 'jpeg');

  await page.emulateMedia({ media: 'screen' });
  await page.addStyleTag({ content: `@page { size: ${W}mm ${H}mm; margin: 0 } html { zoom: ${96 / 25.4} }` });
  await page.pdf({ path: path.join(out, `${name}.pdf`), width: `${W}mm`, height: `${H}mm`, printBackground: true, pageRanges: '1' });

  await browser.close();
  for (const f of fs.readdirSync(out)) console.log(f, (fs.statSync(path.join(out, f)).size / 1e6).toFixed(1) + 'MB');
})();
