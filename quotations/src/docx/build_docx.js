// Word (.docx) version of the CS881-TG quotation, mirroring the PDF page by page.
// Text comes from content.json (source docx + fixes); decoration comes from images rendered off the PDF's HTML.
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, Header, Footer,
  AlignmentType, VerticalAlign, WidthType, BorderStyle, ShadingType, HeightRule, TableLayoutType,
  PageNumber, FrameAnchorType, HorizontalPositionRelativeFrom, VerticalPositionRelativeFrom,
  TextWrappingType, SectionType,
} = require('docx');

const [, , DIR, OUT, TUNE_PATH] = process.argv;
const C = JSON.parse(fs.readFileSync(path.join(DIR, 'content.json'), 'utf8'));
const LAY = JSON.parse(fs.readFileSync(path.join(DIR, 'cover_layout.json'), 'utf8'));
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
});
const para = (children, o = {}) => new Paragraph({
  children: Array.isArray(children) ? children : [children],
  alignment: o.al || AlignmentType.LEFT,
  spacing: o.auto ? { before: tw(o.before || 0), after: tw(o.after || 0), line: 240, lineRule: 'auto' }
    : { before: tw(o.before || 0), after: tw(o.after || 0), line: tw(o.lh || 5.6), lineRule: 'exact' },
  indent: o.indent, border: o.border, keepNext: o.keepNext, frame: o.frame,
});
const sp = mm => new Paragraph({ children: [], spacing: { before: 0, after: 0, line: Math.max(tw(mm), 14), lineRule: 'exact' } });

const B = (color = K.line, sz = 4, style = BorderStyle.SINGLE) => ({ style, size: sz, color });
const NB = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const NOB = { top: NB, bottom: NB, left: NB, right: NB, insideHorizontal: NB, insideVertical: NB };
const cell = (children, w, o = {}) => new TableCell({
  children: Array.isArray(children) ? children : [children],
  width: { size: tw(w), type: WidthType.DXA },
  columnSpan: o.span, verticalAlign: o.va || VerticalAlign.TOP,
  shading: o.fill ? { type: ShadingType.CLEAR, fill: o.fill, color: 'auto' } : undefined,
  borders: Object.assign({ top: NB, bottom: NB, left: NB, right: NB }, o.borders || {}),
  margins: { top: tw(o.mt ?? 0), bottom: tw(o.mb ?? 0), left: tw(o.ml ?? 0), right: tw(o.mr ?? 0) },
});
const row = (cells, h, rule = HeightRule.ATLEAST) => new TableRow({ children: cells, height: h ? { value: tw(h), rule } : undefined, cantSplit: true });
const table = (rows, widths) => new Table({
  rows, layout: TableLayoutType.FIXED, borders: NOB,
  width: { size: tw(widths.reduce((a, b) => a + b, 0)), type: WidthType.DXA },
  columnWidths: widths.map(tw),
});
const image = (name, wmm, hmm, type = 'png') => new ImageRun({ type, data: img(name), transformation: { width: px(wmm), height: px(hmm) } });
const sizeOf = name => { // PNG/JPEG intrinsic size
  const b = img(name);
  if (b[0] === 0x89) return [b.readUInt32BE(16), b.readUInt32BE(20)];
  let i = 2; while (i < b.length) { const m = b[i + 1], l = b.readUInt16BE(i + 2); if (m >= 0xC0 && m <= 0xC3) return [b.readUInt16BE(i + 7), b.readUInt16BE(i + 5)]; i += 2 + l; }
};
const fit = (name, wmax, hmax) => { const [w, h] = sizeOf(name); const s = Math.min(wmax / w, hmax / h); return [w * s, h * s]; };

// ---------------------------------------------------------------- shared building blocks
function secHeading(no, title, extra) {
  const n = [...title].length;
  const wl = 13 + n * 5.9 + (extra ? extra.w : 0);
  const left = [run(` ${String(no).padStart(2, '0')} `, { pt: 10, b: true, c: K.white, bg: K.teal, ls: .4 }),
    run('  ' + title, { pt: 15.5, b: true, c: K.tealDD, ls: 1 })];
  if (extra) left.push(run('   '), run(` ${extra.text} `, { pt: 8.8, c: K.heatD, bg: K.heatT }));
  return table([row([
    cell(para(left, { lh: 9 }), wl, { va: VerticalAlign.CENTER }),
    cell(para([], { lh: .35, border: { bottom: B(K.line, 4) } }), CW - wl, { va: VerticalAlign.CENTER }),
  ], 9, HeightRule.EXACT)], [wl, CW - wl]);
}

