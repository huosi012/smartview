// Builds 抖音封面模板.pptx: guide pages plus three ready-to-edit cover
// templates. With --preview it instead writes build/preview.pptx, a deck of
// sample covers that render.sh turns into the images the guide pages show.
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
const pngAspect = (file) => { // height / width, read from the PNG header
  const b = fs.readFileSync(file);
  return b.readUInt32BE(20) / b.readUInt32BE(16);
};

const FONT = {
  serif: 'Noto Serif SC Black',
  sans: 'Noto Sans SC Black',
  smiley: 'Smiley Sans Oblique',
  cinzel: 'Cinzel',
  body: 'Microsoft YaHei',
};
const C = {
  gold: 'D6B36E',
  goldText: 'F1DDAE', // hero colour of style A; post-processed into a gold gradient
  ribbon: 'E9C77B',
  yellow: 'FFD60A',
  ink: '0B0A09',
  cream: 'F6F1E7',
  page: '121214',
  card: '1C1C20',
  grey: 'A7A39B',
  dim: '6E6A64',
};

const NAME = {
  photo: '手表照片（右键→更改图片）',
  mask: '遮罩（勿删）',
  guide: '构图参考线（导出前隐藏）',
};

const shadow = (blur = 10, offset = 4, opacity = 0.65) => ({
  type: 'outer', color: '000000', blur, offset, angle: 90, opacity,
});

// ---------------------------------------------------------------- covers

function coverBase(pres, slide, photo, withGuide) {
  slide.addImage({
    placeholder: 'photo', path: asset(`photo-${photo}.jpg`),
    x: 0, y: 0, w: SLIDE_W, h: SLIDE_H, objectName: NAME.photo, altText: '手表照片',
  });
  const pieces = { top: [0, 0, 1080, 340], left: [0, 340, 300, 420], right: [780, 340, 300, 420], bottom: [0, 760, 1080, 680] };
  for (const [side, [x, y, w, h]] of Object.entries(pieces)) {
    slide.addImage({
      path: asset(`mask-${side}.png`), x: px(x), y: px(y), w: px(w), h: px(h), objectName: NAME.mask,
    });
  }
  if (withGuide) {
    slide.addImage({ path: asset('guide.png'), x: 0, y: 0, w: SLIDE_W, h: SLIDE_H, objectName: NAME.guide });
  }
}

function text(slide, value, o) {
  slide.addText(value, {
    isTextBox: true, margin: 0, valign: 'middle', ...o,
    x: px(o.x), y: px(o.y), w: px(o.w), h: px(o.h),
    fontSize: fpx(o.fontSize),
  });
}

// A: black and gold, serif. Centred block, the quietest of the three.
function coverA(pres, slide, d) {
  text(slide, d.shop, { x: 290, y: 52, w: 500, h: 60, fontFace: FONT.serif, fontSize: 34, color: C.cream, align: 'center', charSpacing: 2, objectName: '店名', shadow: shadow(6, 2) });
  text(slide, `NO.${d.episode}`, { x: 796, y: 50, w: 220, h: 64, fontFace: FONT.cinzel, bold: true, fontSize: 44, color: C.gold, align: 'right', objectName: '期数', shadow: shadow(6, 2) });
  text(slide, `${d.brand} · ${d.brandCn}`, { x: 60, y: 876, w: 960, h: 72, fontFace: FONT.cinzel, bold: true, fontSize: 44, color: C.gold, align: 'center', charSpacing: 6, objectName: '品牌', fit: 'shrink', shadow: shadow(8, 3) });
  text(slide, d.title, { x: 30, y: 948, w: 1020, h: 220, fontFace: FONT.serif, fontSize: d.titleSizeA || 164, color: C.goldText, align: 'center', objectName: '主标题（型号）', fit: 'shrink', shadow: shadow(14, 5, 0.75) });
  slide.addText(d.service, {
    shape: pres.shapes.RECTANGLE, x: px(170), y: px(1182), w: px(740), h: px(84),
    fill: { color: '000000', transparency: 55 }, line: { color: C.gold, width: 1.5 },
    fontFace: FONT.serif, fontSize: fpx(46), color: C.cream, align: 'center', valign: 'middle',
    charSpacing: 3, margin: 0, fit: 'shrink', objectName: '服务项目',
  });
}

