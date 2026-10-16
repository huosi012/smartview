const { chromium } = require('playwright');
(async () => {
  const [,, htmlPath, pdfPath] = process.argv;
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.goto('file://' + htmlPath, { waitUntil: 'networkidle' });
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(400);
  // overflow report: content boxes whose children spill past the box
  const report = await p.evaluate(() => {
    const out = [];
    document.querySelectorAll('.page').forEach((pg, i) => {
      const c = pg.querySelector('.content');
      if (!c) return;
      const cb = c.getBoundingClientRect();
      let maxB = 0;
      c.querySelectorAll('*').forEach(el => {
        if (el.closest('.seal')) return;
        const r = el.getBoundingClientRect();
        if (r.height) maxB = Math.max(maxB, r.bottom);
      });
      out.push(`page ${i + 1}: content ${(cb.height / 3.7795).toFixed(1)}mm, used ${((maxB - cb.top) / 3.7795).toFixed(1)}mm${maxB > cb.bottom + 0.5 ? '  <-- OVERFLOW' : ''}`);
    });
    return out;
  });
  console.log(report.join('\n'));
  await p.pdf({ path: pdfPath, preferCSSPageSize: true, printBackground: true });
  await b.close();
})();
