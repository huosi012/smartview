// Builds 抖音封面模板.pptx: guide pages plus three frame templates where
// the watch photo sits in a window and all text stays outside the photo.
// With --preview it instead writes build/preview.pptx, a deck of sample
// covers that render.sh turns into the images the guide pages show.
const fs = require('fs');
const path = require('path');
const pptxgen = require('pptxgenjs');
const JSZip = require('jszip');

const HERE = __dirname;
const ASSETS = path.join(HERE, 'assets');
const PREVIEW = process.argv.includes('--preview');
const OUT_FILE = PREVIEW
  ? path.join(HERE, 'build', 'preview.pptx')
  : path.join(HERE, '..', '抖音封面模板.pptx');

// PowerPoint exports slides at 96 dpi, so an 11.25 x 15 in slide saves as a
// 1080 x 1440 PNG: Douyin's 3:4 homepage cover. Covers are laid out in those
// pixels and converted.
const SLIDE_W = 11.25;
const SLIDE_H = 15;
const px = (v) => v / 96;
const fpx = (v) => v * 0.75;
const asset = (name) => path.join(ASSETS, name);
const jpegAspect = (file) => { // height / width, read from the JPEG SOF marker
  const b = fs.readFileSync(file);
  for (let i = 2; i < b.length;) {
    const marker = b[i + 1];
    if (marker >= 0xc0 && marker <= 0xc2) return b.readUInt16BE(i + 5) / b.readUInt16BE(i + 7);
    i += 2 + b.readUInt16BE(i + 2);
  }
  throw new Error(`no size in ${file}`);
};

const FONT = {
  title: 'Noto Serif SC SemiBold',
  zh: 'Noto Serif SC',
  en: 'Cormorant Garamond SemiBold',
  num: 'Cormorant Garamond Medium', // used italic
  body: 'Microsoft YaHei',
};
const C = {
  champagne: 'C4A876',
  ivoryText: 'F2EDE4',
  mute: 'A39B8F',
  bronze: '8A6A3B',
  ink: '16140F',
  inkSoft: '4A453D',
  brass: 'B0925F',
  page: '121214',
  card: '1C1C20',
  grey: 'A7A39B',
  dim: '6E6A64',
};

// Photo window of each style, in cover pixels (make_assets.py has the same).
const WINDOWS = {
  noir: [96, 176, 888, 828],
  ivory: [64, 64, 952, 952],
  dossier: [72, 160, 936, 808],
};

const NAME = {
  photo: '手表照片（右键→更改图片）',
  guide: '构图参考线（导出前隐藏）',
};

// ---------------------------------------------------------------- covers

function text(slide, value, o) {
  slide.addText(value, {
    isTextBox: true, margin: 0, valign: 'middle', ...o,
    x: px(o.x), y: px(o.y), w: px(o.w), h: px(o.h),
    fontSize: fpx(o.fontSize),
  });
}

function coverBase(slide, style, photo, withGuide) {
  const [x, y, w, h] = WINDOWS[style];
  const win = { x: px(x), y: px(y), w: px(w), h: px(h) };
  slide.addImage({ placeholder: 'photo', path: asset(`photo-${style}-${photo}.jpg`), ...win, objectName: NAME.photo, altText: '手表照片' });
  if (withGuide) slide.addImage({ path: asset(`guide-${style}.png`), ...win, objectName: NAME.guide, altText: '构图参考线' });
}

