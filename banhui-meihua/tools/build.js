// Builds the beautified 班会设计 docx. Text comes verbatim from items.json (extracted from the original).
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Header, Footer, Table, TableRow, TableCell,
  AlignmentType, WidthType, ShadingType, BorderStyle, VerticalAlign, HeightRule, TableLayoutType,
  LineRuleType, PageNumber, HorizontalPositionRelativeFrom, VerticalPositionRelativeFrom, TextWrappingType,
} = require('docx');

const [itemsPath, assetDir, outPath] = process.argv.slice(2);
const items = JSON.parse(fs.readFileSync(itemsPath, 'utf8'));
const A = (f) => fs.readFileSync(path.join(assetDir, f));

// ------------------------------------------------------------------ palette & fonts
const NAVY = '0B4B9B', NAVY_D = '12346E', ORANGE = 'D9700F', INK = '2B2B2B', KAI_INK = '4A3B2A';
const ST = ['3D8BE0', 'F2994A', '34B37E', 'EE6A5F'];
const SONG = { ascii: 'Times New Roman', hAnsi: 'Times New Roman', eastAsia: '宋体', cs: 'Times New Roman' };
const HEI = { ascii: '微软雅黑', hAnsi: '微软雅黑', eastAsia: '微软雅黑', cs: '微软雅黑' };
const KAI = { ascii: 'Times New Roman', hAnsi: 'Times New Roman', eastAsia: '楷体', cs: 'Times New Roman' };
const BODY_SIZE = 24;            // 小四
const CONTENT_W = 9298;          // DXA, A4 minus 2.3cm margins
const PX = 620 / 1937;           // asset px -> docx px (asset width 1937 == full content width)
const EXACT = (pt) => ({ line: Math.round(pt * 20), lineRule: LineRuleType.EXACT });

// ------------------------------------------------------------------ text helpers
const T = (i) => {
  const it = items[i];
  if (!it || it.t !== 'p') throw new Error(`item ${i} is not a paragraph`);
  return it.text;
};
const expect = (i, prefix) => {
  if (!T(i).startsWith(prefix)) throw new Error(`item ${i} expected "${prefix}" got "${T(i).slice(0, 20)}"`);
  return T(i);
};
const used = new Set();          // track which items were placed, to verify nothing is lost
const take = (i, prefix = '') => { used.add(i); return prefix ? expect(i, prefix) : T(i); };

const run = (text, o = {}) => new TextRun({
  text, font: o.font || SONG, size: o.size || BODY_SIZE, bold: !!o.bold, color: o.color || INK,
  ...(o.break ? { break: o.break } : {}),
});

function img(file, w, h, alt, extra = {}) {
  return new ImageRun({
    type: file.endsWith('.jpg') ? 'jpg' : 'png', data: A(file),
    transformation: { width: Math.round(w), height: Math.round(h) },
    altText: { title: alt, description: alt, name: alt }, ...extra,
  });
}
// asset image scaled so that 1937 asset px == content width
const assetImg = (file, wpx, hpx, alt, scale = 1) => img(file, wpx * PX * scale, hpx * PX * scale, alt);

// ------------------------------------------------------------------ paragraph builders
const body = (runs, o = {}) => new Paragraph({
  children: runs, alignment: o.align || AlignmentType.JUSTIFIED,
  spacing: { ...EXACT(o.line || 22), before: o.before || 0, after: o.after ?? 60 },
  indent: { firstLine: o.firstLine ?? 480, left: o.left || 0, right: o.right || 0 },
  ...(o.shading ? { shading: o.shading } : {}), ...(o.border ? { border: o.border } : {}),
  keepNext: !!o.keepNext, keepLines: !!o.keepLines,
});
const plain = (i, o) => body([run(take(i))], o);