// B: the shop's current yellow-on-black look, tidied. Left-aligned, loud.
function coverB(pres, slide, d) {
  slide.addText(`第${d.episode}期`, {
    shape: pres.shapes.RECTANGLE, x: px(812), y: px(50), w: px(212), h: px(74),
    fill: { color: C.yellow }, fontFace: FONT.sans, fontSize: fpx(40), color: C.ink,
    align: 'right', valign: 'middle', margin: [0, 8, 0, 8], wrap: false, fit: 'resize', objectName: '期数',
  });
  text(slide, d.shop, { x: 290, y: 57, w: 500, h: 60, fontFace: FONT.sans, fontSize: 34, color: 'FFFFFF', align: 'center', objectName: '店名', shadow: shadow(6, 2) });
  text(slide, `${d.brand} ${d.brandCn}`, { x: 64, y: 870, w: 950, h: 80, fontFace: FONT.sans, fontSize: 56, color: 'FFFFFF', objectName: '品牌', fit: 'shrink', shadow: shadow(8, 3) });
  text(slide, d.title, { x: 56, y: 944, w: 980, h: 226, fontFace: FONT.sans, fontSize: d.titleSizeB || 168, color: C.yellow, objectName: '主标题（型号）', fit: 'shrink', outline: { size: 3, color: '000000' }, shadow: shadow(0, 8, 0.9) });
  slide.addText(d.service.replace(/ · /g, ' + '), {
    shape: pres.shapes.RECTANGLE, x: px(64), y: px(1184), w: px(640), h: px(84),
    fill: { color: C.yellow }, fontFace: FONT.sans, fontSize: fpx(50), color: C.ink,
    align: 'center', valign: 'middle', margin: [0, 10, 0, 10], wrap: false, fit: 'resize', objectName: '服务项目',
  });
}

// C: the diagonal ribbon from the reference screenshots, in Smiley Sans.
function coverC(pres, slide, d) {
  text(slide, d.shop, { x: 290, y: 52, w: 500, h: 64, fontFace: FONT.smiley, fontSize: 42, color: 'FFFFFF', align: 'center', objectName: '店名', shadow: shadow(6, 2) });
  text(slide, `NO.${d.episode}`, { x: 796, y: 44, w: 224, h: 80, fontFace: FONT.smiley, fontSize: 68, color: C.ribbon, align: 'right', objectName: '期数', shadow: shadow(6, 2) });
  slide.addText(d.service, {
    shape: pres.shapes.RECTANGLE, x: px(-210), y: px(760), w: px(1500), h: px(104), rotate: -9,
    fill: { color: C.ribbon }, fontFace: FONT.smiley, fontSize: fpx(62), color: '1A1408',
    align: 'center', valign: 'middle', margin: 0, charSpacing: 4, objectName: '斜带（服务项目）',
    shadow: shadow(18, 6, 0.55),
  });
  text(slide, d.title, { x: 56, y: 958, w: 980, h: 214, fontFace: FONT.smiley, fontSize: d.titleSizeC || 184, color: 'FFFFFF', objectName: '主标题（型号）', fit: 'shrink', shadow: shadow(14, 5, 0.8) });
  text(slide, `${d.brand} ${d.brandCn}`, { x: 64, y: 1172, w: 950, h: 80, fontFace: FONT.smiley, fontSize: 58, color: C.ribbon, objectName: '品牌', fit: 'shrink', shadow: shadow(8, 3) });
}

const STYLES = {
  A: { fn: coverA, name: '黑金典藏' },
  B: { fn: coverB, name: '工坊硬核' },
  C: { fn: coverC, name: '斜带寄修' },
};

const SAMPLE = {
  photo: 'omega-seamaster', shop: 'XX名表维修', episode: '023',
  brand: 'OMEGA', brandCn: '欧米茄', title: '海马150 GMT', service: '洗油大保养 · 外观修复',
};