function kvTable(rows, o = {}) {
  const pad = o.pad ?? 2.3;
  const W = [37, CW - 37];
  return table(rows.map((r, i) => {
    const first = i === 0 ? { top: B(K.tealD, 12) } : {};
    const th = cell(para(run(r.k, { pt: 10, b: true, c: r.hot ? K.heatD : K.tealD }), { lh: 5.6 }), W[0],
      { fill: r.hot ? K.heatT : K.tint, va: VerticalAlign.CENTER, mt: pad, mb: pad, ml: 3.5, mr: 2,
        borders: { ...first, bottom: B(K.white, 6) } });
    const td = cell(r.body, W[1], { fill: K.white, va: VerticalAlign.CENTER, mt: pad, mb: pad, ml: 4, mr: 4,
      borders: { ...first, bottom: B(K.line, 4) } });
    return row([th, td]);
  }), W);
}
const valueRuns = rs => rs.map(r => run(r.t, r.b ? { pt: 10.5, b: true, c: K.tealD } : { pt: 10.5 }));
const valuePara = rs => para(valueRuns(rs), { lh: 6.4 });

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
      cell(para(image('logo.png', lw, lh), { lh: 11 }), 110, { va: VerticalAlign.CENTER }),
      cell([para(run(C.doctitle, { pt: 8, c: K.muted, ls: 1 }), { al: AlignmentType.RIGHT, lh: 4.4 }),
        para(run(label, { pt: 10.5, b: true, c: K.tealD }), { al: AlignmentType.RIGHT, lh: 5.6 })], CW - 110, { va: VerticalAlign.CENTER }),
    ], 11, HeightRule.EXACT)], [110, CW - 110]),
  ] });
}
function footer() {
  return new Footer({ children: [table([row([
    cell(para([run(C.company, { pt: 8, c: K.ink2 }), run('     ' + C.tel + '     ' + C.fax, { pt: 8, c: K.muted })], { lh: 4.6 }), 130, { va: VerticalAlign.CENTER }),
    cell(para([run('第 ', { pt: 8, c: K.muted }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 20, bold: true, color: K.tealD }),
      run(' 页   /   共 ' , { pt: 8, c: K.muted }), new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 16, color: K.muted }),
      run(' 页', { pt: 8, c: K.muted })], { al: AlignmentType.RIGHT, lh: 4.6 }), CW - 130, { va: VerticalAlign.CENTER }),
  ], 5, HeightRule.EXACT)], [130, CW - 130])] });
}
const inner = (label, children) => ({
  properties: {
    type: SectionType.NEXT_PAGE,
    page: { size: { width: tw(210), height: tw(297) }, margin: { top: tw(31), bottom: tw(19), left: tw(17), right: tw(17), header: tw(6.6), footer: tw(5.2) } },
  },
  headers: { default: header(label) }, footers: { default: footer() }, children,
});