// "label：rest" -> bold navy label
function labelled(i, label, o = {}) {
  const t = take(i, label);
  return body([run(label, { bold: true, color: NAVY, font: o.labelFont || SONG }), run(t.slice(label.length), o)], o);
}
// "1. 名称：rest" -> orange number + navy bold name
function numbered(i, o = {}) {
  const t = take(i);
  const m = t.match(/^(\d\.\s*)(.*)$/);
  const num = m[1], restAll = m[2];
  const ci = restAll.indexOf('：');
  const runs = [run(num, { bold: true, color: ORANGE, font: HEI })];
  if (ci > -1 && ci < 16) {
    runs.push(run(restAll.slice(0, ci + 1), { bold: true, color: NAVY }));
    runs.push(run(restAll.slice(ci + 1)));
  } else runs.push(run(restAll));
  return body(runs, o);
}

const imgPara = (image, o = {}) => new Paragraph({
  children: [image], alignment: o.align || AlignmentType.CENTER,
  spacing: { before: o.before ?? 120, after: o.after ?? 120, line: 240, lineRule: LineRuleType.AUTO },
  keepNext: !!o.keepNext,
});

const TAGS = {
  '【背景分析】': 'v3_tag_bjfx.png', '【班会目标】': 'v3_tag_bhmb.png', '【班会准备】': 'v3_tag_bhzb.png',
  '【班会过程】': 'v3_tag_bhgc.png', '【班会后延伸教育活动】': 'v3_tag_yshd.png',
  '【板书设计】': 'v3_tag_bssj.png', '【班会反思】': 'v3_tag_bhfs.png',
};
function tag(i) {
  const t = take(i);
  return imgPara(assetImg(TAGS[t], 1937, 124, t), { align: AlignmentType.LEFT, before: 220, after: 100, keepNext: true });
}
const BANNERS = { 18: 'v3_banner_dr.png', 23: 'v3_banner_h1.png', 30: 'v3_banner_h2.png', 43: 'v3_banner_h3.png', 53: 'v3_banner_h4.png' };
function banner(i) {
  const t = take(i);
  return imgPara(assetImg(BANNERS[i], 1937, 290, t, 0.88), { before: 260, after: 120, keepNext: true });
}

function subhead(i) {                       // （一）主题解析
  const t = take(i);
  const m = t.match(/^(（.）)(.*)$/);
  return new Paragraph({
    children: [run(m[1], { font: HEI, bold: true, color: ORANGE, size: 26 }), run(m[2], { font: HEI, bold: true, color: NAVY_D, size: 26 })],
    spacing: { before: 160, after: 80, line: 300, lineRule: LineRuleType.AUTO },
    border: { left: { style: BorderStyle.SINGLE, size: 36, color: 'FFCC39', space: 6 } },
    indent: { left: 120 }, keepNext: true,
  });
}

function activity(i, stage) {               // 活动一：xxx
  const t = take(i, '活动');
  const ci = t.indexOf('：');
  return new Paragraph({
    children: [
      img('ic_mag.png', 22, 22, '活动'),
      run(' ' + t.slice(0, ci + 1), { font: HEI, bold: true, color: ST[stage] === undefined ? ORANGE : ST[stage], size: 26 }),
      run(t.slice(ci + 1), { font: HEI, bold: true, color: NAVY_D, size: 26 }),
    ],
    spacing: { before: 220, after: 100, line: 300, lineRule: LineRuleType.AUTO },
    border: { bottom: { style: BorderStyle.DOTTED, size: 12, color: 'FFCC39', space: 3 } },
    keepNext: true,
  });
}

function subsub(i) {                        // 1. 情境导入
  const t = take(i);
  return new Paragraph({
    children: [img('ic_dot.png', 14, 14, '要点'), run(' ' + t, { font: HEI, bold: true, color: ORANGE, size: 24 })],
    spacing: { before: 140, after: 60, line: 300, lineRule: LineRuleType.AUTO }, indent: { left: 240 }, keepNext: true,
  });
}

function summary(i, label) {                // 小结 / 教师小结
  const t = take(i, label);
  return body([
    run(label, { font: HEI, bold: true, color: NAVY }),
    run(t.slice(label.length), { color: INK }),
  ], { before: 60 });
}

