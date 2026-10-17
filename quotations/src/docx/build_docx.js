// Word (.docx) version of the CS881-TG quotation, mirroring the PDF page by page.
// Uses only layout features that Word, WPS and phone viewers all render the same way:
//   - no text frames / absolute text; the cover is one full-page image identical to the PDF
//   - no cell padding (tcMar) and no vertical centring: spacing is paragraph spacing / indents
//   - coloured badges are shaded table cells (run shading is dropped by some viewers)
// Text comes from content.json (source docx + fixes); decoration comes from images rendered off the PDF.
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, Header, Footer,
  AlignmentType, WidthType, BorderStyle, ShadingType, HeightRule, TableLayoutType, UnderlineType,
  PageNumber, HorizontalPositionRelativeFrom, VerticalPositionRelativeFrom, TextWrappingType, SectionType,
} = require('docx');

const [, , DIR, OUT, TUNE_PATH] = process.argv;
const C = JSON.parse(fs.readFileSync(path.join(DIR, 'content.json'), 'utf8'));
const TUNE = TUNE_PATH && fs.existsSync(TUNE_PATH) ? JSON.parse(fs.readFileSync(TUNE_PATH, 'utf8')) : {};
const tune = (k, d) => (k in TUNE ? TUNE[k] : d);
const img = n => fs.readFileSync(path.join(DIR, n));

// ---------------------------------------------------------------- units, palette, type
const tw = mm => Math.round(mm * 56.6929);          // twips
const px = mm => mm * 96 / 25.4;                     // docx-js image px (96 dpi)
const emu = mm => Math.round(mm * 36000);
const K = {
  ink: '10252E', ink2: '43565E', muted: '7D8F96', teal: '2E94A6', tealD: '0F4C5C', tealDD: '0A3440',
  tint: 'EEF6F8', tint2: 'F6FAFB', line: 'DCE7EA', heat: 'E2662B', heatD: 'B84A17', heatT: 'FDF2EB', white: 'FFFFFF',
};
const FONT = { ascii: 'Arial', hAnsi: 'Arial', eastAsia: 'Microsoft YaHei', cs: 'Arial' };
const CW = 176;                                       // content width, mm

const run = (text, o = {}) => new TextRun({
  text, font: FONT, size: Math.round((o.pt || 10.5) * 2), bold: !!o.b, color: o.c || K.ink,
  characterSpacing: o.ls ? Math.round(o.ls * 20) : undefined,
  shading: o.bg ? { type: ShadingType.CLEAR, fill: o.bg, color: 'auto' } : undefined,
  underline: o.u ? { type: UnderlineType.DASH, color: o.u } : undefined,
});
// paragraph spec; turned into a Paragraph by mk(), which applies the cell's padding
const P = (runs, o = {}) => ({ __p: true, runs: Array.isArray(runs) ? runs : [runs], o });
const mk = (spec, pad = {}) => {
  const o = spec.o;
  const left = (o.il || 0) + (pad.l || 0), right = (o.ir || 0) + (pad.r || 0);
  const spacing = { before: tw((o.before || 0) + (pad.t || 0)), after: tw((o.after || 0) + (pad.b || 0)) };
  if (o.auto) Object.assign(spacing, { line: 240, lineRule: 'auto' });
  else Object.assign(spacing, { line: tw(o.lh || 5.6), lineRule: 'exact' });
  return new Paragraph({
    children: spec.runs, alignment: o.al || AlignmentType.LEFT, spacing,
    indent: { left: tw(left), right: tw(right), hanging: o.hang ? tw(o.hang) : undefined },
    border: o.border, keepNext: o.keepNext,
  });
};
const para = (runs, o) => mk(P(runs, o));
const sp = mm => new Paragraph({ children: [], spacing: { before: 0, after: 0, line: Math.max(tw(mm), 14), lineRule: 'exact' } });