// Noir gallery: black mat, champagne hairlines, centred caption.
function coverNoir(slide, d) {
  text(slide, d.shopEn, { x: 240, y: 76, w: 600, h: 36, fontFace: FONT.en, fontSize: 26, color: C.champagne, align: 'center', charSpacing: 7, objectName: '店名（英文）' });
  text(slide, d.shop, { x: 240, y: 116, w: 600, h: 32, fontFace: FONT.zh, fontSize: 22, color: '8F877B', align: 'center', charSpacing: 6, objectName: '店名' });
  text(slide, d.brand, { x: 140, y: 1042, w: 800, h: 50, fontFace: FONT.en, fontSize: 38, color: C.champagne, align: 'center', charSpacing: 10, objectName: '品牌', fit: 'shrink' });
  text(slide, d.title, { x: 80, y: 1092, w: 920, h: 124, fontFace: FONT.title, fontSize: d.size || 96, color: C.ivoryText, align: 'center', objectName: '主标题（型号）', fit: 'shrink' });
  text(slide, d.service, { x: 140, y: 1222, w: 800, h: 46, fontFace: FONT.zh, fontSize: 30, color: C.mute, align: 'center', charSpacing: 5, objectName: '服务项目', fit: 'shrink' });
  text(slide, `N° ${d.episode}`, { x: 740, y: 1318, w: 252, h: 58, fontFace: FONT.num, italic: true, fontSize: 40, color: C.champagne, align: 'right', objectName: '期数' });
}

// Ivory catalogue: printed photo on paper, editorial caption, big lot number.
function coverIvory(slide, d) {
  text(slide, d.brand, { x: 64, y: 1046, w: 640, h: 40, fontFace: FONT.en, fontSize: 32, color: C.bronze, charSpacing: 9, objectName: '品牌', fit: 'shrink' });
  text(slide, d.title, { x: 64, y: 1088, w: 700, h: 112, fontFace: FONT.title, fontSize: d.size || 92, color: C.ink, objectName: '主标题（型号）', fit: 'shrink' });
  text(slide, d.service, { x: 64, y: 1206, w: 700, h: 44, fontFace: FONT.zh, fontSize: 30, color: C.inkSoft, charSpacing: 3, objectName: '服务项目', fit: 'shrink' });
  text(slide, 'N°', { x: 840, y: 1052, w: 176, h: 40, fontFace: FONT.num, italic: true, fontSize: 36, color: C.bronze, align: 'right', objectName: 'N°' });
  text(slide, d.episode, { x: 760, y: 1080, w: 262, h: 150, fontFace: FONT.num, italic: true, fontSize: 138, color: C.bronze, align: 'right', objectName: '期数' });
  slide.addText([
    { text: d.shop, options: { fontFace: FONT.zh, fontSize: fpx(22), charSpacing: 4 } },
    { text: `  ·  ${d.shopEn}`, options: { fontFace: FONT.en, fontSize: fpx(21), charSpacing: 4 } },
  ], { isTextBox: true, x: px(400), y: px(1306), w: px(616), h: px(40), margin: 0, align: 'right', valign: 'middle', color: C.inkSoft, objectName: '店名' });
}

// Service dossier: viewfinder marks, title, record table.
function coverDossier(slide, d) {
  text(slide, `N° ${d.episode}`, { x: 760, y: 66, w: 248, h: 60, fontFace: FONT.num, italic: true, fontSize: 42, color: C.brass, align: 'right', objectName: '期数' });
  text(slide, d.title, { x: 72, y: 1008, w: 936, h: 120, fontFace: FONT.title, fontSize: d.size || 88, color: 'EDE8E0', objectName: '主标题（型号）', fit: 'shrink' });
  text(slide, d.brand, { x: 330, y: 1148, w: 678, h: 58, fontFace: FONT.zh, fontSize: 30, color: 'D9D3C8', objectName: '品牌', fit: 'shrink' });
  text(slide, d.service, { x: 330, y: 1210, w: 678, h: 58, fontFace: FONT.zh, fontSize: 30, color: 'D9D3C8', objectName: '服务项目', fit: 'shrink' });
  slide.addText([
    { text: d.shop, options: { fontFace: FONT.zh, fontSize: fpx(22), charSpacing: 4 } },
    { text: `  ·  ${d.shopEn}`, options: { fontFace: FONT.en, fontSize: fpx(21), charSpacing: 4 } },
  ], { isTextBox: true, x: px(400), y: px(1318), w: px(608), h: px(40), margin: 0, align: 'right', valign: 'middle', color: '8A857C', objectName: '店名' });
}