// Newest first, as Douyin lays out a profile.
const GRID = [
  SAMPLE,
  { photo: 'rolex-dj-black', episode: '022', brand: 'ROLEX', brandCn: '劳力士', title: '日志', service: '十年没保养 · 拆开看看' },
  { photo: 'gp-1945', episode: '021', brand: 'GP', brandCn: '芝柏', title: '1945方表', service: '洗油大保养 · 修复' },
  { photo: 'breguet-a', episode: '020', brand: 'BREGUET', brandCn: '宝玑', title: '宝玑经典', service: '表壳补金 · 修复' },
  { photo: 'montblanc', episode: '019', brand: 'MONTBLANC', brandCn: '万宝龙', title: '明星计时', service: '磕碰修复 · 洗油' },
  { photo: 'iwc-portugieser', episode: '018', brand: 'IWC', brandCn: '万国', title: '葡萄牙', service: '寄修 · 洗油大保养' },
  { photo: 'chopard-luc', episode: '017', brand: 'CHOPARD', brandCn: '萧邦', title: 'L.U.C', service: '寄修 · 洗油大保养' },
  { photo: 'breguet-b', episode: '016', brand: 'BREGUET', brandCn: '宝玑', title: '补金修复', service: '原色补金 · 抛光' },
  { photo: 'rolex-dj-white', episode: '015', brand: 'ROLEX', brandCn: '劳力士', title: '钻刻日志', service: '寄修 · 洗油大保养' },
].map((d) => ({ ...SAMPLE, ...d }));

const COVER_NOTES = (style) => [
  `模板 ${style}「${STYLES[style].name}」使用方法：`,
  '1. 左侧缩略图右键这一页 →「复制幻灯片」，在副本上改，原模板留着下次用。',
  '2. 点表盘位置选中照片 → 右键「更改图片」→ 选新照片。位置不准就用「裁剪」拖动对齐。',
  '   点不中照片时：开始 → 选择 → 选择窗格，点「手表照片」。',
  '   对位时可在选择窗格里显示「构图参考线」，导出前一定要再隐藏。',
  '3. 直接点文字修改：店名、期数、品牌、型号、服务项目。字多了会自动缩小。',
  '4. 导出：文件 → 导出 → 更改文件类型 → PNG → 仅当前幻灯片（1080×1440）。',
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
    shape: pres.shapes.OVAL, x, y, w: d, h: d, fill: { color: C.gold },
    fontFace: FONT.sans, fontSize: 22, color: C.ink, align: 'center', valign: 'middle', margin: 0,
  });
}

function overviewPage(pres) {
  const s = pres.addSlide({ masterName: 'GUIDE', sectionTitle: '使用说明' });
  pageTitle(s, '三种封面风格，选一种用到底', '整个主页统一一种风格、统一拍摄角度，九宫格才整齐。每次只需换照片、改文字，导出就是 1080×1440 的抖音封面。');
  const cards = [
    ['A', '黑金典藏', '推荐', '高级感最强，适合劳力士、百达翡丽这类高端表'],
    ['B', '工坊硬核', '', '延续你们现在的黄字风格，最醒目'],
    ['C', '斜带寄修', '', '参考图里的斜带元素，动感、有辨识度'],
  ];
  cards.forEach(([k, name, tag, desc], i) => {
    const x = 0.75 + i * 3.325;
    s.addImage({ path: asset(`preview-${k}.png`), x, y: 2.75, w: 3.1, h: 4.133, objectName: `风格${k}预览`, altText: `封面风格 ${k}「${name}」示例` });
    s.addText([
      { text: `${k}  ${name}`, options: { fontFace: FONT.sans, fontSize: 22, color: 'FFFFFF' } },
      ...(tag ? [{ text: `  ${tag}`, options: { fontFace: FONT.sans, fontSize: 16, color: C.gold } }] : []),
    ], { isTextBox: true, x, y: 7.03, w: 3.1, h: 0.5, margin: 0, valign: 'middle' });
    s.addText(desc, { isTextBox: true, x, y: 7.55, w: 3.1, h: 0.85, margin: 0, fontFace: FONT.body, fontSize: 14, color: C.grey, valign: 'top' });
  });

  s.addText('字体都可免费商用', { isTextBox: true, x: 0.75, y: 8.85, w: 9.75, h: 0.55, margin: 0, fontFace: FONT.sans, fontSize: 24, color: 'FFFFFF' });
  const fonts = [
    ['思源宋体 Black', FONT.serif, '海马150 GMT', '模板 A 标题', 'Noto Serif SC · Google / Adobe'],
    ['思源黑体 Black', FONT.sans, '海马150 GMT', '模板 B 标题', 'Noto Sans SC · Google / Adobe'],
    ['得意黑', FONT.smiley, '海马150 GMT', '模板 C 标题', 'Smiley Sans · 锚坞'],
    ['Cinzel', FONT.cinzel, 'OMEGA · ROLEX', '模板 A 英文品牌', 'Cinzel · NDISCOVER'],
  ];
  fonts.forEach(([name, face, specimen, use, src], i) => {
    const y = 9.6 + i * 1.02;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.75, y, w: 9.75, h: 0.88, fill: { color: C.card }, line: { type: 'none' }, rectRadius: 0.08 });
    s.addText(specimen, { isTextBox: true, x: 1.0, y, w: 4.1, h: 0.88, margin: 0, fontFace: face, bold: face === FONT.cinzel, fontSize: 30, color: C.goldText, valign: 'middle' });
    s.addText([
      { text: name, options: { fontFace: FONT.sans, fontSize: 17, color: 'FFFFFF', breakLine: true } },
      { text: `${use} · ${src}`, options: { fontFace: FONT.body, fontSize: 12, color: C.grey } },
    ], { isTextBox: true, x: 5.2, y, w: 3.6, h: 0.88, margin: 0, valign: 'middle' });
    s.addText('SIL OFL 1.1', { isTextBox: true, x: 8.75, y, w: 1.55, h: 0.88, margin: 0, fontFace: FONT.body, fontSize: 12, color: C.gold, align: 'right', valign: 'middle' });
  });
  s.addText('字体在 fonts 文件夹，第一次用前先安装。也可换成抖音官方的「抖音美好体」（免费商用）。', {
    isTextBox: true, x: 0.75, y: 13.75, w: 9.75, h: 0.6, margin: 0, fontFace: FONT.body, fontSize: 13, color: C.dim, valign: 'top',
  });
}