const B = (color = K.line, sz = 4, style = BorderStyle.SINGLE) => ({ style, size: sz, color });
const NB = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const NOB = { top: NB, bottom: NB, left: NB, right: NB, insideHorizontal: NB, insideVertical: NB };
const ZERO = { top: 0, bottom: 0, left: 0, right: 0 };
// cell: padding o.pt/pb/pl/pr (mm) becomes paragraph spacing/indent — never tcMar
function cell(content, w, o = {}) {
  const items = (Array.isArray(content) ? content : [content]).filter(Boolean);
  const pad = { l: o.pl || 0, r: o.pr || 0 };
  const out = [];
  items.forEach((it, i) => {
    if (it.__p) out.push(mk(it, { ...pad, t: i === 0 ? o.pt || 0 : 0, b: i === items.length - 1 ? o.pb || 0 : 0 }));
    else out.push(it);
  });
  if (items.length && !items[0].__p && o.pt) out.unshift(sp(o.pt));
  if (!items.length || !items[items.length - 1].__p) out.push(sp(o.pb || .3));
  return new TableCell({
    children: out, width: { size: tw(w), type: WidthType.DXA }, columnSpan: o.span, margins: ZERO,
    shading: o.fill ? { type: ShadingType.CLEAR, fill: o.fill, color: 'auto' } : undefined,
    borders: Object.assign({ top: NB, bottom: NB, left: NB, right: NB }, o.borders || {}),
  });
}
const row = (cells, h, rule = HeightRule.ATLEAST) => new TableRow({ children: cells, height: h ? { value: tw(h), rule } : undefined, cantSplit: true });
const table = (rows, widths) => new Table({
  rows, layout: TableLayoutType.FIXED, borders: NOB, margins: ZERO,
  width: { size: tw(widths.reduce((a, b) => a + b, 0)), type: WidthType.DXA },
  columnWidths: widths.map(tw),
});
const gapRow = (W, h) => row(W.map(w => cell(P([], { lh: .4 }), w)), h, HeightRule.EXACT);
const image = (name, wmm, hmm, type = 'png') => new ImageRun({ type, data: img(name), transformation: { width: px(wmm), height: px(hmm) } });
const sizeOf = name => {
  const b = img(name);
  if (b[0] === 0x89) return [b.readUInt32BE(16), b.readUInt32BE(20)];
  let i = 2; while (i < b.length) { const m = b[i + 1], l = b.readUInt16BE(i + 2); if (m >= 0xC0 && m <= 0xC3) return [b.readUInt16BE(i + 7), b.readUInt16BE(i + 5)]; i += 2 + l; }
};
const fit = (name, wmax, hmax) => { const [w, h] = sizeOf(name); const s = Math.min(wmax / w, hmax / h); return [w * s, h * s]; };
// rough line count for wrapped CJK text (to centre short items next to taller ones)
const lines = (s, widthMm, pt) => { let u = 0; for (const ch of s) u += /[\x00-\xff]/.test(ch) ? .55 : 1; return Math.max(1, Math.ceil(u * pt * .3528 / widthMm - .02)); };

// ---------------------------------------------------------------- shared building blocks
function secHeading(no, title, extra) {
  const n = [...title].length;
  const wt = 4 + n * 5.9 + (extra ? extra.w + 4 : 0);
  const left = [run(title, { pt: 15.5, b: true, c: K.tealDD, ls: 1 })];
  if (extra) left.push(run('   '), run(` ${extra.text} `, { pt: 8.8, c: K.heatD, bg: K.heatT }));
  const W = [9.5, wt, CW - 9.5 - wt];
  return table([row([
    cell(P(run(String(no).padStart(2, '0'), { pt: 10, b: true, c: K.white }), { al: AlignmentType.CENTER, lh: 5.2 }), W[0], { fill: K.teal, pt: 1.9, pb: 1.9 }),
    cell(P(left, { lh: 9 }), W[1], { pl: 3 }),
    cell(P([], { lh: .4, before: 4.3, border: { bottom: B(K.line, 4) } }), W[2]),
  ])], W);
}