const STYLES = {
  noir: { fn: coverNoir, key: 'A', name: '暗夜画廊', bg: '0D0C0B' },
  ivory: { fn: coverIvory, key: 'B', name: '象牙画册', bg: 'E9E3D7' },
  dossier: { fn: coverDossier, key: 'C', name: '维修档案', bg: '131313' },
};
const RECOMMENDED = 'noir';

// Fixed words that never change per cover live on the layout.
const LAYOUT_TEXT = {
  noir: [],
  ivory: [],
  dossier: [
    ['SERVICE  RECORD', { x: 240, y: 74, w: 600, h: 44, fontFace: FONT.en, fontSize: 28, color: 'ECE6DA', align: 'center', charSpacing: 12 }],
    ['BRAND  品牌', { x: 72, y: 1148, w: 250, h: 58, fontFace: FONT.en, fontSize: 24, color: C.brass, charSpacing: 4 }],
    ['SERVICE  项目', { x: 72, y: 1210, w: 250, h: 58, fontFace: FONT.en, fontSize: 24, color: C.brass, charSpacing: 4 }],
  ],
};

const SAMPLE = {
  photo: 'omega-gmt', shop: '名表维修工作室', shopEn: 'WATCH SERVICE ATELIER', episode: '023',
  brand: 'OMEGA', title: '海马150 GMT', service: '洗油大保养 · 外观修复',
};

// Newest first, as Douyin lays out a profile. The first three are the
// shop's own current posts.
const GRID = [
  SAMPLE,
  { photo: 'longines-hydroconquest', episode: '022', brand: 'LONGINES', title: '康卡斯', service: '大保养 · 更换刻度圈' },
  { photo: 'tissot-lelocle', episode: '021', brand: 'TISSOT', title: '力洛克', service: '机芯大保养 · 外观修复' },
  { photo: 'rolex-dj-black', episode: '020', brand: 'ROLEX', title: '日志', service: '洗油大保养 · 抛光' },
  { photo: 'gp-1945', episode: '019', brand: 'GIRARD-PERREGAUX', title: '1945 方表', service: '洗油修复大保养' },
  { photo: 'montblanc', episode: '018', brand: 'MONTBLANC', title: '明星计时', service: '磕碰修复 · 洗油' },
  { photo: 'breguet-a', episode: '017', brand: 'BREGUET', title: '经典系列', service: '表壳补金修复' },
  { photo: 'iwc-portugieser', episode: '016', brand: 'IWC', title: '葡萄牙', service: '寄修 · 洗油大保养' },
  { photo: 'chopard-luc', episode: '015', brand: 'CHOPARD', title: 'L.U.C', service: '寄修 · 洗油大保养' },
].map((d) => ({ ...SAMPLE, ...d }));

const COVER_NOTES = (style) => [
  `模板 ${STYLES[style].key}「${STYLES[style].name}」使用方法：`,
  '1. 左侧缩略图右键这一页 →「复制幻灯片」，在副本上改，原模板留着下次用。',
  '2. 换照片：右键照片 →「更改图片」→ 选新照片；或者选中照片按 Delete，再点画框中间的图标插入，会自动裁成画框大小。',
  '3. 调位置：双击照片 →「裁剪」，拖动照片让表盘居中。可在「开始 → 选择 → 选择窗格」显示「构图参考线」对位，导出前再隐藏。',
  '4. 直接点文字修改：店名、期数、品牌、型号、服务项目。字多了会自动缩小。',
  '5. 导出：文件 → 导出 → 更改文件类型 → PNG → 仅当前幻灯片（1080×1440）。',
  '   WPS：文件 → 输出为图片 → 当前页；或 另存为 → PNG。',
].join('\n');

