// 门前灯箱效果图：商场店铺门口场景 + 立式背光灯箱。
// 用法: node mockup.cjs <灯箱画面.png> <字体目录> <输出.jpg>
// 场景按透视比例画：相机高 1.6 m，灯箱距相机 5 m、店面玻璃距相机 7 m，
// 灯箱 1.26 × 2.66 m 按同一比例缩放，所以和门、店招的大小关系是真实的。
const { pathToFileURL } = require("node:url");
const { resolve, dirname, join } = require("node:path");
const { writeFileSync, unlinkSync } = require("node:fs");
const { chromium } = require("playwright");

const [posterPath, fontDir, outPath] = process.argv.slice(2);
const poster = pathToFileURL(resolve(posterPath)).href;
const font = (f) => pathToFileURL(resolve(fontDir, f)).href;

const VW = 1800, VH = 2400;
const HZ = 1200;            // 视平线（相机高 1.6 m）
const F = 2800;             // 焦距系数：y = HZ + 1.6 * F / z
const yAt = (z) => HZ + (1.6 * F) / z;
const WALL_Z = 7, BOX_Z = 5;
const wallBase = yAt(WALL_Z);            // 1840
const sWall = F / WALL_Z;                // 店面处 px/m
const sBox = F / BOX_Z;                  // 灯箱处 px/m
const boxBase = yAt(BOX_Z);              // 灯箱落地处

// 灯箱尺寸
const PW = 1.26 * sBox, PH = 2.66 * sBox;   // 画面
const FR = 0.055 * sBox;                     // 铝框宽 55 mm
const FEET = 0.05 * sBox;                    // 底座高
const cx = VW / 2;
const px0 = cx - PW / 2, py1 = boxBase - FEET - FR, py0 = py1 - PH;
const fx0 = px0 - FR, fy0 = py0 - FR, fw = PW + 2 * FR, fh = PH + 2 * FR;

const wallTop = 380, fasciaBottom = 560;

// 地砖透视线
let floorLines = "";
for (let z = WALL_Z - 0.8; z > 2; z -= 0.8) {
  const y = yAt(z);
  if (y < VH) floorLines += `<line x1="0" y1="${y}" x2="${VW}" y2="${y}"/>`;
}
for (let k = -8; k <= 8; k++) {
  const xb = cx + k * 0.8 * sWall;
  const x2 = cx + (xb - cx) * (VH - HZ) / (wallBase - HZ);
  floorLines += `<line x1="${xb}" y1="${wallBase}" x2="${x2}" y2="${VH}"/>`;
}
// 天花板分格线
let ceilLines = "";
for (let k = -6; k <= 6; k++) {
  const xb = cx + k * 1.2 * sWall;
  const x2 = cx + (xb - cx) * HZ / (HZ - wallTop);
  ceilLines += `<line x1="${xb}" y1="${wallTop}" x2="${x2}" y2="0"/>`;
}
for (const z of [7.6, 9, 11.5]) {
  // 天花板在相机上方约 1.9 m（层高 3.5 m）
  const y = HZ - (1.9 * F) / (z - 3.6);
  if (y > 0 && y < wallTop) ceilLines += `<line x1="0" y1="${y}" x2="${VW}" y2="${y}"/>`;
}
// 筒灯
let lights = "";
for (const [y, rx, xs] of [[300, 26, [-2, -1, 0, 1, 2]], [130, 40, [-1.5, -0.5, 0.5, 1.5]]]) {
  for (const k of xs) {
    const x = cx + k * (y === 300 ? 330 : 520);
    lights += `<ellipse cx="${x}" cy="${y}" rx="${rx * 2.6}" ry="${rx}" fill="#FFF7E6" opacity="0.55" filter="url(#blur18)"/>`;
    lights += `<ellipse cx="${x}" cy="${y}" rx="${rx}" ry="${rx * 0.32}" fill="#FFFFFF"/>`;
  }
}

// 店面：左门 + 玻璃橱窗，竖框位置
const mullions = [120, 470, 1330, 1680];
const doorX0 = 150, doorX1 = 470;
const doorTop = wallBase - 2.3 * sWall;