// ================================================================ cover
function cover() {
  const hex = s => { const m = s.match(/\d+/g).map(Number); return m.slice(0, 3).map(v => v.toString(16).padStart(2, '0')).join('').toUpperCase(); };
  const bg = new ImageRun({
    type: 'jpg', data: img('bg_cover.jpg'), transformation: { width: px(210), height: px(297) },
    floating: { horizontalPosition: { relative: HorizontalPositionRelativeFrom.PAGE, offset: 0 }, verticalPosition: { relative: VerticalPositionRelativeFrom.PAGE, offset: 0 },
      behindDocument: true, allowOverlap: true, lockAnchor: true, wrap: { type: TextWrappingType.NONE } },
  });
  const L = LAY.logo;
  const logo = new ImageRun({
    type: 'png', data: img('logo.png'), transformation: { width: px(L.w), height: px(L.h) },
    floating: { horizontalPosition: { relative: HorizontalPositionRelativeFrom.PAGE, offset: emu(L.x) }, verticalPosition: { relative: VerticalPositionRelativeFrom.PAGE, offset: emu(L.y) },
      behindDocument: false, allowOverlap: true, lockAnchor: true, wrap: { type: TextWrappingType.NONE } },
  });
  const dy = tune('cover_dy', 0);
  const frames = LAY.items.map(it0 => {
    let it = it0;
    const right = it.x > 120;                         // ref/date and contact are right-aligned
    if (it.key === 'sub') { it = { ...it, x: it.x + 13 }; }
    const W = it.w + 30;
    const x = right ? it.x + it.w - W : it.x;
    const pt = Math.round(it.size * 2) / 2;
    const runs = it.runs.map(r => run(r.t, { pt: Math.round(r.size * 2) / 2, b: +r.weight >= 600, c: hex(r.color), ls: (r.ls || 0) * 0.75 }));
    return para(runs, {
      al: right ? AlignmentType.RIGHT : AlignmentType.LEFT, lh: Math.max(it.h, pt * 0.3528 * 1.18),
      frame: { type: 'absolute', position: { x: tw(x), y: tw(it.y + dy) }, width: tw(W), height: tw(it.h),
        anchor: { horizontal: FrameAnchorType.PAGE, vertical: FrameAnchorType.PAGE } },
    });
  });
  return {
    properties: { page: { size: { width: tw(210), height: tw(297) }, margin: { top: tw(10), bottom: tw(5), left: tw(17), right: tw(17), header: 0, footer: 0 } } },
    children: [para([bg, logo], { lh: .35 }), ...frames],
  };
}