// ---------------------------------------------------------------- guide pages

function pageTitle(slide, title, sub) {
  slide.addText(title, { placeholder: 'title' });
  if (sub) {
    slide.addText(sub, { isTextBox: true, x: 0.75, y: 1.72, w: 9.75, h: 0.9, margin: 0, fontFace: FONT.body, fontSize: 19, color: C.grey, valign: 'top', objectName: '说明' });
  }
}

function numberDot(pres, slide, n, x, y, d = 0.62) {
  slide.addText(String(n), {
    shape: pres.shapes.OVAL, x, y, w: d, h: d, fill: { color: C.champagne },
    fontFace: FONT.title, fontSize: 20, color: '111111', align: 'center', valign: 'middle', margin: 0,
  });
}

function overviewPage(pres) {
  const s = pres.addSlide({ masterName: 'GUIDE', sectionTitle: '使用说明' });
  pageTitle(s, '三种画框风格，选一种用到底', '照片放进画框，文字都在照片外面，不压表。你们用柔光灯把表拍好，套进画框、改几个字就是一张封面。');
  const cards = [
    ['noir', '推荐', '黑卡纸配香槟金细线，像画廊里的展品，最稳重'],
    ['ivory', '', '米白纸张质感，像拍卖图录，在深色主页里最显眼'],
    ['dossier', '', '取景框加维修档案表格，突出专业维修'],
  ];
  cards.forEach(([style, tag, desc], i) => {
    const x = 0.75 + i * 3.325;
    const { key, name } = STYLES[style];
    s.addImage({ path: asset(`preview-${style}.jpg`), x, y: 2.75, w: 3.1, h: 4.133, objectName: `风格${key}预览`, altText: `封面风格 ${key}「${name}」示例` });
    s.addText([
      { text: `${key}  ${name}`, options: { fontFace: FONT.title, fontSize: 21, color: 'FFFFFF' } },
      ...(tag ? [{ text: `  ${tag}`, options: { fontFace: FONT.title, fontSize: 15, color: C.champagne } }] : []),
    ], { isTextBox: true, x, y: 7.03, w: 3.1, h: 0.5, margin: 0, valign: 'middle' });
    s.addText(desc, { isTextBox: true, x, y: 7.55, w: 3.1, h: 0.85, margin: 0, fontFace: FONT.body, fontSize: 14, color: C.grey, valign: 'top' });
  });

  s.addText('字体都可免费商用', { isTextBox: true, x: 0.75, y: 8.85, w: 9.75, h: 0.55, margin: 0, fontFace: FONT.title, fontSize: 24, color: 'FFFFFF' });
  const fonts = [
    ['思源宋体 SemiBold', FONT.title, false, '海马150 GMT', '型号大标题', 'Noto Serif SC'],
    ['思源宋体 Regular', FONT.zh, false, '洗油大保养 · 外观修复', '服务项目、店名', 'Noto Serif SC'],
    ['Cormorant Garamond', FONT.en, false, 'OMEGA · LONGINES', '英文品牌名', 'Cormorant'],
    ['Cormorant Garamond Italic', FONT.num, true, 'N° 023', '期数编号', 'Cormorant'],
  ];
  fonts.forEach(([name, face, italic, specimen, use, src], i) => {
    const y = 9.6 + i * 1.02;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.75, y, w: 9.75, h: 0.88, fill: { color: C.card }, line: { type: 'none' }, rectRadius: 0.08 });
    s.addText(specimen, { isTextBox: true, x: 1.0, y, w: 4.1, h: 0.88, margin: 0, fontFace: face, italic, fontSize: 26, color: 'E8D9B8', valign: 'middle' });
    s.addText([
      { text: name, options: { fontFace: FONT.title, fontSize: 16, color: 'FFFFFF', breakLine: true } },
      { text: `${use} · ${src}`, options: { fontFace: FONT.body, fontSize: 12, color: C.grey } },
    ], { isTextBox: true, x: 5.2, y, w: 3.6, h: 0.88, margin: 0, valign: 'middle' });
    s.addText('SIL OFL 1.1', { isTextBox: true, x: 8.75, y, w: 1.55, h: 0.88, margin: 0, fontFace: FONT.body, fontSize: 12, color: C.champagne, align: 'right', valign: 'middle' });
  });
  s.addText('字体在 fonts 文件夹，第一次用前先安装。', {
    isTextBox: true, x: 0.75, y: 13.75, w: 9.75, h: 0.4, margin: 0, fontFace: FONT.body, fontSize: 13, color: C.dim, valign: 'top',
  });
}