function kvTable(rows, o = {}) {
  const pad = o.pad ?? 2.3;
  const W = [37, CW - 37];
  return table(rows.map((r, i) => {
    const first = i === 0 ? { top: B(K.tealD, 12) } : {};
    const body = Array.isArray(r.body) ? r.body : [r.body];
    const th = cell(P(run(r.k, { pt: 10, b: true, c: r.hot ? K.heatD : K.tealD }), { lh: 6.4 }), W[0],
      { fill: r.hot ? K.heatT : K.tint, pt: pad, pb: pad, pl: 3.5, pr: 2, borders: { ...first, bottom: B(K.white, 6) } });
    const td = cell(body, W[1], { fill: K.white, pt: pad, pb: pad, pl: 4, pr: 4, borders: { ...first, bottom: B(K.line, 4) } });
    return row([th, td]);
  }), W);
}
const valueRuns = rs => rs.map(r => run(r.t, r.b ? { pt: 10.5, b: true, c: K.tealD } : { pt: 10.5 }));
const valueP = rs => P(valueRuns(rs), { lh: 6.4 });

function header(label) {
  const bg = new ImageRun({
    type: 'jpg', data: img('bg_inner.jpg'), transformation: { width: px(210), height: px(297) },
    floating: {
      horizontalPosition: { relative: HorizontalPositionRelativeFrom.PAGE, offset: 0 },
      verticalPosition: { relative: VerticalPositionRelativeFrom.PAGE, offset: 0 },
      behindDocument: true, allowOverlap: true, lockAnchor: true, wrap: { type: TextWrappingType.NONE },
    },
  });
  const [lw, lh] = fit('logo.png', 200, 10.5);
  return new Header({ children: [
    para([bg], { lh: .35 }),
    table([row([
      cell(P(image('logo.png', lw, lh), { auto: true }), 110),
      cell([P(run(C.doctitle, { pt: 8, c: K.muted, ls: 1 }), { al: AlignmentType.RIGHT, lh: 4.4, before: .6 }),
        P(run(label, { pt: 10.5, b: true, c: K.tealD }), { al: AlignmentType.RIGHT, lh: 5.6 })], CW - 110),
    ])], [110, CW - 110]),
  ] });
}
function footer() {
  return new Footer({ children: [table([row([
    cell(P([run(C.company, { pt: 8, c: K.ink2 }), run('     ' + C.tel + '     ' + C.fax, { pt: 8, c: K.muted })], { lh: 4.6 }), 130),
    cell(P([run('第 ', { pt: 8, c: K.muted }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 20, bold: true, color: K.tealD }),
      run(' 页   /   共 ', { pt: 8, c: K.muted }), new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 16, color: K.muted }),
      run(' 页', { pt: 8, c: K.muted })], { al: AlignmentType.RIGHT, lh: 4.6 }), CW - 130),
  ])], [130, CW - 130])] });
}
const inner = (label, children) => ({
  properties: {
    type: SectionType.NEXT_PAGE,
    page: { size: { width: tw(210), height: tw(297) }, margin: { top: tw(31), bottom: tw(19), left: tw(17), right: tw(17), header: tw(6.6), footer: tw(6.4) } },
  },
  headers: { default: header(label) }, footers: { default: footer() }, children,
});

// ================================================================ cover: the PDF's cover as one full-page image
function cover() {
  const bg = new ImageRun({
    type: 'jpg', data: img('cover_full-1.jpg'), transformation: { width: px(210), height: px(297) },
    floating: { horizontalPosition: { relative: HorizontalPositionRelativeFrom.PAGE, offset: 0 }, verticalPosition: { relative: VerticalPositionRelativeFrom.PAGE, offset: 0 },
      behindDocument: true, allowOverlap: true, lockAnchor: true, wrap: { type: TextWrappingType.NONE } },
  });
  return {
    properties: { page: { size: { width: tw(210), height: tw(297) }, margin: { top: tw(10), bottom: tw(5), left: tw(17), right: tw(17), header: 0, footer: 0 } } },
    children: [para([bg], { lh: .35 })],
  };
}