const wall = `
  <!-- 天花 -->
  <rect x="0" y="0" width="${VW}" height="${wallTop}" fill="url(#ceil)"/>
  <g stroke="#C9CDD4" stroke-width="2">${ceilLines}</g>
  ${lights}
  <!-- 店招 -->
  <rect x="0" y="${wallTop}" width="${VW}" height="${fasciaBottom - wallTop}" fill="url(#fascia)"/>
  <rect x="0" y="${fasciaBottom - 8}" width="${VW}" height="8" fill="#FFF2CF"/>
  <rect x="0" y="${fasciaBottom - 4}" width="${VW}" height="30" fill="#FFF2CF" opacity="0.45" filter="url(#blur18)"/>
  <g transform="translate(180 ${(wallTop + fasciaBottom) / 2})">
    <g transform="rotate(-40)"><path d="M0 0 Q22 -18 48 0 Q26 18 0 0Z" fill="#46C46F"/></g>
    <text x="64" y="26" font-family="NotoBlack" font-size="72" fill="#FFFFFF" letter-spacing="6">叶子书房</text>
    <text x="440" y="20" font-family="NotoMedium" font-size="34" fill="#C8D0DE" letter-spacing="2">学而思魔法校</text>
  </g>
  <!-- 两侧石材柱 -->
  <rect x="0" y="${fasciaBottom}" width="${mullions[0]}" height="${wallBase - fasciaBottom}" fill="url(#stone)"/>
  <rect x="${mullions[3]}" y="${fasciaBottom}" width="${VW - mullions[3]}" height="${wallBase - fasciaBottom}" fill="url(#stone)"/>
  <g stroke="#BDB6AC" stroke-width="2">
    ${[0.6, 1.2, 1.8, 2.4, 3.0].map((m) => `<line x1="0" y1="${wallBase - m * sWall}" x2="${mullions[0]}" y2="${wallBase - m * sWall}"/><line x1="${mullions[3]}" y1="${wallBase - m * sWall}" x2="${VW}" y2="${wallBase - m * sWall}"/>`).join("")}
  </g>
  <!-- 玻璃与店内 -->
  <rect x="${mullions[0]}" y="${fasciaBottom}" width="${mullions[3] - mullions[0]}" height="${wallBase - fasciaBottom}" fill="url(#glass)"/>
  <g filter="url(#blur10)" opacity="0.9">
    <rect x="560" y="${wallBase - 1.9 * sWall}" width="260" height="${1.9 * sWall}" fill="#D8C7A8"/>
    <rect x="1000" y="${wallBase - 2.1 * sWall}" width="300" height="${2.1 * sWall}" fill="#CDB995"/>
    <rect x="1400" y="${wallBase - 1.6 * sWall}" width="240" height="${1.6 * sWall}" fill="#DCCDB1"/>
    <rect x="520" y="${wallBase - 0.75 * sWall}" width="900" height="26" fill="#F6F1E8"/>
    <rect x="1340" y="${wallBase - 0.75 * sWall}" width="320" height="26" fill="#F6F1E8"/>
    <ellipse cx="700" cy="${fasciaBottom + 90}" rx="120" ry="30" fill="#FFF8E8"/>
    <ellipse cx="1150" cy="${fasciaBottom + 90}" rx="120" ry="30" fill="#FFF8E8"/>
    <ellipse cx="1550" cy="${fasciaBottom + 90}" rx="100" ry="26" fill="#FFF8E8"/>
    <circle cx="640" cy="${wallBase - 1.05 * sWall}" r="34" fill="#7A6A5A"/>
    <rect x="606" y="${wallBase - 0.95 * sWall}" width="68" height="${0.2 * sWall}" rx="20" fill="#4F79C9"/>
    <circle cx="1480" cy="${wallBase - 1.05 * sWall}" r="32" fill="#6B5B4C"/>
    <rect x="1448" y="${wallBase - 0.95 * sWall}" width="64" height="${0.2 * sWall}" rx="20" fill="#E07B5A"/>
  </g>
  <rect x="${mullions[0]}" y="${fasciaBottom}" width="${mullions[3] - mullions[0]}" height="${wallBase - fasciaBottom}" fill="url(#glassTint)"/>
  <g fill="#FFFFFF" opacity="0.22">
    <polygon points="260,${fasciaBottom} 380,${fasciaBottom} 200,${wallBase} 80,${wallBase}"/>
    <polygon points="1460,${fasciaBottom} 1520,${fasciaBottom} 1400,${wallBase} 1340,${wallBase}"/>
    <polygon points="1560,${fasciaBottom} 1640,${fasciaBottom} 1510,${wallBase} 1430,${wallBase}"/>
  </g>
  <!-- 门 -->
  <rect x="${doorX0}" y="${doorTop}" width="${doorX1 - doorX0}" height="${wallBase - doorTop}" fill="none" stroke="#7D8590" stroke-width="10"/>
  <line x1="${(doorX0 + doorX1) / 2}" y1="${doorTop}" x2="${(doorX0 + doorX1) / 2}" y2="${wallBase}" stroke="#7D8590" stroke-width="6"/>
  <rect x="${(doorX0 + doorX1) / 2 - 26}" y="${wallBase - 1.45 * sWall}" width="9" height="${0.6 * sWall}" rx="4" fill="#E6E9ED" stroke="#8D949E" stroke-width="2"/>
  <rect x="${(doorX0 + doorX1) / 2 + 17}" y="${wallBase - 1.45 * sWall}" width="9" height="${0.6 * sWall}" rx="4" fill="#E6E9ED" stroke="#8D949E" stroke-width="2"/>
  <!-- 竖框与踢脚 -->
  ${mullions.map((x) => `<rect x="${x - 7}" y="${fasciaBottom}" width="14" height="${wallBase - fasciaBottom}" fill="#6E7680"/>`).join("")}
  <rect x="0" y="${doorTop - 7}" width="${mullions[3]}" height="14" fill="#6E7680"/>
  <rect x="0" y="${wallBase - 26}" width="${VW}" height="26" fill="#4B525C"/>
`;