function gridPage(pres) {
  const s = pres.addSlide({ masterName: 'GUIDE', sectionTitle: '使用说明' });
  const { key, name } = STYLES[RECOMMENDED];
  pageTitle(s, '主页效果：统一后的九宫格', `下图用模板 ${key}「${name}」套了你们的表（照片取自发来的截图，仅作示意）。`);
  const mock = asset(`grid-mockup-${RECOMMENDED}.jpg`);
  s.addImage({ path: mock, x: 0.55, y: 2.55, w: 7.2, h: 7.2 * jpegAspect(mock), objectName: '主页效果图', altText: `套用模板 ${key} 后的抖音主页九宫格示意` });
  const tips = [
    ['标题克制', '型号 2–6 个字，用宋体，不描边、不用亮黄，高级感来自留白。'],
    ['文字不压照片', '照片完整干净，品牌、型号、服务都放在画框里。'],
    ['避开点赞数', '主页左下角会被点赞数挡住，模板在那里留了空。'],
    ['光线角度统一', '每块表同样的柔光、同样的角度，主页才整齐。'],
  ];
  tips.forEach(([t, d], i) => {
    const y = 2.85 + i * 2.65;
    numberDot(pres, s, i + 1, 7.85, y);
    s.addText(t, { isTextBox: true, x: 7.85, y: y + 0.78, w: 2.65, h: 0.5, margin: 0, fontFace: FONT.title, fontSize: 20, color: 'FFFFFF', valign: 'top' });
    s.addText(d, { isTextBox: true, x: 7.85, y: y + 1.3, w: 2.65, h: 1.2, margin: 0, fontFace: FONT.body, fontSize: 14, color: C.grey, valign: 'top' });
  });
}

function stepsPage(pres) {
  const s = pres.addSlide({ masterName: 'GUIDE', sectionTitle: '使用说明' });
  pageTitle(s, '出一张封面的流程', '第 1 步只做一次，以后每次从第 2 步开始，几分钟一张。');
  const steps = [
    ['安装字体（只做一次）', '打开 fonts 文件夹，双击 4 个字体文件 → 点「安装」（Mac 用「字体册」）。装好后重开 PPT / WPS，否则字体会被替换成默认字体。'],
    ['复制一页模板', '左侧缩略图右键选好的模板页 →「复制幻灯片」，在副本上改，原模板留着下次用。'],
    ['换手表照片', '右键照片 →「更改图片」→ 选新照片。或者选中照片按 Delete，再点画框中间的图标插入，会自动裁成画框大小。'],
    ['调位置', '双击照片 →「裁剪」，拖动照片让表盘居中。可在选择窗格里显示「构图参考线」对位，对好后一定再隐藏，否则会被导出。'],
    ['改文字', '点文字直接改店名、期数、品牌、型号、服务项目；型号 2–6 个字最好看。'],
    ['导出图片', 'PowerPoint：文件 → 导出 → 更改文件类型 → PNG → 仅当前幻灯片，得到 1080×1440。\nWPS：文件 → 输出为图片 → 当前页（或 另存为 → PNG）。'],
    ['发抖音时设为封面', '发布页点「选封面」→ 从相册上传这张图，主页九宫格显示的就是它。'],
  ];
  steps.forEach(([t, d], i) => {
    const y = 2.75 + i * 1.6;
    numberDot(pres, s, i + 1, 0.75, y + 0.02);
    s.addText(t, { isTextBox: true, x: 1.65, y, w: 8.85, h: 0.55, margin: 0, fontFace: FONT.title, fontSize: 22, color: 'FFFFFF', valign: 'middle' });
    s.addText(d, { isTextBox: true, x: 1.65, y: y + 0.6, w: 8.85, h: 0.9, margin: 0, fontFace: FONT.body, fontSize: 15, color: C.grey, valign: 'top', lineSpacingMultiple: 1.1 });
  });
}