// ================================================================ p2 quotation
function pQuote() {
  const out = [];
  out.push(table([row([
    cell([P(run(C.quote_title, { pt: 9.5, b: true, c: K.teal, ls: 2.6 }), { lh: 5.4 }),
      P(run('报价单', { pt: 29, b: true, c: K.tealDD, ls: 5.5 }), { lh: 13 })], 110),
    cell([P(run(C.price_row[0], { pt: 10, c: K.ink2 }), { al: AlignmentType.RIGHT, lh: 5.2, before: 5.8 }),
      P(run(C.price_row[1], { pt: 16, b: true, c: K.tealD }), { al: AlignmentType.RIGHT, lh: 7.4 })], CW - 110),
  ])], [110, CW - 110]));
  out.push(sp(tune('q_gap1', 5)));
  // info grid
  const W = [15, 69, 8, 15, 69];
  const ip = tune('q_info_pad', 2.6);
  const ic = (k, v, first) => {
    const bt = first ? { top: B(K.line, 4) } : {};
    const kc = cell(P(run(k.toUpperCase(), { pt: 8.4, b: true, c: K.muted, ls: 1.2 }), { lh: 6 }), W[0], { pt: ip, pb: ip, borders: { ...bt, bottom: B(K.line, 4) } });
    const vr = v ? run(v, { pt: 10.6, b: true }) : run('_'.repeat(30), { pt: 10.6, c: 'B9C9CE' });
    const vc = cell(P(vr, { lh: 6 }), W[1], { pt: ip, pb: ip, pr: 4, borders: { ...bt, bottom: B(K.line, 4) } });
    return [kc, vc];
  };
  const rows = [];
  for (let i = 0; i < 4; i++) {
    const [a, b] = [C.info[i * 2], C.info[i * 2 + 1]];
    rows.push(row([...ic(a[0], a[1], i === 0), cell(P([]), W[2]), ...ic(b[0], b[1], i === 0)]));
  }
  out.push(table(rows, W));
  out.push(sp(tune('q_gap2', 7.5)));
  // price table
  const PW = [20, 52, 32, 18, 22, 32];
  const RH = 21;                                          // data row height, mm
  const th = (t, w, span, al = AlignmentType.CENTER) => cell(P(run(t, { pt: 9.5, c: K.white, ls: .8 }), { al, lh: 5.4 }), w, { fill: K.tealD, span, pt: 2.3, pb: 2.3, pl: span ? 4 : 1, pr: 1 });
  const one = (t, w, o = {}) => cell(P(run(t, { pt: 11, ...o }), { al: AlignmentType.CENTER, lh: 6 }), w, { pt: (RH - 6) / 2, pb: (RH - 6) / 2, borders: { bottom: B(K.line, 4) } });
  const [tw0, th0] = fit('cut_p2_sm.png', 14, 14);
  out.push(table([
    row([th(C.price_header[0], PW[0] + PW[1], 2, AlignmentType.LEFT), th(C.price_header[1], PW[2]), th(C.price_header[2], PW[3]), th(C.price_header[3], PW[4]), th(C.price_header[4], PW[5])]),
    row([
      cell(P(image('cut_p2_sm.png', tw0, th0), { al: AlignmentType.CENTER, auto: true }), PW[0], { fill: K.tint, pt: (RH - th0 - 1.5) / 2, pb: (RH - th0 - 1.5) / 2, borders: { bottom: B(K.line, 4) } }),
      cell([P(run(C.price_row[0], { pt: 12, b: true, c: K.tealDD }), { lh: 6.6 }), P(run(C.price_sub, { pt: 8.4, c: K.muted }), { lh: 4.6 })], PW[1],
        { pl: 4, pt: (RH - 11.2) / 2, pb: (RH - 11.2) / 2, borders: { bottom: B(K.line, 4) } }),
      one(C.price_row[1], PW[2]), one(C.price_row[2], PW[3]), one(C.price_row[3], PW[4]), one(C.price_row[4], PW[5], { b: true, c: K.tealDD }),
    ]),
  ], PW));
  out.push(sp(.4));
  const TP = tune('q_total_pad', 4);
  out.push(table([row([
    cell(P([run(C.total[0], { pt: 9.4, c: '9ED6E0', ls: 1.8 }), run('    '), run(C.total[1], { pt: 17.5, b: true, c: K.white, ls: 2.4 })], { lh: 9 }), 100, { fill: K.tealDD, pl: 4.5, pt: TP, pb: TP }),
    cell(P([run(C.total[2], { pt: 9, c: 'E4F3F6' }), run('    '), run(C.price_row[4], { pt: 21.5, b: true, c: K.white })], { al: AlignmentType.RIGHT, lh: 9 }), CW - 100, { fill: K.tealDD, pr: 5, pt: TP, pb: TP }),
  ])], [100, CW - 100]));
  out.push(sp(tune('q_gap3', 10)));
  out.push(secHeading(1, C.terms_title));
  out.push(sp(3.6));
  // terms cards (3 rows x 2)
  const TW = [12, 73, 6, 12, 73];
  const cp = tune('q_card_pad', 4.5);
  const card = t => {
    const bd = { top: B(K.line, 4), bottom: B(K.line, 4) };
    return [
      cell(P(image(`ic_${t[2]}.png`, 6.4, 6.4), { al: AlignmentType.CENTER, auto: true }), TW[0], { fill: K.tint2, pt: cp - .5, pl: 1, borders: { ...bd, left: B(K.line, 4) } }),
      cell([P(run(t[0], { pt: 8.8, b: true, c: K.tealD, ls: .5 }), { lh: 5 }), P(run(t[1], { pt: 9.7 }), { lh: 5.6, before: .6 })], TW[1],
        { fill: K.tint2, pt: cp, pb: cp, pr: 4, borders: { ...bd, right: B(K.line, 4) } }),
    ];
  };
  const trows = [];
  for (let i = 0; i < 3; i++) {
    if (i) trows.push(gapRow(TW, tune('q_card_gap', 4.4)));
    trows.push(row([...card(C.terms[i * 2]), cell(P([]), TW[2]), ...card(C.terms[i * 2 + 1])]));
  }
  out.push(table(trows, TW));
  return inner(C.headers[0], out);
}