const box = `
  <!-- 背光光晕 -->
  <rect x="${fx0 - 30}" y="${fy0 - 30}" width="${fw + 60}" height="${fh + 60}" rx="40" fill="#5B8CFF" opacity="0.65" filter="url(#blur60)"/>
  <!-- 底座 -->
  <rect x="${fx0 + 40}" y="${py1 + FR - 4}" width="${fw * 0.22}" height="${FEET + 4}" rx="4" fill="url(#foot)"/>
  <rect x="${fx0 + fw - 40 - fw * 0.22}" y="${py1 + FR - 4}" width="${fw * 0.22}" height="${FEET + 4}" rx="4" fill="url(#foot)"/>
  <!-- 铝框 -->
  <rect x="${fx0}" y="${fy0}" width="${fw}" height="${fh}" rx="14" fill="url(#alu)" stroke="#8F969F" stroke-width="2"/>
  <rect x="${px0 - 5}" y="${py0 - 5}" width="${PW + 10}" height="${PH + 10}" rx="4" fill="#7D848D"/>
  <!-- 画面 -->
  <image href="${poster}" x="${px0}" y="${py0}" width="${PW}" height="${PH}" preserveAspectRatio="none"/>
  <rect x="${px0}" y="${py0}" width="${PW}" height="${PH}" fill="url(#sheen)"/>
  <rect x="${px0}" y="${py0}" width="${PW}" height="${PH}" fill="none" stroke="#000" stroke-opacity="0.18" stroke-width="6"/>
`;