function gridPage(pres) {
  const s = pres.addSlide({ masterName: 'GUIDE', sectionTitle: '使用说明' });
  pageTitle(s, '主页效果：统一后的九宫格', '下图用模板 A 套了 9 块表（照片取自你们发来的截图，仅作示意）。');
  s.addImage({ path: asset('grid-mockup.png'), x: 0.75, y: 2.75, w: 6.8, h: 6.8 * pngAspect(asset('grid-mockup.png')), objectName: '主页效果图', altText: '套用模板 A 后的抖音主页九宫格示意' });
  const tips = [
    ['大标题要够大', '型号或昵称用 2–6 个字，缩略图里也能一眼看清。'],
    ['避开点赞数', '主页左下角会被点赞数挡住，模板的文字都在它上面。'],
    ['角度统一', '每块表同一角度、同一位置拍，主页才整齐。'],
    ['加期数编号', 'NO.023 这类编号让主页像一个系列，粉丝愿意往下翻。'],
  ];
  tips.forEach(([t, d], i) => {
    const y = 2.85 + i * 2.65;
    numberDot(pres, s, i + 1, 7.85, y);
    s.addText(t, { isTextBox: true, x: 7.85, y: y + 0.78, w: 2.65, h: 0.5, margin: 0, fontFace: FONT.sans, fontSize: 20, color: 'FFFFFF', valign: 'top' });
    s.addText(d, { isTextBox: true, x: 7.85, y: y + 1.3, w: 2.65, h: 1.2, margin: 0, fontFace: FONT.body, fontSize: 14, color: C.grey, valign: 'top' });
  });
}

function stepsPage(pres) {
  const s = pres.addSlide({ masterName: 'GUIDE', sectionTitle: '使用说明' });
  pageTitle(s, '出一张封面的流程', '第 1 步只做一次，以后每次从第 2 步开始，几分钟一张。');
  const steps = [
    ['安装字体（只做一次）', '打开 fonts 文件夹，双击 4 个字体文件 → 点「安装」（Mac 用「字体册」）。装好后重开 PPT / WPS，否则字体会被替换成默认字体。'],
    ['复制一页模板', '左侧缩略图右键选好的模板页 →「复制幻灯片」，在副本上改，原模板留着下次用。'],
    ['换手表照片', '点表盘位置选中照片 → 右键「更改图片」→ 选新照片。位置不准用「图片格式 → 裁剪」拖动对齐。点不中照片时：开始 → 选择 → 选择窗格，点「手表照片」。'],
    ['对位置（可选）', '在选择窗格里点亮「构图参考线」，把表盘对进圆圈；对好后一定再把它隐藏，否则会被导出。'],
    ['改文字', '点文字直接改店名、期数、品牌、型号、服务项目；型号 2–8 个字最好。'],
    ['导出图片', 'PowerPoint：文件 → 导出 → 更改文件类型 → PNG → 仅当前幻灯片，得到 1080×1440。\nWPS：文件 → 输出为图片 → 当前页（或 另存为 → PNG）。'],
    ['发抖音时设为封面', '发布页点「选封面」→ 从相册上传这张图，主页九宫格显示的就是它。'],
  ];
  steps.forEach(([t, d], i) => {
    const y = 2.75 + i * 1.6;
    numberDot(pres, s, i + 1, 0.75, y + 0.02);
    s.addText(t, { isTextBox: true, x: 1.65, y, w: 8.85, h: 0.55, margin: 0, fontFace: FONT.sans, fontSize: 22, color: 'FFFFFF', valign: 'middle' });
    s.addText(d, { isTextBox: true, x: 1.65, y: y + 0.6, w: 8.85, h: 0.9, margin: 0, fontFace: FONT.body, fontSize: 15, color: C.grey, valign: 'top', lineSpacingMultiple: 1.1 });
  });
}