function intent(i) {                        // 【设计意图】 box
  const t = take(i, '【设计意图】');
  const pad = { style: BorderStyle.SINGLE, size: 4, color: 'FFF4D6', space: 5 };
  return new Paragraph({
    children: [run('【设计意图】', { font: KAI, bold: true, color: ORANGE }), run(t.slice(6), { font: KAI, color: KAI_INK })],
    alignment: AlignmentType.JUSTIFIED,
    spacing: { ...EXACT(22), before: 200, after: 160 },
    indent: { left: 200, right: 120 },
    shading: { type: ShadingType.CLEAR, color: 'auto', fill: 'FFF4D6' },
    border: { left: { style: BorderStyle.SINGLE, size: 36, color: 'F5A623', space: 10 }, top: pad, bottom: pad, right: pad },
  });
}

function news(i) {                          // 3. 播放新闻档案案例：...
  const t = take(i);
  const m = t.match(/^(\d\.\s*)(.*?：)(.*)$/);
  return new Paragraph({
    children: [
      img('v3_ic_paper.png', 26, 22, '新闻'),
      run(' ' + m[1], { bold: true, color: ORANGE, font: HEI }),
      run(m[2], { bold: true, color: NAVY }),
      run(m[3]),
    ],
    alignment: AlignmentType.JUSTIFIED,
    spacing: { before: 100, after: 120, line: 340, lineRule: LineRuleType.AUTO },
    indent: { left: 140, right: 140 },
    shading: { type: ShadingType.CLEAR, color: 'auto', fill: 'EDF4FD' },
    border: {
      left: { style: BorderStyle.SINGLE, size: 36, color: NAVY, space: 8 },
      top: { style: BorderStyle.SINGLE, size: 4, color: 'EDF4FD', space: 4 },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: 'EDF4FD', space: 4 },
    },
  });
}

function chant(lines) {                     // 口诀 card; lines joined must equal the source text
  const bd = { style: BorderStyle.SINGLE, size: 8, color: 'F5A623', space: 8 };
  const children = [];
  lines.forEach((l, k) => children.push(run(l, { font: KAI, bold: true, color: NAVY_D, size: 28, ...(k ? { break: 1 } : {}) })));
  return new Paragraph({
    children, alignment: AlignmentType.CENTER,
    spacing: { ...EXACT(30), before: 160, after: 200 },
    indent: { left: 700, right: 700 },
    shading: { type: ShadingType.CLEAR, color: 'auto', fill: 'FFF1C9' },
    border: { top: bd, bottom: bd, left: bd, right: bd },
  });
}

// ------------------------------------------------------------------ tables
const cellB = (color, size = 6) => ({ style: BorderStyle.SINGLE, size, color });
const allB = (b) => ({ top: b, bottom: b, left: b, right: b });
const NOB = allB({ style: BorderStyle.NONE, size: 0, color: 'FFFFFF' });

function cell(paras, w, o = {}) {
  return new TableCell({
    children: paras, width: { size: w, type: WidthType.DXA },
    verticalAlign: o.valign || VerticalAlign.CENTER,
    shading: o.fill ? { type: ShadingType.CLEAR, color: 'auto', fill: o.fill } : undefined,
    margins: o.margins || { top: 90, bottom: 90, left: 120, right: 120 },
    borders: o.borders, columnSpan: o.span,
  });
}
const cp = (text, o = {}) => new Paragraph({
  children: [run(text, { size: o.size || 22, bold: o.bold, color: o.color, font: o.font })],
  alignment: o.align || AlignmentType.CENTER, spacing: { line: 300, lineRule: LineRuleType.AUTO, before: 0, after: 0 },
  keepNext: true,
});