// ================================================================ p3 specs + overview
function tileRow(tiles) {
  const gap = 2.4;
  const tot = tiles.reduce((a, t) => a + t.w, 0);
  const avail = CW - gap * (tiles.length - 1);
  const W = []; tiles.forEach((t, i) => { if (i) W.push(gap); W.push(avail * t.w / tot); });
  const sty = {
    feature: { fill: 'D9622D', bd: 'D9622D', k: 'FFE3D3', v: K.white, s: 'FFE7DA' },
    hot: { fill: K.heatT, bd: 'F6D8C6', k: 'B97C5E', v: K.heatD, s: K.ink2 },
    dim: { fill: K.tint, bd: 'D3E6EB', k: K.muted, v: K.tealDD, s: K.ink2 },
    el: { fill: K.tint2, bd: K.line, k: K.muted, v: K.tealDD, s: K.ink2 },
  };
  const vpt = { feature: 18.5, hot: 18.5, dim: 21, el: 15.5 };
  const cells = [];
  tiles.forEach((t, i) => {
    if (i) cells.push(cell(P([]), gap));
    const s = sty[t.cls], bd = B(s.bd, 4);
    const val = [];
    if (t.pre) val.push(run(t.pre + ' ', { pt: 9.5, c: s.s }));
    val.push(run(t.big, { pt: vpt[t.cls], b: true, c: s.v }));
    if (t.unit) val.push(run(' ' + t.unit, { pt: 9.5, b: true, c: s.s }));
    cells.push(cell([
      P(run(t.k, { pt: 8.6, c: s.k, ls: .6 }), { lh: 5 }),
      P(val, { lh: 10, before: tune('tile_vgap', 4.2) }),
      P(run(t.small || ' ', { pt: 8.6, c: s.s }), { lh: 4.6 }),
    ], W[cells.length], { fill: s.fill, pt: 3.6, pb: tune('tile_pb', 3.2), pl: 4, pr: 2.5, borders: { top: bd, bottom: bd, left: bd, right: bd } }));
  });
  return table([row(cells)], W);
}
function pSpecs() {
  const out = [secHeading(2, C.spec_title), sp(3.6)];
  C.tiles.forEach((r, i) => { if (i) out.push(sp(2.4)); out.push(tileRow(r)); });
  out.push(sp(tune('spec_gap', 6)));
  out.push(secHeading(3, C.overview_title), sp(2.4));
  out.push(para(run(C.overview_lead, { pt: 9.4, b: true, c: K.tealD, ls: 1 }), { lh: 5, after: 2.2 }));
  const W = [13, 73.8, 2.4, 13, 73.8];
  const pad = tune('ov_pad', 3.6), LH = 6.6, textW = W[1] - 5;
  const rows = [];
  for (let i = 0; i < 4; i++) {
    const pair = [C.overview[i * 2], C.overview[i * 2 + 1]];
    const nl = Math.max(...pair.map(t => lines(t, textW, 10.8)));
    const card = (n, t) => {
      const bd = { top: B(K.line, 4), bottom: B(K.line, 4) };
      const own = lines(t, textW, 10.8);
      const extra = (nl - own) * LH / 2;              // centre shorter text against its neighbour
      return [
        cell(P(run(String(n).padStart(2, '0'), { pt: 15.5, b: true, c: K.teal }), { lh: 8, al: AlignmentType.CENTER }), W[0],
          { fill: K.white, pt: pad + (nl * LH - 8) / 2, borders: { ...bd, left: B(K.teal, 24) } }),
        cell(P(run(t, { pt: 10.8 }), { lh: LH }), W[1], { fill: K.white, pt: pad + extra, pb: pad + extra, pl: 1, pr: 4, borders: { ...bd, right: B(K.line, 4) } }),
      ];
    };
    if (i) rows.push(gapRow(W, 2.6));
    rows.push(row([...card(i * 2 + 1, pair[0]), cell(P([]), W[2]), ...card(i * 2 + 2, pair[1])]));
  }
  out.push(table(rows, W));
  return inner(C.headers[1], out);
}

