// Render background layers, icons and diagram from the PDF's HTML for use in the Word version.
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [,, htmlPath, outDir] = process.argv;
  const b = await chromium.launch();
  const MM = 96 / 25.4;

  // ---- inner-page background: decoration + header/footer rules, no text or content
  let p = await b.newPage({ viewport: { width: 900, height: 1200 }, deviceScaleFactor: 2 });
  await p.goto('file://' + htmlPath); await p.evaluate(() => document.fonts.ready);
  await p.addStyleTag({ content: `
    .page .content{visibility:hidden!important}
    header.run *, footer.run *{color:transparent!important}
    .run-logo{visibility:hidden!important}` });
  let pages = await p.$$('.page');
  await pages[1].screenshot({ path: `${outDir}/bg_inner.png` });

  // ---- cover background: everything except text and logo; record text line boxes
  await p.close();
  p = await b.newPage({ viewport: { width: 900, height: 1200 }, deviceScaleFactor: 2.6 });
  await p.goto('file://' + htmlPath); await p.evaluate(() => document.fonts.ready);
  const layout = await p.evaluate((MM) => {
    const cover = document.querySelector('.page.cover');
    const o = cover.getBoundingClientRect();
    const box = el => { const r = el.getBoundingClientRect(); return { x: (r.left - o.left) / MM, y: (r.top - o.top) / MM, w: r.width / MM, h: r.height / MM }; };
    const st = el => { const c = getComputedStyle(el); return { size: parseFloat(c.fontSize) * 0.75, weight: c.fontWeight, color: c.color, ls: parseFloat(c.letterSpacing) || 0, lh: parseFloat(c.lineHeight) / MM }; };
    const runsOf = el => [...el.childNodes].map(n => n.nodeType === 3 ? { t: n.textContent, ...st(el) } : { t: n.textContent, ...st(n) }).filter(r => r.t.trim() !== '' || r.t === ' ');
    const items = [];
    const add = (sel, key) => cover.querySelectorAll(sel).forEach((el, i) => items.push({ key: key + (i || ''), ...box(el), ...st(el), runs: runsOf(el) }));
    add('.cv-ref span', 'ref');
    add('.cv-eyebrow', 'eyebrow'); add('.cv-title h1', 'h1'); add('.cv-sub', 'sub');
    add('.cv-model span', 'model_k'); add('.cv-model b', 'model_v');
    add('.cv-side dt', 'dt'); add('.cv-side dd', 'dd');
    add('.cv-co .cn', 'cn'); add('.cv-co .en', 'en'); add('.cv-contact div', 'contact');
    const logo = box(cover.querySelector('.cv-logo'));
    return { items, logo };
  }, MM);
  fs.writeFileSync(`${outDir}/cover_layout.json`, JSON.stringify(layout, null, 1));
  await p.addStyleTag({ content: `
    .cover *{color:transparent!important}
    .cv-logo{visibility:hidden!important}` });
  pages = await p.$$('.page');
  await pages[0].screenshot({ path: `${outDir}/bg_cover.png` });

  // ---- install diagram (from the last page)
  const plan = await p.$('svg.plan');
  await p.evaluate(el => { el.style.width = '120mm'; el.style.height = 'auto'; el.style.flex = 'none'; }, plan);
  await plan.screenshot({ path: `${outDir}/plan.png`, omitBackground: true });
  await p.close();

  // ---- icons as PNG (teal; alert / ground in orange)
  const icons = await (async () => {
    const pg = await b.newPage({ deviceScaleFactor: 4 });
    await pg.goto('file://' + htmlPath);
    const list = await pg.evaluate(() => {
      const seen = {};
      document.querySelectorAll('svg.ic').forEach(s => { const k = s.innerHTML; if (!seen[k]) seen[k] = s.outerHTML; });
      return Object.values(seen);
    });
    return { pg, list };
  })();
  const { pg, list } = icons;
  await pg.setContent('<html><body style="margin:0;background:transparent"><div id="h"></div></body></html>');
  const names = JSON.parse(process.argv[4]);
  for (const [name, inner, color] of names) {
    await pg.evaluate(([inner, color]) => {
      document.getElementById('h').innerHTML = `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" style="display:block">${inner}</svg>`;
    }, [inner, color]);
    const el = await pg.$('#h svg');
    await el.screenshot({ path: `${outDir}/ic_${name}.png`, omitBackground: true });
  }
  await b.close();
  console.log('icons from page:', list.length, 'written:', names.length);
})();
