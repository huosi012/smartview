// Render the board: measure layout, export PDF and preview PNGs.
// usage: node render.js <source dir> <out dir> [--pdf] [--theme=yellow]
// Writes preview.png (screen size) and, with --pdf, board.pdf at 760 x 1760 mm.
const path = require('path');
const { chromium } = require('/opt/node-tools/node_modules/playwright');

const [, , boardDir, outDir, ...flags] = process.argv;
const PX_PER_MM = 96 / 25.4;
const theme = (flags.find((f) => f.startsWith('--theme=')) || '').slice(8);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: Math.round(760 * PX_PER_MM), height: Math.round(1760 * PX_PER_MM) },
    deviceScaleFactor: 1,
  });
  await page.goto('file://' + path.resolve(boardDir, 'index.html') + (theme ? '?theme=' + theme : ''));
  await page.waitForLoadState('load');
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(500);

  const report = await page.evaluate((pxPerMm) => {
    const mm = (v) => Math.round((v / pxPerMm) * 10) / 10;
    const board = document.querySelector('.board');
    board.style.height = 'auto';
    document.querySelector('main').style.flex = 'none';
    const natural = mm(board.scrollHeight);
    const parts = [...document.querySelectorAll('.header, .sec, .footer')].map((el) => {
      const r = el.getBoundingClientRect();
      return `${(el.className || '').padEnd(10)} top ${mm(r.top)}  h ${mm(r.height)}`;
    });
    board.style.height = '';
    document.querySelector('main').style.flex = '';
    // Elements whose content overflows their box.
    const over = [];
    document.querySelectorAll('.board *').forEach((el) => {
      if (el.closest('svg')) return;
      if (el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflow !== 'visible') {
        over.push(`${el.tagName}.${el.className} w ${mm(el.scrollWidth)} > ${mm(el.clientWidth)}`);
      }
    });
    const fonts = [...document.fonts].map((f) => `${f.family} ${f.weight} ${f.status}`);
    return { natural, parts, over, fonts };
  }, PX_PER_MM);
  console.log('natural height (mm):', report.natural, '/ 1760');
  report.parts.forEach((p) => console.log('  ' + p));
  if (report.over.length) console.log('overflow:', report.over);
  console.log('fonts:', report.fonts.join(' | '));

  await page.screenshot({ path: path.join(outDir, 'preview.png'), fullPage: false });

  if (flags.includes('--pdf')) {
    await page.pdf({
      path: path.join(outDir, 'board.pdf'),
      width: '760mm',
      height: '1760mm',
      printBackground: true,
      preferCSSPageSize: true,
    });
    console.log('pdf written');
  }
  await browser.close();
})();