function shootingPage(pres) {
  const s = pres.addSlide({ masterName: 'GUIDE', sectionTitle: '使用说明' });
  pageTitle(s, '拍摄建议：柔光 + 统一角度', '画框接近正方形，手机竖拍的照片上下会被裁掉一些。表放正中、四周留空，套进去就刚好。');
  s.addImage({ path: asset('crop-guide.png'), x: 0.75, y: 2.75, w: 4.6, h: 4.6 * 4 / 3, objectName: '裁切示意', altText: '手机竖拍照片套进画框时，上下会被裁掉' });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.65, y: 2.75, w: 4.85, h: 3.0, fill: { color: C.card }, line: { type: 'none' }, rectRadius: 0.1 });
  s.addImage({ path: asset('diagram-top.png'), x: 5.75, y: 2.8, w: 3.9 * 1000 / 760, h: 2.9, objectName: '俯视图', altText: '俯视图：表盘向左转约 25 度，手机正对表头' });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.65, y: 5.95, w: 4.85, h: 3.0, fill: { color: C.card }, line: { type: 'none' }, rectRadius: 0.1 });
  s.addImage({ path: asset('diagram-side.png'), x: 5.75, y: 6.0, w: 3.9 * 1000 / 760, h: 2.9, objectName: '侧视图', altText: '侧视图：柔光灯在左上方，镜头略高于表盘中心' });

  const rules = [
    ['光线', '一盏柔光灯（带柔光箱）从左上 45° 打，右侧放白卡给表壳补一道高光，关掉顶灯防反光。'],
    ['背景', '黑色或深灰植绒布，表离背景 30 cm 以上，背景才干净。'],
    ['角度', '表立在表枕上，表盘向左转约 25°，露出右侧表冠。'],
    ['高度', '镜头与表盘中心同高或略高 5–10°，不要从正上方俯拍。'],
    ['构图', '手机竖拍 3:4，表盘放正中，约占画面宽度六成，上下多留空。'],
    ['镜头', '用 2× 长焦，距离 20–30 cm，表盘不变形。'],
    ['细节', '表镜擦干净、指针调到 10:10、点表盘对焦，曝光略降让背景更黑。'],
    ['统一', '每块表同一套灯位和角度，九宫格才整齐。'],
  ];
  rules.forEach(([k, d], i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.75 + col * 5.0;
    const y = 9.7 + row * 1.1;
    s.addText(k, { isTextBox: true, x, y, w: 0.9, h: 0.95, margin: 0, fontFace: FONT.title, fontSize: 18, color: C.champagne, valign: 'top' });
    s.addText(d, { isTextBox: true, x: x + 0.85, y, w: 3.85, h: 0.95, margin: 0, fontFace: FONT.body, fontSize: 13.5, color: 'F2EEE6', valign: 'top' });
  });
}

// ---------------------------------------------------------------- deck

