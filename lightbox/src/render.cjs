// 用 Chromium 把 build.py 生成的 SVG 打印成矢量 PDF。
// 用法: node render.cjs <输入.svg> <输出目录>
// 输出: lightbox_1260x2660mm.pdf（成品尺寸）与 lightbox_bleed30_1320x2720mm.pdf（含 30mm 出血）
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { chromium } = require("playwright");

const [svgPath, outDir] = process.argv.slice(2);
const W = 1260, H = 2660, BLEED = 30;
const src = readFileSync(svgPath, "utf8");

function sized(svg, x, y, w, h) {
  return svg.replace(/<svg [^>]*>/, (tag) =>
    tag
      .replace(/width="[^"]*"/, `width="${w}mm"`)
      .replace(/height="[^"]*"/, `height="${h}mm"`)
      .replace(/viewBox="[^"]*"/, `viewBox="${x} ${y} ${w} ${h}"`)
  );
}

const variants = [
  { file: `lightbox_${W}x${H}mm.pdf`, svg: sized(src, 0, 0, W, H), w: W, h: H },
  {
    file: `lightbox_bleed${BLEED}_${W + 2 * BLEED}x${H + 2 * BLEED}mm.pdf`,
    svg: sized(src, -BLEED, -BLEED, W + 2 * BLEED, H + 2 * BLEED),
    w: W + 2 * BLEED,
    h: H + 2 * BLEED,
  },
];

(async () => {
const browser = await chromium.launch();
const page = await browser.newPage();
for (const v of variants) {
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>
    @page { size: ${v.w}mm ${v.h}mm; margin: 0 }
    html, body { margin: 0; padding: 0 }
    svg { display: block }
  </style></head><body>${v.svg}</body></html>`;
  await page.setContent(html, { waitUntil: "load" });
  await page.pdf({
    path: join(outDir, v.file),
    width: `${v.w}mm`,
    height: `${v.h}mm`,
    printBackground: true,
    preferCSSPageSize: true,
    pageRanges: "1",
  });
  console.log("wrote", v.file);
}
await browser.close();
})();