// ================================================================ p2 quotation
function pQuote() {
  const out = [];
  out.push(table([row([
    cell([para(run(C.quote_title, { pt: 9.5, b: true, c: K.teal, ls: 2.6 }), { lh: 5.4 }),
      para(run('报价单', { pt: 29, b: true, c: K.tealDD, ls: 5.5 }), { lh: 13 })], 110, { va: VerticalAlign.BOTTOM }),
    cell([para(run(C.price_row[0], { pt: 10, c: K.ink2 }), { al: AlignmentType.RIGHT, lh: 5.2 }),
      para(run(C.price_row[1], { pt: 16, b: true, c: K.tealD }), { al: AlignmentType.RIGHT, lh: 7.4 })], CW - 110, { va: VerticalAlign.BOTTOM }),
  ])], [110, CW - 110]));
  out.push(sp(tune('q_gap1', 5)));
  // info grid
  const W = [15, 69, 8, 15, 69];
  const ic = (k, v, first) => {
    const bt = first ? { top: B(K.line, 4) } : {};
    const kc = cell(para(run(k.toUpperCase(), { pt: 8.4, b: true, c: K.muted, ls: 1.2 }), { lh: 5 }), W[0], { va: VerticalAlign.CENTER, mt: 2.6, mb: 2.6, borders: { ...bt, bottom: B(K.line, 4) } });
    const vp = v ? para(run(v, { pt: 10.6, b: true }), { lh: 5.6 })
      : para([], { lh: 4.2, border: { bottom: { style: BorderStyle.DASHED, size: 4, color: 'B9C9CE' } } });
    const vc = cell(vp, W[1], { va: VerticalAlign.CENTER, mt: 2.6, mb: 2.6, mr: 4, borders: { ...bt, bottom: B(K.line, 4) } });
    return [kc, vc];
  };
  const rows = [];
  for (let i = 0; i < 4; i++) {
    const [a, b] = [C.info[i * 2], C.info[i * 2 + 1]];
    rows.push(row([...ic(a[0], a[1], i === 0), cell(para([]), W[2]), ...ic(b[0], b[1], i === 0)]));
  }
  out.push(table(rows, W));
  out.push(sp(tune('q_gap2', 7.5)));
  // price table
  const PW = [20, 52, 32, 18, 22, 32];
  const th = (t, w, span, al = AlignmentType.CENTER) => cell(para(run(t, { pt: 9.5, c: K.white, ls: .8 }), { al, lh: 5.2 }), w, { fill: K.tealD, span, va: VerticalAlign.CENTER, mt: 2.4, mb: 2.4, ml: span ? 4 : 1, mr: 1 });
  const td = (children, w, o = {}) => cell(children, w, { va: VerticalAlign.CENTER, mt: tune('q_rowpad', 4.2), mb: tune('q_rowpad', 4.2), ml: 1, mr: 1, borders: { bottom: B(K.line, 4) }, ...o });
  const [tw0, th0] = fit('cut_p2_sm.png', 14, 14);
  out.push(table([
    row([th(C.price_header[0], PW[0] + PW[1], 2, AlignmentType.LEFT), th(C.price_header[1], PW[2]), th(C.price_header[2], PW[3]), th(C.price_header[3], PW[4]), th(C.price_header[4], PW[5])]),
    row([
      td(para(image('cut_p2_sm.png', tw0, th0), { al: AlignmentType.CENTER, lh: 15 }), PW[0], { fill: K.tint, ml: 1, mr: 1, mt: 2, mb: 2 }),
      td([para(run(C.price_row[0], { pt: 12, b: true, c: K.tealDD }), { lh: 6.6 }), para(run(C.price_sub, { pt: 8.4, c: K.muted }), { lh: 4.6 })], PW[1], { ml: 4 }),
      td(para(run(C.price_row[1], { pt: 11 }), { al: AlignmentType.CENTER }), PW[2]),
      td(para(run(C.price_row[2], { pt: 11 }), { al: AlignmentType.CENTER }), PW[3]),
      td(para(run(C.price_row[3], { pt: 11 }), { al: AlignmentType.CENTER }), PW[4]),
      td(para(run(C.price_row[4], { pt: 11, b: true, c: K.tealDD }), { al: AlignmentType.CENTER }), PW[5]),
    ]),
  ], PW));
  out.push(sp(.4));
  out.push(table([row([
    cell(para([run(C.total[0], { pt: 9.4, c: '9ED6E0', ls: 1.8 }), run('    '), run(C.total[1], { pt: 17.5, b: true, c: K.white, ls: 2.4 })], { lh: 9 }), 100, { fill: K.tealDD, va: VerticalAlign.CENTER, ml: 4.5 }),
    cell(para([run(C.total[2], { pt: 9, c: 'E4F3F6' }), run('    '), run(C.price_row[4], { pt: 21.5, b: true, c: K.white })], { al: AlignmentType.RIGHT, lh: 9 }), CW - 100, { fill: K.tealDD, va: VerticalAlign.CENTER, mr: 5 }),
  ], tune('q_total_h', 17), HeightRule.EXACT)], [100, CW - 100]));
  out.push(sp(tune('q_gap3', 10)));
  out.push(secHeading(1, C.terms_title));
  out.push(sp(3.6));
  // terms cards (3 rows x 2)
  const TW = [12, 73, 6, 12, 73];
  const card = t => {
    const bd = { top: B(K.line, 4), bottom: B(K.line, 4) };
    return [
      cell(para(image(`ic_${t[2]}.png`, 6.4, 6.4), { al: AlignmentType.CENTER, lh: 7 }), TW[0], { fill: K.tint2, mt: 3.6, ml: 1.5, borders: { ...bd, left: B(K.line, 4) } }),
      cell([para(run(t[0], { pt: 8.8, b: true, c: K.tealD, ls: .5 }), { lh: 5 }), para(run(t[1], { pt: 9.7 }), { lh: 5.6, before: .6 })], TW[1],
        { fill: K.tint2, mt: tune('q_card_pad', 4), mb: tune('q_card_pad', 4), mr: 4, borders: { ...bd, right: B(K.line, 4) } }),
    ];
  };
  const trows = [];
  for (let i = 0; i < 3; i++) {
    if (i) trows.push(row([cell(para([], { lh: .5 }), TW[0]), cell(para([], { lh: .5 }), TW[1]), cell(para([], { lh: .5 }), TW[2]), cell(para([], { lh: .5 }), TW[3]), cell(para([], { lh: .5 }), TW[4])], tune('q_card_gap', 4.4), HeightRule.EXACT));
    trows.push(row([...card(C.terms[i * 2]), cell(para([]), TW[2]), ...card(C.terms[i * 2 + 1])], tune('q_card_h', 25)));
  }
  out.push(table(trows, TW));
  return inner(C.headers[0], out);
}