function shootingPage(pres) {
  const s = pres.addSlide({ masterName: 'GUIDE', sectionTitle: '使用说明' });
  pageTitle(s, '拍摄规范：以后都按这个角度拍', '在你们现在的拍法（黑背景、表立起来、侧转露出表冠）基础上定成标准，每块表都一样。');
  s.addImage({ path: asset('guide-sample.png'), x: 0.75, y: 2.75, w: 4.6, h: 4.6 * 4 / 3, objectName: '构图示意', altText: '标准构图：表盘在青色圆圈内，虚线以下为文字区' });
  s.addText('青色圆圈 = 表盘位置；虚线以下 = 文字区；红色 = 会被抖音界面挡住', { isTextBox: true, x: 0.75, y: 8.95, w: 4.6, h: 0.6, margin: 0, fontFace: FONT.body, fontSize: 12, color: C.grey, valign: 'top' });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.65, y: 2.75, w: 4.85, h: 3.0, fill: { color: C.card }, line: { type: 'none' }, rectRadius: 0.1 });
  s.addImage({ path: asset('diagram-top.png'), x: 5.75, y: 2.8, w: 3.9 * 1000 / 760, h: 2.9, objectName: '俯视图', altText: '俯视图：表盘向左转约 25 度，手机正对表头' });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.65, y: 5.95, w: 4.85, h: 3.0, fill: { color: C.card }, line: { type: 'none' }, rectRadius: 0.1 });
  s.addImage({ path: asset('diagram-side.png'), x: 5.75, y: 6.0, w: 3.9 * 1000 / 760, h: 2.9, objectName: '侧视图', altText: '侧视图：镜头略高于表盘中心 5 到 10 度，距离 20 到 30 厘米' });

  const rules = [
    ['背景', '黑色植绒布（吸光布），表离背景 30 cm 以上，背景才够黑。'],
    ['摆放', '表立在表枕或支架上，表盘正面朝镜头。'],
    ['角度', '表盘向左转约 25°，露出右侧表冠和表壳侧面。'],
    ['高度', '镜头与表盘中心同高或略高 5–10°，不要从正上方俯拍。'],
    ['构图', '手机竖拍 3:4，表盘在画面上半部、约占宽度一半，下半部留给文字。'],
    ['镜头', '用 2× 长焦，距离 20–30 cm，表盘不变形。'],
    ['光线', '一盏柔光灯从左上 45° 打光，右侧放白卡或灯条给表壳边缘补高光，关掉顶灯防反光。'],
    ['细节', '表镜擦干净、指针调到 10:10、点表盘对焦，曝光略降让背景纯黑。'],
  ];
  rules.forEach(([k, d], i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.75 + col * 5.0;
    const y = 9.7 + row * 1.1;
    s.addText(k, { isTextBox: true, x, y, w: 0.9, h: 0.95, margin: 0, fontFace: FONT.sans, fontSize: 18, color: C.gold, valign: 'top' });
    s.addText(d, { isTextBox: true, x: x + 0.85, y, w: 3.85, h: 0.95, margin: 0, fontFace: FONT.body, fontSize: 13.5, color: C.cream, valign: 'top' });
  });
}

// ---------------------------------------------------------------- deck