function experimentTable(idx) {
  used.add(idx);
  const rows = items[idx].rows;
  const widths = [2500, 2200, 2200, 2398];
  const bd = allB(cellB('BCD3F0'));
  const out = [new TableRow({
    tableHeader: true, cantSplit: true, height: { value: 620, rule: HeightRule.ATLEAST },
    children: rows[0].map((t, k) => cell([cp(t.trim(), { bold: true, color: 'FFFFFF', font: HEI, size: 21 })], widths[k], { fill: NAVY, borders: bd })),
  })];
  const tints = [['FDE4E1', 'C0392B'], ['E3EEFB', NAVY]];
  rows.slice(1).forEach((r, ri) => out.push(new TableRow({
    cantSplit: true, height: { value: 860, rule: HeightRule.ATLEAST },
    children: r.map((t, k) => k === 0
      ? cell([cp(t.trim(), { bold: true, color: tints[ri][1], font: HEI, size: 21 })], widths[k], { fill: tints[ri][0], borders: bd })
      : cell([cp(t.trim())], widths[k], { fill: 'FFFFFF', borders: bd })),
  })));
  return new Table({ rows: out, width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: widths, layout: TableLayoutType.FIXED, alignment: AlignmentType.CENTER });
}

function situationTable(idx) {
  used.add(idx);
  const rows = items[idx].rows;
  const widths = [3500, 3900, 1898];
  const bd = allB(cellB('F5D6A8'));
  const out = [new TableRow({
    tableHeader: true, cantSplit: true, height: { value: 600, rule: HeightRule.ATLEAST },
    children: rows[0].map((t, k) => cell([cp(t.trim(), { bold: true, color: 'FFFFFF', font: HEI, size: 22 })], widths[k], { fill: 'F08A24', borders: bd })),
  })];
  rows.slice(1).forEach((r, ri) => out.push(new TableRow({
    cantSplit: true, height: { value: 560, rule: HeightRule.ATLEAST },
    children: r.map((t, k) => k === 2
      ? cell([cp(t.trim(), { bold: true, color: ORANGE, font: HEI, size: 22 })], widths[k], { fill: 'FFEFD2', borders: bd })
      : cell([cp(t.trim(), { align: AlignmentType.LEFT })], widths[k], { fill: ri % 2 ? 'FFF9EF' : 'FFFFFF', borders: bd })),
  })));
  return new Table({ rows: out, width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: widths, layout: TableLayoutType.FIXED, alignment: AlignmentType.CENTER });
}

const spacer = (after = 120) => new Paragraph({ children: [], spacing: { before: 0, after, line: 240, lineRule: LineRuleType.AUTO } });

function closingCard(iTitle, iText) {       // 班主任结语
  const title = take(iTitle, '班主任结语');
  const text = take(iText);
  const thin = { style: BorderStyle.SINGLE, size: 6, color: 'EBDDBE', space: 0 };
  const charW = 96, charH = charW * 1203 / 609;
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [2000, 7298], layout: TableLayoutType.FIXED,
    borders: { ...NOB, insideHorizontal: NOB.top, insideVertical: NOB.top },
    rows: [new TableRow({
      cantSplit: true,
      children: [
        cell([new Paragraph({ children: [img('char_stand.png', charW, charH, '小侦探')], alignment: AlignmentType.CENTER })], 2000,
          { borders: NOB, valign: VerticalAlign.BOTTOM, margins: { top: 0, bottom: 0, left: 0, right: 80 } }),
        cell([
          new Paragraph({ children: [run(title, { font: HEI, bold: true, color: NAVY, size: 26 })], spacing: { after: 80, line: 300, lineRule: LineRuleType.AUTO } }),
          body([run(text, { color: INK })], { after: 0 }),
        ], 7298, {
          fill: 'FFFDF5', margins: { top: 220, bottom: 220, left: 320, right: 260 },
          borders: { top: { style: BorderStyle.SINGLE, size: 24, color: 'F5A623', space: 0 }, left: { style: BorderStyle.DOUBLE, size: 6, color: 'EE8E86', space: 0 }, bottom: thin, right: thin },
        }),
      ],
    })],
  });
}