// ================================================================ p4 materials
function pMaterials() {
  const rows = C.materials.map(m => {
    if (m.door) {
      const body = [P(run(m.door_head, { pt: 10.5, b: true }), { lh: 6.4 })];
      m.door.forEach(([n, t]) => body.push(P([run(n, { pt: 10.5, b: true, c: K.teal }), run(t, { pt: 10.5 })], { lh: 6.2, il: 10, hang: 10 })));
      return { k: m.k, body };
    }
    if (m.chip) return { k: m.k, hot: true, body: P(run(' ' + m.chip + ' ', { pt: 11.5, b: true, c: K.heatD, bg: K.heatT }), { lh: 6.4 }) };
    return { k: m.k, body: valueP(m.v) };
  });
  return inner(C.headers[2], [secHeading(4, C.materials_title), sp(3.6), kvTable(rows, { pad: tune('mat_pad', 2.6) })]);
}

// ================================================================ p5 air / circulation / heating
function pSystems() {
  const pad = tune('sys_pad', 3.2);
  const mk2 = list => list.map(([k, v]) => ({ k, body: valueP(v) }));
  const note = table([row([
    cell(P(image('ic_info.png', 6, 6), { auto: true }), 12, { fill: K.tint, pt: 3.6, pl: 4.5 }),
    cell(P([run(C.test_note[0], { pt: 10.3, b: true, c: K.tealDD }), run(C.test_note[1], { pt: 10.3, c: K.tealDD })], { lh: 6.2 }), CW - 12, { fill: K.tint, pt: 4, pb: 4, pr: 4.5 }),
  ])], [12, CW - 12]);
  return inner(C.headers[3], [
    secHeading(5, C.air_title), sp(3.6), kvTable(mk2(C.air), { pad: pad * 1.6 }), sp(tune('sys_gap', 7)),
    secHeading(6, C.circ_title), sp(3.6), kvTable(mk2(C.circ), { pad }), sp(tune('sys_gap', 7)),
    secHeading(7, C.heat_title), sp(3.6), kvTable(mk2(C.heat), { pad: pad * 1.3 }), sp(tune('sys_gap', 7)),
    note,
  ]);
}