// ================================================================ p3 specs + overview
function tileRow(tiles, h) {
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
    if (i) cells.push(cell(para([]), gap));
    const s = sty[t.cls];
    const bd = B(s.bd, 4);
    const val = [];
    if (t.pre) val.push(run(t.pre + ' ', { pt: 9.5, c: s.s }));
    val.push(run(t.big, { pt: vpt[t.cls], b: true, c: s.v }));
    if (t.unit) val.push(run(' ' + t.unit, { pt: 9.5, b: true, c: s.s }));
    cells.push(cell([
      para(run(t.k, { pt: 8.6, c: s.k, ls: .6 }), { lh: 5 }),
      para(val, { lh: 10, before: tune('tile_vgap', 4.2) }),
      para(run(t.small || ' ', { pt: 8.6, c: s.s }), { lh: 4.6 }),
    ], W[cells.length], { fill: s.fill, borders: { top: bd, bottom: bd, left: bd, right: bd }, mt: 3.6, ml: 4, mr: 2.5 }));
  });
  return table([row(cells, h, HeightRule.EXACT)], W);
}
function pSpecs() {
  const out = [secHeading(2, C.spec_title), sp(3.6)];
  C.tiles.forEach((r, i) => { if (i) out.push(sp(2.4)); out.push(tileRow(r, tune('tile_h', 30))); });
  out.push(sp(tune('spec_gap', 6)));
  out.push(secHeading(3, C.overview_title), sp(2.4));
  out.push(para(run(C.overview_lead, { pt: 9.4, b: true, c: K.tealD, ls: 1 }), { lh: 5, after: 2.2 }));
  const W = [13, 73.8, 2.4, 13, 73.8];
  const pad = tune('ov_pad', 3.6);
  const card = (n, t) => {
    const bd = { top: B(K.line, 4), bottom: B(K.line, 4) };
    return [
      cell(para(run(String(n).padStart(2, '0'), { pt: 15.5, b: true, c: K.teal }), { lh: 8, al: AlignmentType.CENTER }), W[0], { va: VerticalAlign.CENTER, fill: K.white, borders: { ...bd, left: B(K.teal, 24) } }),
      cell(para(run(t, { pt: 10.8 }), { lh: 6.6 }), W[1], { va: VerticalAlign.CENTER, fill: K.white, mt: pad, mb: pad, ml: 1, mr: 4, borders: { ...bd, right: B(K.line, 4) } }),
    ];
  };
  const rows = [];
  for (let i = 0; i < 4; i++) {
    if (i) rows.push(row(W.map(w => cell(para([], { lh: .5 }), w)), 2.6, HeightRule.EXACT));
    rows.push(row([...card(i * 2 + 1, C.overview[i * 2]), cell(para([]), W[2]), ...card(i * 2 + 2, C.overview[i * 2 + 1])], tune('ov_h', 0) || undefined));
  }
  out.push(table(rows, W));
  return inner(C.headers[1], out);
}

// ================================================================ p4 materials
function pMaterials() {
  const rows = C.materials.map(m => {
    if (m.door) {
      const body = [para(run(m.door_head, { pt: 10.5, b: true }), { lh: 6.4 })];
      m.door.forEach(([n, t]) => body.push(para([run(n, { pt: 10.5, b: true, c: K.teal }), run(t, { pt: 10.5 })], { lh: 6.2, indent: { left: tw(10), hanging: tw(10) } })));
      return { k: m.k, body };
    }
    if (m.chip) return { k: m.k, hot: true, body: para(run(' ' + m.chip + ' ', { pt: 11.5, b: true, c: K.heatD, bg: K.heatT }), { lh: 6.4 }) };
    return { k: m.k, body: valuePara(m.v) };
  });
  return inner(C.headers[2], [secHeading(4, C.materials_title), sp(3.6), kvTable(rows, { pad: tune('mat_pad', 2.6) })]);
}