function extensionCards(ids) {
  const fills = ['E3EEFB', 'FFF1D6', 'E1F5EA', 'FDE6E4'];
  const icons = ['ic_school.png', 'ic_medal.png', 'ic_home.png', 'ic_mega.png'];
  const nameColor = [NAVY, ORANGE, '1E8A5A', 'C9463C'];
  const gap = { style: BorderStyle.SINGLE, size: 48, color: 'FFFCF2' };
  const cells = ids.map((i, k) => {
    const t = take(i);
    const m = t.match(/^(\d\.\s*)([^：]+：[^：]+：)(.*)$/);
    return cell([
      new Paragraph({ children: [img(icons[k], 38, 38, '图标')], alignment: AlignmentType.CENTER, spacing: { after: 60, line: 240, lineRule: LineRuleType.AUTO } }),
      new Paragraph({
        children: [run(m[1] + m[2], { font: HEI, bold: true, color: nameColor[k], size: 23 })],
        alignment: AlignmentType.CENTER, spacing: { after: 60, line: 300, lineRule: LineRuleType.AUTO },
      }),
      new Paragraph({ children: [run(m[3], { size: 22 })], alignment: AlignmentType.JUSTIFIED, spacing: EXACT(20) }),
    ], CONTENT_W / 2, { fill: fills[k], borders: allB(gap), valign: VerticalAlign.TOP, margins: { top: 200, bottom: 200, left: 240, right: 240 } });
  });
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W / 2, CONTENT_W / 2], layout: TableLayoutType.FIXED,
    rows: [new TableRow({ children: cells.slice(0, 2), cantSplit: true }), new TableRow({ children: cells.slice(2, 4), cantSplit: true })],
  });
}

function reflection(i) {                    // 第一，xxx。rest
  const t = take(i);
  const k = t.indexOf('。');
  return body([run(t.slice(0, k + 1), { bold: true, color: NAVY }), run(t.slice(k + 1))]);
}

// ------------------------------------------------------------------ document flow
const C = [];
used.add(0); used.add(1);
C.push(imgPara(assetImg('hero.png', 1937, 820, T(0).trim() + ' ' + T(1)), { before: 0, after: 80 }));

// 背景分析
C.push(tag(2));
C.push(subhead(3));
{
  const t = take(4);
  const em = ['“培养学生良好行为习惯和文明素养”', '“队伍一条线”'];
  const parts = t.split(new RegExp(`(${em.join('|')})`));
  C.push(body(parts.filter(Boolean).map((p) => em.includes(p) ? run(p, { bold: true, color: NAVY }) : run(p))));
}
C.push(subhead(5));
C.push(plain(6));

// 班会目标
C.push(tag(7));
for (const i of [8, 9, 10]) C.push(numbered(i, { after: 80 }));
used.add(11);

// 班会准备
C.push(tag(12));
C.push(labelled(13, '教师准备：'));
C.push(labelled(14, '学生准备：'));
C.push(imgPara(assetImg('img_survey.png', 1937, 2150, '队伍侦探社·课前小调查'), { before: 160, after: 80 }));
used.add(15);

// 班会过程
C.push(tag(16));
used.add(17);
C.push(imgPara(assetImg('img_overview.png', 1937, 1110, '班会过程总览：导入 侦探集结令——初识队伍一条线；知 情 意 行 四个环节'), { before: 80, after: 80 }));

// 导入
C.push(banner(18));
C.push(plain(19));
C.push(plain(20));
C.push(summary(21, '教师小结：'));
C.push(intent(22));

// 环节一
C.push(banner(23));
C.push(activity(24, 0));
C.push(plain(25));
C.push(activity(26, 0));
C.push(plain(27));
C.push(summary(28, '小结：'));
C.push(intent(29));

// 环节二
C.push(banner(30));
C.push(activity(31, 1));
C.push(numbered(32, { keepNext: true }));
C.push(experimentTable(33));
C.push(spacer(60));
C.push(summary(34, '教师小结：'));
C.push(numbered(35));
C.push(news(36));
C.push(activity(37, 1));
C.push(numbered(38));
C.push(numbered(39));
C.push(news(40));
C.push(summary(41, '小结：'));
C.push(intent(42));