const html = `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: NotoBlack; src: url(${font("NotoSansSC-900.ttf")}); }
@font-face { font-family: NotoMedium; src: url(${font("NotoSansSC-500.ttf")}); }
html, body { margin: 0; background: #fff; }
svg { display: block; }
</style></head><body>
<svg xmlns="http://www.w3.org/2000/svg" width="${VW}" height="${VH}" viewBox="0 0 ${VW} ${VH}">
<defs>
  <filter id="blur10" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="10"/></filter>
  <filter id="blur18" x="-50%" y="-200%" width="200%" height="500%"><feGaussianBlur stdDeviation="18"/></filter>
  <filter id="blur60" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="60"/></filter>
  <filter id="blur6"><feGaussianBlur stdDeviation="6"/></filter>
  <linearGradient id="ceil" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#E7E9ED"/><stop offset="1" stop-color="#F4F5F7"/></linearGradient>
  <linearGradient id="fascia" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3A414D"/><stop offset="1" stop-color="#262B33"/></linearGradient>
  <linearGradient id="stone" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#E4DFD7"/><stop offset="1" stop-color="#D3CDC3"/></linearGradient>
  <linearGradient id="glass" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#EDE7DC"/><stop offset="1" stop-color="#E2D8C6"/></linearGradient>
  <linearGradient id="glassTint" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#A9C3DA" stop-opacity="0.45"/><stop offset="0.5" stop-color="#C9DAE8" stop-opacity="0.25"/><stop offset="1" stop-color="#9FB6CC" stop-opacity="0.45"/></linearGradient>
  <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#D9DCE1"/><stop offset="1" stop-color="#EEF0F2"/></linearGradient>
  <linearGradient id="alu" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#C9CED5"/><stop offset="0.08" stop-color="#F4F5F7"/><stop offset="0.5" stop-color="#DADDE2"/><stop offset="0.92" stop-color="#F1F2F4"/><stop offset="1" stop-color="#B9BFC7"/></linearGradient>
  <linearGradient id="foot" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9AA1AA"/><stop offset="1" stop-color="#5E656E"/></linearGradient>
  <linearGradient id="sheen" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.10"/><stop offset="0.45" stop-color="#FFFFFF" stop-opacity="0"/><stop offset="1" stop-color="#000000" stop-opacity="0.04"/></linearGradient>
  <linearGradient id="fadeWall" x1="0" y1="${wallBase}" x2="0" y2="${wallBase + 420}" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#fff" stop-opacity="0.32"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <linearGradient id="fadeBox" x1="0" y1="${boxBase}" x2="0" y2="${VH}" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#fff" stop-opacity="0.42"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <radialGradient id="vignette" cx="0.5" cy="0.5" r="0.75"><stop offset="0.6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="0.22"/></radialGradient>
  <mask id="mWall"><rect x="0" y="${wallBase}" width="${VW}" height="${VH - wallBase}" fill="url(#fadeWall)"/></mask>
  <mask id="mBox"><rect x="0" y="${boxBase}" width="${VW}" height="${VH - boxBase}" fill="url(#fadeBox)"/></mask>
  <g id="wall">${wall}</g>
  <g id="box">${box}</g>
</defs>
<!-- 地面 + 倒影 -->
<rect x="0" y="${wallBase}" width="${VW}" height="${VH - wallBase}" fill="url(#floor)"/>
<g mask="url(#mWall)"><g transform="translate(0 ${2 * wallBase}) scale(1 -1)" filter="url(#blur6)"><use href="#wall"/></g></g>
<g mask="url(#mBox)"><g transform="translate(0 ${2 * boxBase}) scale(1 -1)" filter="url(#blur6)"><use href="#box"/></g></g>
<g stroke="#FFFFFF" stroke-opacity="0.7" stroke-width="2">${floorLines}</g>
<ellipse cx="${cx}" cy="${boxBase + 40}" rx="${fw * 0.85}" ry="110" fill="#6F9BFF" opacity="0.32" filter="url(#blur60)"/>
<use href="#wall"/>
<ellipse cx="${cx}" cy="${boxBase + 2}" rx="${fw * 0.5}" ry="14" fill="#1E2430" opacity="0.35" filter="url(#blur6)"/>
<use href="#box"/>
<rect x="0" y="0" width="${VW}" height="${VH}" fill="url(#vignette)"/>
</svg></body></html>`;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: VW, height: VH } });
  // 写成本地文件再打开，页面才能读取同样在本地的画面图片和字体
  const tmp = join(dirname(resolve(outPath)), ".mockup.tmp.html");
  writeFileSync(tmp, html);
  await page.goto(pathToFileURL(tmp).href, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: outPath, type: "jpeg", quality: 92 });
  await browser.close();
  unlinkSync(tmp);
  console.log("wrote", outPath);
})();