// ================================================================ p5 air / circulation / heating
function pSystems() {
  const pad = tune('sys_pad', 3.2);
  const mk = list => list.map(([k, v]) => ({ k, body: valuePara(v) }));
  const note = table([row([
    cell(para(image('ic_info.png', 6, 6), { lh: 6.4 }), 12, { fill: K.tint, mt: 4, ml: 4.5 }),
    cell(para([run(C.test_note[0], { pt: 10.3, b: true, c: K.tealDD }), run(C.test_note[1], { pt: 10.3, c: K.tealDD })], { lh: 6.2 }), CW - 12, { fill: K.tint, mt: 4, mb: 4, mr: 4.5 }),
  ])], [12, CW - 12]);
  return inner(C.headers[3], [
    secHeading(5, C.air_title), sp(3.6), kvTable(mk(C.air), { pad: pad * 1.6 }), sp(tune('sys_gap', 7)),
    secHeading(6, C.circ_title), sp(3.6), kvTable(mk(C.circ), { pad }), sp(tune('sys_gap', 7)),
    secHeading(7, C.heat_title), sp(3.6), kvTable(mk(C.heat), { pad: pad * 1.3 }), sp(tune('sys_gap', 7)),
    note,
  ]);
}

// ================================================================ p6 electrical + product photos
function cutoutRow(names, h, fill = 'EEF4F6') {
  const gap = 2.4, w = (CW - 2 * gap) / 3;
  const W = [w, gap, w, gap, w];
  const cells = [];
  names.forEach((n, i) => {
    if (i) cells.push(cell(para([]), gap));
    const [iw, ih] = fit(n, w - 8, h - 12);
    cells.push(cell(para(image(n, iw, ih), { al: AlignmentType.CENTER, auto: true }), w, { fill, va: VerticalAlign.BOTTOM, mb: 5 }));
  });
  return table([row(cells, h, HeightRule.EXACT)], W);
}
const galNote = () => para(run(C.gal_note, { pt: 8.4, c: K.muted, ls: 1 }), { al: AlignmentType.RIGHT, lh: 5, before: 1.8 });
function pElectrical() {
  const rows = C.el.map(([k, v]) => ({ k, body: valuePara(v) }));
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
    cell(para(image('ph_c3.jpg', w, H1 - 2.5, 'jpg'), { auto: true }), w),
    cell(para([]), gap),
    cell(para(image('ph_c4.jpg', w, H1 - 2.5, 'jpg'), { auto: true }), w),
  ], H1, HeightRule.EXACT)], [w, gap, w]);
  return inner(C.headers[5], [
    secHeading(10, C.co_title), sp(3.6), photos, sp(gap),
    cutoutRow(['card_c1.png', 'card_c2.png', 'card_c5.png'], H2), galNote(),
  ]);
}