function definePres() {
  const pres = new pptxgen();
  pres.defineLayout({ name: 'COVER_3x4', width: SLIDE_W, height: SLIDE_H });
  pres.layout = 'COVER_3x4';
  pres.title = '抖音封面模板 · 名表维修';
  pres.theme = { headFontFace: FONT.title, bodyFontFace: FONT.body };

  for (const [style, { bg }] of Object.entries(STYLES)) {
    const [x, y, w, h] = WINDOWS[style];
    pres.defineSlideMaster({
      title: `COVER_${style.toUpperCase()}`,
      background: { path: asset(`bg-${style}.jpg`), color: bg },
      objects: [
        { placeholder: { options: { name: 'photo', type: 'pic', x: px(x), y: px(y), w: px(w), h: px(h) }, text: '点图标插入手表照片' } },
        ...LAYOUT_TEXT[style].map(([t, o]) => ({
          text: { text: t, options: { ...o, margin: 0, valign: 'middle', x: px(o.x), y: px(o.y), w: px(o.w), h: px(o.h), fontSize: fpx(o.fontSize) } },
        })),
      ],
    });
  }
  pres.defineSlideMaster({
    title: 'GUIDE',
    background: { color: C.page },
    objects: [
      { placeholder: { options: { name: 'title', type: 'title', x: 0.75, y: 0.75, w: 9.75, h: 0.9, fontFace: FONT.title, fontSize: 40, color: 'FFFFFF', align: 'left', valign: 'middle', margin: 0 }, text: '' } },
      { text: { text: '名表维修 · 抖音封面模板', options: { x: 0.75, y: 14.35, w: 6, h: 0.35, fontFace: FONT.body, fontSize: 11, color: C.dim, margin: 0 } } },
    ],
    slideNumber: { x: 9.5, y: 14.35, w: 1, h: 0.35, fontFace: FONT.body, fontSize: 11, color: C.dim, align: 'right' },
  });
  return pres;
}

function addCover(pres, style, d, { guide = true, section = '封面模板', notes = true } = {}) {
  const slide = pres.addSlide({ masterName: `COVER_${style.toUpperCase()}`, sectionTitle: section });
  coverBase(slide, style, d.photo, guide);
  STYLES[style].fn(slide, d);
  if (notes) slide.addNotes(COVER_NOTES(style));
  return slide;
}

// pptxgenjs cannot write these, so they are patched into the XML afterwards.
function patchXml(xml) {
  return xml
    .replaceAll('lang="en-US"', 'lang="zh-CN"')
    // pptxgenjs puts the source file path in the alt text; don't ship it.
    .replace(/ descr="[^"]*\/assets\/[^"]*"/g, '')
    // Cormorant has no Chinese: its runs fall back to Noto Serif SC.
    .replace(/<a:(ea|cs) typeface="Cormorant Garamond[^"]*"/g, `<a:$1 typeface="${FONT.zh}"`)
    // The composition guide ships hidden; it is shown from the selection pane.
    .replace(new RegExp(`(<p:cNvPr id="\\d+" name="${NAME.guide}")`, 'g'), '$1 hidden="1"');
}

async function main() {
  const pres = definePres();
  if (PREVIEW) {
    for (const style of Object.keys(STYLES)) {
      pres.addSection({ title: style });
      for (const d of GRID) addCover(pres, style, d, { guide: false, notes: false, section: style });
    }
  } else {
    pres.addSection({ title: '使用说明' });
    overviewPage(pres);
    gridPage(pres);
    stepsPage(pres);
    shootingPage(pres);
    pres.addSection({ title: '封面模板' });
    for (const style of Object.keys(STYLES)) addCover(pres, style, SAMPLE);
  }

  const zip = await JSZip.loadAsync(await pres.write({ outputType: 'nodebuffer' }));
  for (const f of Object.keys(zip.files).filter((n) => /^ppt\/(slides|slideLayouts)\/[^/]+\.xml$/.test(n))) {
    zip.file(f, patchXml(await zip.file(f).async('string')));
  }
  fs.mkdirSync(path.dirname(OUT_FILE), { recursive: true });
  fs.writeFileSync(OUT_FILE, await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' }));
  console.log('wrote', OUT_FILE);
}

main().catch((e) => { console.error(e); process.exit(1); });