function definePres() {
  const pres = new pptxgen();
  pres.defineLayout({ name: 'COVER_3x4', width: SLIDE_W, height: SLIDE_H });
  pres.layout = 'COVER_3x4';
  pres.title = '抖音封面模板 · 名表维修';
  pres.theme = { headFontFace: FONT.sans, bodyFontFace: FONT.body };

  pres.defineSlideMaster({
    title: 'COVER',
    background: { color: '000000' },
    objects: [{ placeholder: { options: { name: 'photo', type: 'pic', x: 0, y: 0, w: SLIDE_W, h: SLIDE_H }, text: '点图标插入手表照片' } }],
  });
  pres.defineSlideMaster({
    title: 'GUIDE',
    background: { color: C.page },
    objects: [
      { placeholder: { options: { name: 'title', type: 'title', x: 0.75, y: 0.75, w: 9.75, h: 0.9, fontFace: FONT.sans, fontSize: 40, color: 'FFFFFF', align: 'left', valign: 'middle', margin: 0 }, text: '' } },
      { text: { text: '名表维修 · 抖音封面模板', options: { x: 0.75, y: 14.35, w: 6, h: 0.35, fontFace: FONT.body, fontSize: 11, color: C.dim, margin: 0 } } },
    ],
    slideNumber: { x: 9.5, y: 14.35, w: 1, h: 0.35, fontFace: FONT.body, fontSize: 11, color: C.dim, align: 'right' },
  });
  return pres;
}

function addCover(pres, style, d, { guide = true, section = '封面模板', notes = true } = {}) {
  const slide = pres.addSlide({ masterName: 'COVER', sectionTitle: section });
  coverBase(pres, slide, d.photo, guide);
  STYLES[style].fn(pres, slide, d);
  if (notes) slide.addNotes(COVER_NOTES(style));
  return slide;
}

// pptxgenjs cannot write these, so they are patched into the XML afterwards.
const GOLD_GRADIENT = '<a:gradFill flip="none" rotWithShape="1"><a:gsLst>'
  + '<a:gs pos="0"><a:srgbClr val="FFF3D6"/></a:gs>'
  + '<a:gs pos="50000"><a:srgbClr val="E6C47E"/></a:gs>'
  + '<a:gs pos="100000"><a:srgbClr val="B38842"/></a:gs>'
  + '</a:gsLst><a:lin ang="5400000" scaled="1"/></a:gradFill>';

function patchSlide(xml) {
  return xml
    .replaceAll('lang="en-US"', 'lang="zh-CN"')
    // pptxgenjs puts the source file path in the alt text; don't ship it.
    .replace(/ descr="[^"]*\/assets\/[^"]*"/g, '')
    // Cinzel has no Chinese: give its runs a Chinese fallback of the same mood.
    .replace(/<a:ea typeface="Cinzel"([^>]*)\/>/g, `<a:ea typeface="${FONT.serif}"$1/>`)
    // Gold text (style A's title, the font specimens): a gradient instead of
    // the flat stand-in colour. Only text runs use C.goldText.
    .replaceAll(`<a:solidFill><a:srgbClr val="${C.goldText}"/></a:solidFill>`, GOLD_GRADIENT)
    // The composition guide ships hidden; it is shown from the selection pane.
    .replace(new RegExp(`(<p:cNvPr id="\\d+" name="${NAME.guide}")`, 'g'), '$1 hidden="1"');
}

async function main() {
  const pres = definePres();
  if (PREVIEW) {
    pres.addSection({ title: '风格' });
    for (const k of Object.keys(STYLES)) addCover(pres, k, SAMPLE, { guide: false, notes: false, section: '风格' });
    pres.addSection({ title: '九宫格' });
    for (const d of GRID) addCover(pres, 'A', d, { guide: false, notes: false, section: '九宫格' });
  } else {
    pres.addSection({ title: '使用说明' });
    overviewPage(pres);
    gridPage(pres);
    stepsPage(pres);
    shootingPage(pres);
    pres.addSection({ title: '封面模板' });
    for (const k of Object.keys(STYLES)) addCover(pres, k, SAMPLE);
  }

  const zip = await JSZip.loadAsync(await pres.write({ outputType: 'nodebuffer' }));
  for (const f of Object.keys(zip.files).filter((n) => /^ppt\/slides\/slide\d+\.xml$/.test(n))) {
    zip.file(f, patchSlide(await zip.file(f).async('string')));
  }
  fs.mkdirSync(path.dirname(OUT_FILE), { recursive: true });
  fs.writeFileSync(OUT_FILE, await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' }));
  console.log('wrote', OUT_FILE);
}

main().catch((e) => { console.error(e); process.exit(1); });