// ================================================================ p8 advice + closing (the only seal)
function pAdvice() {
  const warnRuns = [];
  const [a, b] = C.warn.split(C.ban);
  warnRuns.push(run(a, { pt: 10.3, c: '5A2A12' }), run(C.ban, { pt: 10.3, b: true, c: 'C62D1F' }), run(b, { pt: 10.3, c: '5A2A12' }));
  const warn = table([row([
    cell(para(image('ic_alert.png', 6.4, 6.4), { lh: 6.6 }), 13, { fill: K.heatT, mt: 4, ml: 4.5, borders: { left: B(K.heat, 36) } }),
    cell(para(warnRuns, { lh: 6.4 }), CW - 13, { fill: K.heatT, mt: 4, mb: 4, mr: 4.5 }),
  ])], [13, CW - 13]);
  const h3 = t => para([run('▍', { pt: 12, c: K.teal }), run(t, { pt: 12.5, b: true, c: K.tealDD, ls: .6 })], { lh: 7, after: 2.2 });
  const colW = 84.5, gapW = CW - 2 * colW;
  // install box
  const [pw, ph] = fit('plan.png', colW - 9, 70);
  const installBox = table([row([cell([
    para(image('plan.png', pw, ph), { al: AlignmentType.CENTER, auto: true, after: tune('inst_gap', 6) }),
    ...C.install.map(t => para([run('—  ', { pt: 10, b: true, c: K.teal }), run(t, { pt: 10.3 })], { lh: 6, indent: { left: tw(5), hanging: tw(5) }, after: 1 })),
  ], colW, { fill: K.tint2, mt: tune('inst_pad', 6), mb: tune('inst_pad', 6), ml: 4, mr: 4,
    borders: { top: B(K.line, 4), bottom: B(K.line, 4), left: B(K.line, 4), right: B(K.line, 4) } })])], [colW]);
  // environment cards
  const EW = [13, colW - 13];
  const envRows = [];
  C.env.forEach(([t, ic], i) => {
    const last = i === C.env.length - 1;
    const bd = B(last ? 'F6CDB4' : K.line, 4);
    if (i) envRows.push(row(EW.map(w => cell(para([], { lh: .5 }), w)), 2.6, HeightRule.EXACT));
    envRows.push(row([
      cell(para(image(`ic_${ic}.png`, 6, 6), { al: AlignmentType.CENTER, lh: 6.4 }), EW[0], { fill: last ? K.heatT : K.white, va: VerticalAlign.CENTER, borders: { top: bd, bottom: bd, left: bd } }),
      cell(para(run(t, last ? { pt: 10.3, b: true, c: K.heatD } : { pt: 10.3 }), { lh: 5.8 }), EW[1], { fill: last ? K.heatT : K.white, va: VerticalAlign.CENTER, mr: 3, borders: { top: bd, bottom: bd, right: bd } }),
    ], tune('env_h', 13.5)));
  });
  const two = table([row([
    cell([h3(C.install_title), installBox], colW),
    cell(para([]), gapW),
    cell([h3(C.env_title), table(envRows, EW)], colW),
  ])], [colW, gapW, colW]);
  // closing card with the seal over the company name
  const seal = new ImageRun({
    type: 'png', data: img('seal.png'), transformation: { width: px(38), height: px(38 * 433 / 404) },
    floating: {
      horizontalPosition: { relative: HorizontalPositionRelativeFrom.COLUMN, offset: emu(tune('seal_x', 44)) },
      verticalPosition: { relative: VerticalPositionRelativeFrom.PARAGRAPH, offset: emu(tune('seal_y', -16)) },
      behindDocument: false, allowOverlap: true, wrap: { type: TextWrappingType.NONE },
    },
  });
  const CWl = 96;
  const closing = table([row([
    cell([para(run(C.thanks[0], { pt: 16, b: true, c: K.tealDD, ls: 1.2 }), { lh: 10 }), para(run(C.thanks[1], { pt: 16, b: true, c: K.tealDD, ls: 1.2 }), { lh: 10 })],
      CWl, { fill: K.white, ml: 10, mt: (tune('close_h', 52) - 20) / 2, borders: { top: B(K.line, 4), bottom: B(K.line, 4), left: B(K.teal, 36) } }),
    cell([para(run(C.closing_company, { pt: 13, b: true, c: K.tealDD, ls: 1 }), { lh: 7.5 }), para([run(C.date, { pt: 9.4, c: K.muted }), seal], { lh: 5.5, before: 1 })],
      CW - CWl, { fill: K.white, ml: 2, mt: (tune('close_h', 52) - 14) / 2, borders: { top: B(K.line, 4), bottom: B(K.line, 4), right: B(K.line, 4) } }),
  ], tune('close_h', 52), HeightRule.EXACT)], [CWl, CW - CWl]);
  return inner(C.headers[6], [secHeading(11, C.adv_title), sp(3.6), warn, sp(tune('adv_gap1', 6)), two, sp(tune('adv_gap2', 6)), closing]);
}

// ================================================================ assemble
const doc = new Document({
  creator: C.company, title: `${C.price_row[0]} ${C.price_row[1]} 报价单`, description: C.doctitle,
  styles: { default: { document: { run: { font: FONT, size: 21, color: K.ink }, paragraph: { spacing: { before: 0, after: 0, line: 20, lineRule: 'exact' } } } } },
  sections: [cover(), pQuote(), pSpecs(), pMaterials(), pSystems(), pElectrical(), pCompany(), pAdvice()],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log('wrote', OUT, buf.length); });