// ================================================================ p6 electrical + product photos
function cutoutRow(names, h, fill = 'EEF4F6') {
  const gap = 2.4, w = (CW - 2 * gap) / 3;
  const W = [w, gap, w, gap, w];
  const cells = [];
  names.forEach((n, i) => {
    if (i) cells.push(cell(P([]), gap));
    const [iw, ih] = fit(n, w - 8, h - 12);
    // bottom-align the product on its card with spacing above (no vertical-align needed)
    cells.push(cell(P(image(n, iw, ih), { al: AlignmentType.CENTER, auto: true }), w, { fill, pt: h - ih - 7, pb: 5 }));
  });
  return table([row(cells)], W);
}
const galNote = () => para(run(C.gal_note, { pt: 8.4, c: K.muted, ls: 1 }), { al: AlignmentType.RIGHT, lh: 5, before: 1.8 });
function pElectrical() {
  const rows = C.el.map(([k, v]) => ({ k, body: valueP(v) }));
  const noteW = [...C.el_note].length * 3.15 + 6;
  return inner(C.headers[4], [
    secHeading(8, C.el_title, { text: C.el_note, w: noteW }), sp(3.6), kvTable(rows, { pad: tune('el_pad', 2.3) }), sp(tune('el_gap', 6)),
    secHeading(9, C.prod_title), sp(3.6), cutoutRow(['card_p1.png', 'card_p2.png', 'card_p3.png'], tune('strip_h', 66)), galNote(),
  ]);
}

// ================================================================ p7 company equipment
function pCompany() {
  const H1 = tune('co_h1', 124), H2 = tune('co_h2', 98);
  const gap = 2.4, w = (CW - gap) / 2;
  const photos = table([row([
    cell(P(image('ph_c3.jpg', w, H1 - 2.5, 'jpg'), { auto: true }), w),
    cell(P([]), gap),
    cell(P(image('ph_c4.jpg', w, H1 - 2.5, 'jpg'), { auto: true }), w),
  ])], [w, gap, w]);
  return inner(C.headers[5], [
    secHeading(10, C.co_title), sp(3.6), photos, sp(gap),
    cutoutRow(['card_c1.png', 'card_c2.png', 'card_c5.png'], H2), galNote(),
  ]);
}