// 环节三
C.push(banner(43));
C.push(activity(44, 2));
C.push(plain(45));
C.push(chant([take(46)]));
C.push(activity(47, 2));
C.push(plain(48));
{
  const t = take(49);
  const lines = t.split(/(?<=！)/).filter(Boolean);
  if (lines.join('') !== t) throw new Error('chant split mismatch');
  C.push(chant(lines));
}
C.push(labelled(50, '侦探演练场实战：'));
C.push(summary(51, '小结：'));
C.push(intent(52));

// 环节四
C.push(banner(53));
C.push(activity(54, 3));
C.push(subsub(55));
C.push(labelled(56, '教师播放侦探音效：'));
C.push(labelled(57, '揭示任务：'));
C.push(subsub(58));
for (const [i, lb] of [[59, '第一步 抽卡：'], [60, '第二步 讨论：'], [61, '第三步 演绎：']]) {
  used.add(i);
  const t = T(i).trim();
  if (!t.startsWith(lb)) throw new Error('step ' + i);
  C.push(body([run(lb, { bold: true, color: NAVY }), run(t.slice(lb.length))]));
}
C.push(spacer(40));
C.push(situationTable(62));
used.add(63);
C.push(spacer(60));
C.push(labelled(64, '教师点拨：'));
C.push(labelled(65, '引导学生认识：'));
C.push(activity(66, 3));
C.push(plain(67));
C.push(labelled(68, '板书生成：'));
C.push(labelled(69, '侦探进阶思辨：'));
C.push(summary(70, '小结：'));
C.push(intent(71));
used.add(72);

// 班主任结语
C.push(spacer(160));
C.push(closingCard(73, 74));

// 延伸活动
C.push(tag(75));
C.push(extensionCards([76, 77, 78, 79]));

// 板书设计
C.push(tag(80));
used.add(81);
C.push(imgPara(assetImg('img_board.png', 1937, 1100, '板书设计：队伍侦探社 寻回最美一条线', 0.9), { before: 60, after: 60 }));

// 班会反思
C.push(tag(82));
C.push(plain(83));
for (const i of [84, 85, 86, 87]) C.push(reflection(i));

// verify every source item was placed
const missing = items.map((_, i) => i).filter((i) => !used.has(i));
if (missing.length) throw new Error('unplaced items: ' + missing.join(','));

// ------------------------------------------------------------------ page frame & document
const bgRun = new ImageRun({
  type: 'jpg', data: A('v3_page_bg.jpg'), transformation: { width: 794, height: 1123 },
  altText: { title: '页面背景', description: '页面背景', name: '页面背景' },
  floating: {
    horizontalPosition: { relative: HorizontalPositionRelativeFrom.PAGE, offset: 0 },
    verticalPosition: { relative: VerticalPositionRelativeFrom.PAGE, offset: 0 },
    behindDocument: true, allowOverlap: true, lockAnchor: true, layoutInCell: true,
    wrap: { type: TextWrappingType.NONE },
  },
});

const doc = new Document({
  creator: '', title: T(0).trim(), description: T(1),
  styles: {
    default: {
      document: { run: { font: SONG, size: BODY_SIZE, color: INK }, paragraph: { spacing: { line: 360, lineRule: LineRuleType.AUTO } } },
    },
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1500, bottom: 1300, left: 1304, right: 1304, header: 500, footer: 520 },
      },
    },
    headers: { default: new Header({ children: [new Paragraph({ children: [bgRun], spacing: { line: 240, lineRule: LineRuleType.AUTO } })] }) },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: ['— ', PageNumber.CURRENT, ' —'], font: HEI, size: 18, color: NAVY, bold: true })],
        })],
      }),
    },
    children: C,
  }],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(outPath, buf); console.log('wrote', outPath, buf.length); });