// ================================================================ p8 advice + closing (the only seal)
function pAdvice() {
  const [a, b] = C.warn.split(C.ban);
  const warnRuns = [run(a, { pt: 10.3, c: '5A2A12' }), run(C.ban, { pt: 10.3, b: true, c: 'C62D1F' }), run(b, { pt: 10.3, c: '5A2A12' })];
  const warn = table([row([
    cell(P(image('ic_alert.png', 6.4, 6.4), { auto: true }), 13, { fill: K.heatT, pt: 3.6, pl: 4.5, borders: { left: B(K.heat, 36) } }),
    cell(P(warnRuns, { lh: 6.4 }), CW - 13, { fill: K.heatT, pt: 4, pb: 4, pr: 4.5 }),
  ])], [13, CW - 13]);
  const h3 = t => P([run('▍', { pt: 12, c: K.teal }), run(t, { pt: 12.5, b: true, c: K.tealDD, ls: .6 })], { lh: 7, after: 2.2 });
  const colW = 84.5, gapW = CW - 2 * colW;
  // install box
  const [pw, ph] = fit('plan.png', colW - 9, 70);
  const ip = tune('inst_pad', 6);
  const installBox = table([row([cell([
    P(image('plan.png', pw, ph), { al: AlignmentType.CENTER, auto: true, after: tune('inst_gap', 6) }),
    ...C.install.map((t, i) => P([run('—  ', { pt: 10, b: true, c: K.teal }), run(t, { pt: 10.3 })], { lh: 6, il: 5, hang: 5, after: i === 0 ? 1 : 0 })),
  ], colW, { fill: K.tint2, pt: ip, pb: ip, pl: 4, pr: 4,
    borders: { top: B(K.line, 4), bottom: B(K.line, 4), left: B(K.line, 4), right: B(K.line, 4) } })])], [colW]);
  // environment cards
  const EW = [13, colW - 13];
  const EH = tune('env_h', 13.5);
  const envRows = [];
  C.env.forEach(([t, ic], i) => {
    const last = i === C.env.length - 1;
    const bd = B(last ? 'F6CDB4' : K.line, 4);
    const nl = lines(t, EW[1] - 4, 10.3);
    const tp = (EH - nl * 5.8) / 2;
    if (i) envRows.push(gapRow(EW, 2.6));
    envRows.push(row([
      cell(P(image(`ic_${ic}.png`, 6, 6), { al: AlignmentType.CENTER, auto: true }), EW[0], { fill: last ? K.heatT : K.white, pt: (EH - 7.5) / 2, borders: { top: bd, bottom: bd, left: bd } }),
      cell(P(run(t, last ? { pt: 10.3, b: true, c: K.heatD } : { pt: 10.3 }), { lh: 5.8 }), EW[1], { fill: last ? K.heatT : K.white, pt: tp, pb: tp, pr: 3, borders: { top: bd, bottom: bd, right: bd } }),
    ]));
  });
  const two = table([row([
    cell([h3(C.install_title), installBox], colW),
    cell(P([]), gapW),
    cell([h3(C.env_title), table(envRows, EW)], colW),
  ])], [colW, gapW, colW]);
  // closing card with the seal over the company name
  const seal = new ImageRun({
    type: 'png', data: img('seal.png'), transformation: { width: px(38), height: px(38 * 433 / 404) },
    floating: {
      horizontalPosition: { relative: HorizontalPositionRelativeFrom.COLUMN, offset: emu(tune('seal_x', 36)) },
      verticalPosition: { relative: VerticalPositionRelativeFrom.PARAGRAPH, offset: emu(tune('seal_y', -20)) },
      behindDocument: false, allowOverlap: true, wrap: { type: TextWrappingType.NONE },
    },
  });
  const H = tune('close_h', 56), CWl = 96;
  const closing = table([row([
    cell([P(run(C.thanks[0], { pt: 16, b: true, c: K.tealDD, ls: 1.2 }), { lh: 10 }), P(run(C.thanks[1], { pt: 16, b: true, c: K.tealDD, ls: 1.2 }), { lh: 10 })],
      CWl, { fill: K.white, pl: 10, pt: (H - 20) / 2, pb: (H - 20) / 2, borders: { top: B(K.line, 4), bottom: B(K.line, 4), left: B(K.teal, 36) } }),
    cell([P(run(C.closing_company, { pt: 13, b: true, c: K.tealDD, ls: 1 }), { lh: 7.5 }), P([run(C.date, { pt: 9.4, c: K.muted }), seal], { lh: 5.5, before: 1 })],
      CW - CWl, { fill: K.white, pl: 2, pt: (H - 14) / 2, pb: (H - 14) / 2, borders: { top: B(K.line, 4), bottom: B(K.line, 4), right: B(K.line, 4) } }),
  ])], [CWl, CW - CWl]);
  return inner(C.headers[6], [secHeading(11, C.adv_title), sp(3.6), warn, sp(tune('adv_gap1', 6)), two, sp(tune('adv_gap2', 6)), closing]);
}

// ================================================================ assemble
const doc = new Document({
  creator: C.company, title: `${C.price_row[0]} ${C.price_row[1]} 报价单`, description: C.doctitle,
  styles: { default: { document: { run: { font: FONT, size: 21, color: K.ink }, paragraph: { spacing: { before: 0, after: 0, line: 20, lineRule: 'exact' } } } } },
  sections: [cover(), pQuote(), pSpecs(), pMaterials(), pSystems(), pElectrical(), pCompany(), pAdvice()],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log('wrote', OUT, buf.length); });
