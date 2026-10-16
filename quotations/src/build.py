"""Build the CS881-TG quotation HTML. All wording comes from the source docx."""
import sys, html, re
import docx
from docx.table import Table
from fixes import fix

SRC, OUT = sys.argv[1], sys.argv[2]
TOTAL_PAGES = int(sys.argv[3]) if len(sys.argv) > 3 else 8

d = docx.Document(SRC)
tables = d.tables


def rows_of(t):
    out = []
    for row in t.rows:
        cells, prev = [], None
        for c in row.cells:
            if c._tc is prev:
                continue
            prev = c._tc
            cells.append(fix(c.text))
        out.append(cells)
    return out


paras = [fix(p.text) for p in d.paragraphs if p.text.strip()]
COMPANY, DOCTITLE = paras[0], paras[1]          # 吴江长胜烘箱设备制造有限公司 / 烘箱技术规范合同附件
QUOTE_TITLE = paras[2]                          # QUOTATION（报价）
INFO = rows_of(tables[0])
PRICE = rows_of(tables[1])
R = rows_of(tables[2])


def e(s):
    return html.escape(s)


def lab(s):
    return s.strip().rstrip('：:').strip()


def kv(i):
    """label/value pair of a spec row"""
    return lab(R[i][0]), R[i][1].strip()


BRANDS = ['宇电', '正泰·施耐德', '正泰', '白云机电', 'APT/AD16', 'HS48S-99.99', 'K型']


def brandify(s):
    out = e(s)
    done = set()
    for b in BRANDS:
        if any(b in x for x in done):
            continue
        eb = e(b)
        if eb in out:
            out = out.replace(eb, f'<b class="brand">{eb}</b>', 1)
            done.add(b)
    return out


ICONS = {
    'clock': '<circle cx="12" cy="12" r="9.5"/><polyline points="12 6.5 12 12 15.5 14"/>',
    'box': '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.3 7 12 12 20.7 7"/><line x1="12" y1="22" x2="12" y2="12"/>',
    'shield': '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    'truck': '<path d="M10 17h4V5H2v12h3"/><path d="M20 17h2v-3.34a4 4 0 0 0-1.17-2.83L19 9h-5"/><path d="M14 17h1"/><circle cx="7.5" cy="17.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
    'card': '<rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/><line x1="6" y1="15" x2="10" y2="15"/>',
    'cal': '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
    'alert': '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    'info': '<circle cx="12" cy="12" r="9.5"/><line x1="12" y1="16" x2="12" y2="11.5"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
    'thermo': '<path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/>',
    'drop': '<path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/>',
    'wave': '<path d="M2 12c2-4 4-4 6 0s4 4 6 0 4-4 6 0"/><path d="M2 18c2-4 4-4 6 0s4 4 6 0 4-4 6 0" opacity=".45"/><path d="M2 6c2-4 4-4 6 0s4 4 6 0 4-4 6 0" opacity=".45"/>',
    'zap': '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    'flask': '<path d="M9 3h6"/><path d="M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2.2h12.4a1.5 1.5 0 0 0 1.3-2.2L14 9V3"/><line x1="7" y1="15" x2="17" y2="15"/>',
    'ground': '<line x1="12" y1="2" x2="12" y2="12"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="7" y1="16" x2="17" y2="16"/><line x1="10" y1="20" x2="14" y2="20"/>',
}


def icon(name, cls='ic'):
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')



def deco(variant='inner'):
    """decorative background layer: soft gradients + intersecting brand-colour bands (mm coordinates)"""
    if variant == 'cover':
        return '''<svg class="deco" viewBox="0 0 210 297" preserveAspectRatio="none">
  <defs>
    <linearGradient id="cvT" x1="1" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#2E94A6" stop-opacity=".30"/><stop offset="1" stop-color="#2E94A6" stop-opacity="0"/></linearGradient>
    <linearGradient id="cvO" x1="1" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#E8743A" stop-opacity=".28"/><stop offset="1" stop-color="#E8743A" stop-opacity="0"/></linearGradient>
  </defs>
  <polygon points="118,297 150,297 210,262 210,236" fill="url(#cvT)"/>
  <polygon points="160,297 176,297 210,276 210,256" fill="url(#cvO)"/>
  <polygon points="186,297 210,297 210,248 196,256" fill="#0F4C5C" opacity=".07"/>
</svg>'''
    return '''<svg class="deco" viewBox="0 0 210 297" preserveAspectRatio="none">
  <defs>
    <radialGradient id="gTR" cx="1" cy="0" r=".55"><stop offset="0" stop-color="#2E94A6" stop-opacity=".16"/><stop offset="1" stop-color="#2E94A6" stop-opacity="0"/></radialGradient>
    <radialGradient id="gBL" cx="0" cy="1" r=".5"><stop offset="0" stop-color="#E8743A" stop-opacity=".07"/><stop offset=".5" stop-color="#2E94A6" stop-opacity=".05"/><stop offset="1" stop-color="#2E94A6" stop-opacity="0"/></radialGradient>
    <linearGradient id="bT" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2E94A6" stop-opacity=".42"/><stop offset="1" stop-color="#2E94A6" stop-opacity="0"/></linearGradient>
    <linearGradient id="bO" x1="1" y1="0" x2=".2" y2="1"><stop offset="0" stop-color="#E8743A" stop-opacity=".36"/><stop offset="1" stop-color="#E8743A" stop-opacity="0"/></linearGradient>
    <linearGradient id="bD" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#0F4C5C" stop-opacity=".26"/><stop offset="1" stop-color="#0F4C5C" stop-opacity="0"/></linearGradient>
    <linearGradient id="bL" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#E8743A" stop-opacity=".30"/><stop offset=".55" stop-color="#2E94A6" stop-opacity=".18"/><stop offset="1" stop-color="#2E94A6" stop-opacity="0"/></linearGradient>
  </defs>
  <rect width="210" height="297" fill="url(#gTR)"/>
  <rect width="210" height="297" fill="url(#gBL)"/>
  <polygon points="138,0 160,0 210,34 210,54" fill="url(#bT)"/>
  <polygon points="178,0 188,0 210,64 210,84" fill="url(#bO)"/>
  <polygon points="194,0 210,0 210,22" fill="#0F4C5C" opacity=".18"/>
  <circle cx="210" cy="0" r="46" fill="none" stroke="#2E94A6" stroke-width=".3" opacity=".45"/>
  <circle cx="210" cy="0" r="58" fill="none" stroke="#2E94A6" stroke-width=".18" opacity=".22"/>
  <polygon points="0,248 0,270 52,297 78,297" fill="url(#bD)"/>
  <polygon points="0,222 0,236 36,297 50,297" fill="url(#bL)"/>
  <polygon points="0,280 0,297 20,297" fill="#E8743A" opacity=".30"/>
</svg>'''

# ---------------------------------------------------------------- page chrome
def header(section):
    return f'''
<header class="run">
  <img class="run-logo" src="assets/logo.png" alt="">
  <div class="run-meta">
    <div class="run-doc">{e(DOCTITLE)}</div>
    <div class="run-sec">{section}</div>
  </div>
</header>'''


def footer(n):
    tel = INFO[1][1].strip()
    fax = INFO[2][1].strip()
    return f'''
<footer class="run">
  <div class="f-left"><b>{e(COMPANY)}</b><span>{e(tel)}</span><span>{e(fax)}</span></div>
  <div class="f-right">第 <b>{n}</b> 页<i>/</i>共 {TOTAL_PAGES} 页</div>
</footer>'''


def sec(no, title, extra=''):
    return f'<div class="sec"><span class="no">{no:02d}</span><h2>{e(title)}</h2>{extra}<span class="rule"></span></div>'


def kv_table(idx, cls='kv', fmt=brandify):
    out = [f'<table class="{cls}">']
    for i in idx:
        k, v = kv(i)
        out.append(f'<tr><th>{e(k)}</th><td>{fmt(v)}</td></tr>')
    out.append('</table>')
    return ''.join(out)


pages = []

# =============================================================== P1 cover
inner_k, inner_v = kv(4)
temp_k, temp_v = kv(0)
acc_k, acc_v = kv(1)
pow_k, pow_v = R[2][2], R[2][3]
pname = PRICE[1][0].strip().rstrip('：:')
model = PRICE[1][1].strip()
date_t, ref_t = INFO[0][0].strip(), INFO[0][1].strip()

pages.append(f'''
<section class="page cover">
  {deco('cover')}
  <div class="cv-top">
    <img class="cv-logo" src="assets/logo.png" alt="">
    <div class="cv-ref"><span>{e(ref_t)}</span><span>{e(date_t)}</span></div>
  </div>
  <div class="cv-hero">
    <svg class="cv-arcs" viewBox="0 0 210 212" preserveAspectRatio="none">
      <path d="M58 212 C 52 120, 110 46, 214 30 L 214 40 C 128 58, 76 128, 82 212 Z" fill="#2E94A6" opacity=".16"/>
      <circle cx="140" cy="128" r="74" fill="none" stroke="#8FD3DF" stroke-width=".25" opacity=".35"/>
      <circle cx="140" cy="128" r="96" fill="none" stroke="#8FD3DF" stroke-width=".2" opacity=".22"/>
    </svg>
    <div class="cv-floor"></div>
    <div class="cv-title">
      <div class="cv-eyebrow">{e(QUOTE_TITLE)}</div>
      <h1>{e(pname)}</h1>
      <div class="cv-sub">{e(DOCTITLE)}</div>
    </div>
    <div class="cv-side">
      <div class="cv-model"><span>型号</span><b>{e(model)}</b></div>
      <dl>
        <div><dt>{e(lab(inner_k))}</dt><dd class="num">{e(inner_v)}<small>{e(R[4][2])}</small></dd><dd class="sub">{e(R[4][3])}</dd></div>
        <div><dt>{e(lab(temp_k))}</dt><dd class="num">常温-300℃</dd><dd class="sub">（任意可调）</dd></div>
        <div><dt>{e(lab(acc_k))}</dt><dd class="num">{e(acc_v)}</dd></div>
        <div><dt>{e(lab(pow_k))}</dt><dd class="num"><small class="pre">功率</small>21KW</dd></div>
      </dl>
    </div>
    <i class="cv-glow"></i><i class="cv-stage"></i><i class="cv-shadow"></i><div class="cv-prod"><img src="assets/cover_c1.png" alt=""></div>
  </div>
  <div class="cv-foot">
    <div class="cv-co">
      <div class="cn">{e(COMPANY)}</div>
      <div class="en">WUJIANG CHANGSHENG OVEN EQUIPMENT MANUFACTURING CO., LTD</div>
    </div>
    <div class="cv-contact">
      <div>{e(INFO[1][1].strip())}</div>
      <div>{e(INFO[2][1].strip())}</div>
    </div>
  </div>
</section>''')

# =============================================================== P2 quotation
def info_cell(s):
    k, _, v = s.strip().partition('：')
    v = v.strip()
    if k == 'Page' and not v:
        v = f'共 {TOTAL_PAGES} 页'
    val = f'<b>{e(v)}</b>' if v else '<b class="blank"></b>'
    return f'<div class="ic-cell"><span>{e(k)}</span>{val}</div>'


info_html = ''.join(info_cell(c) for row in INFO for c in row)
hdr = PRICE[0]
row = PRICE[1]
tot = PRICE[2]  # 人民币总计： | 叁万叁仟元整 | 含税含运费

terms_idx = [48, 49, 50, 51, 52, 53]
term_icons = ['clock', 'box', 'shield', 'truck', 'card', 'cal']
terms_html = ''.join(
    f'<div class="term">{icon(ic)}<div><span>{e(kv(i)[0])}</span><p>{e(kv(i)[1])}</p></div></div>'
    for i, ic in zip(terms_idx, term_icons))

pages.append(f'''
<section class="page">
  {deco()}
  {header('报价单 · ' + e(QUOTE_TITLE))}
  <div class="content fill spread">
    <div class="q-head">
      <div>
        <div class="q-eyebrow">{e(QUOTE_TITLE)}</div>
        <h1 class="q-title">报价单</h1>
      </div>
      <div class="q-badge">{e(pname)}<b>{e(model)}</b></div>
    </div>
    <div class="info-grid">{info_html}</div>

    <table class="price">
      <thead><tr>{''.join(f'<th>{e(h)}</th>' for h in hdr)}</tr></thead>
      <tbody><tr>
        <td class="pn"><i class="thumb"><img src="assets/cut_p2_sm.png" alt=""></i><div><b>{e(row[0].strip().rstrip('：:'))}</b><span>{e(inner_k)} {e(inner_v)} {e(R[4][2])}</span></div></td>
        <td class="mono">{e(row[1])}</td>
        <td>{e(row[2])}</td>
        <td class="mono">{e(row[3])}</td>
        <td class="mono strong">{e(row[4])}</td>
      </tr></tbody>
    </table>
    <div class="total">
      <div class="t-l"><span>{e(lab(tot[0]))}</span><b>{e(tot[1])}</b></div>
      <div class="t-r"><em>{e(tot[2])}</em><b class="num">{e(row[4])}</b></div>
    </div>

    {sec(1, lab(R[47][0]))}
    <div class="terms">{terms_html}</div>

  </div>
  {footer(len(pages)+1)}
</section>''')

# =============================================================== P3 specs + overview
def tile_rows(rows, templates):
    """each tile = background + label/value/sub placed on a shared row grid so values share a baseline"""
    out = []
    for row, tpl in zip(rows, templates):
        out.append(f'<div class="trow" style="grid-template-columns:{tpl}">')
        r = 1
        col = 1
        for (k, big, small, unit, pre, cls, span) in row:
            gc = f'grid-column:{col} / span {span}'
            pre_h = f'<small class="pre">{e(pre)}</small>' if pre else ''
            unit_h = f'<small class="unit">{e(unit)}</small>' if unit else ''
            out.append(f'<div class="tb {cls}" style="{gc};grid-row:{r} / span 3"></div>')
            out.append(f'<span class="tk {cls}" style="{gc};grid-row:{r}">{e(k)}</span>')
            out.append(f'<b class="tv num {cls}" style="{gc};grid-row:{r + 1}">{pre_h}{e(big)}{unit_h}</b>')
            out.append(f'<em class="ts {cls}" style="{gc};grid-row:{r + 2}">{e(small) if small else "&nbsp;"}</em>')
            col += span
        out.append('</div>')
    return ''.join(out)


tiles = tile_rows([
    [(lab(R[0][0]), '常温-300℃', '（任意可调）', '', '', 'hot feature', 1),
     (lab(R[3][0]), '室温-200℃', '可调', '', '', 'hot', 1),
     (lab(R[1][0]), '±1℃', '', '', '', 'hot', 1),
     (lab(R[2][0]), '±3℃', '（空载状态下）', '', '', 'hot', 1)],
    [(lab(R[4][0]), '1200×1500×1500', R[4][3], R[4][2], '', 'dim', 2),
     (lab(R[5][0]), '1400×2200×2200', '（以实际为准）', R[5][2], '', 'dim', 2)],
    [(lab(R[1][2]), R[1][3], '', '', '', 'el', 1),
     (lab(R[2][2]), '21KW', '', '', '功率', 'el', 1),
     (lab(R[3][2]), '1100W', '（380V）', '', '', 'el', 1),
     (lab(R[0][2]), R[0][3], '', '', '', 'el', 1)],
], ['1.3fr 1.3fr .7fr .7fr', '1fr 1fr', '1.5fr 1fr 1fr 1fr'])

ov = R[7][0]
ov_lead, _, ov_body = ov.partition('：')
ov_sents = [x + '。' for x in ov_body.split('。') if x.strip()]
ov_items = ''.join(f'<li><i>{n:02d}</i><p>{e(t)}</p></li>' for n, t in enumerate(ov_sents, 1))

pages.append(f'''
<section class="page">
  {deco()}
  {header('规格参数 · 设备概述')}
  <div class="content fill">
    {sec(2, lab(paras[3]))}
    <div class="tiles">{tiles}</div>
    {sec(3, lab(R[6][0]))}
    <div class="ov-wrap g1">
      <div class="ov-lead">{e(ov_lead)}：</div>
      <ol class="ov-grid">{ov_items}</ol>
    </div>
  </div>
  {footer(len(pages)+1)}
</section>''')

# =============================================================== P4 materials
door_k, door_v = kv(14)
door_head, _, door_rest = door_v.partition('：')
door_items = [x for x in re.split(r'(?=（[一二三四五六七八九十]）)', door_rest) if x.strip()]
door_html = f'<b>{e(door_head)}：</b><ol class="cn-list">' + ''.join(
    f'<li><i>{e(it[:3])}</i>{e(it[3:].strip())}</li>' for it in door_items) + '</ol>'

mat_rows = []
for i in range(9, 23):
    k, v = kv(i)
    if i == 14:
        mat_rows.append(f'<tr><th>{e(k)}</th><td>{door_html}</td></tr>')
    elif i == 19:
        mat_rows.append(f'<tr class="hl"><th>{e(k)}</th><td><span class="chip">{e(v)}</span></td></tr>')
    else:
        mat_rows.append(f'<tr><th>{e(k)}</th><td>{brandify(v)}</td></tr>')

pages.append(f'''
<section class="page">
  {deco()}
  {header(e(lab(R[8][0])))}
  <div class="content fill">
    {sec(4, lab(R[8][0]))}
    <table class="kv stretch g1">{''.join(mat_rows)}</table>
  </div>
  {footer(len(pages)+1)}
</section>''')

# =============================================================== P5 air / circulation / heating
test_note = R[34][0]
tn_k, _, tn_v = test_note.partition('：')

pages.append(f'''
<section class="page">
  {deco()}
  {header('进气排气 · 循环 · 加热系统')}
  <div class="content fill">
    {sec(5, lab(R[23][0]))}
    {kv_table([24, 25], cls='kv stretch g2')}
    {sec(6, lab(R[26][0]))}
    {kv_table([27, 28, 29], cls='kv stretch g3')}
    {sec(7, lab(R[30][0]))}
    {kv_table([31, 32, 33], cls='kv stretch g3')}
    <div class="note info">{icon('info')}<p><b>{e(tn_k)}：</b>{e(tn_v)}</p></div>
  </div>
  {footer(len(pages)+1)}
</section>''')

# =============================================================== P6 electrical
el_title = R[35][0]
el_head, _, el_note = el_title.partition('：')
pages.append(f'''
<section class="page">
  {deco()}
  {header(e(el_head) + ' · 产品实物图')}
  <div class="content">
    {sec(8, el_head, f'<span class="pill">{e(el_note)}</span>')}
    {kv_table(range(36, 47), cls='kv el-table')}
    {sec(9, '产品实物图')}
    <div class="gal g-prod">
      <figure class="cut"><img src="assets/card_p1.png" alt=""></figure>
      <figure class="cut"><img src="assets/card_p2.png" alt=""></figure>
      <figure class="cut"><img src="assets/card_p3.png" alt=""></figure>
    </div>
    <div class="gal-note">图片仅供参考，以实物为准</div>
  </div>
  {footer(len(pages)+1)}
</section>''')

# =============================================================== P8 company equipment
pages.append(f'''
<section class="page">
  {deco()}
  {header('公司设备')}
  <div class="content fill">
    {sec(10, '公司设备')}
    <div class="gal g-co g1">
      <figure class="a"><img src="assets/c3_m.jpg" alt=""></figure>
      <figure class="b"><img src="assets/c4_m.jpg" alt=""></figure>
      <figure class="c cut"><img src="assets/card_c1.png" alt=""></figure>
      <figure class="d cut"><img src="assets/card_c2.png" alt=""></figure>
      <figure class="e cut"><img src="assets/card_c5.png" alt=""></figure>
    </div>
    <div class="gal-note">图片仅供参考，以实物为准</div>
  </div>
  {footer(len(pages)+1)}
</section>''')

# =============================================================== P9 advice / install / environment / closing
adv = R[54][0].split('\n')
# adv[0] 意见及建议：  adv[1] warning  adv[2] 安装要求：  adv[3..4]  adv[5] 正常工作环境条件：  adv[6..11]  adv[12] thanks  adv[13] company
warn = adv[1]
ban = '严禁直接烘烤酒精等易燃易爆物品！'
warn_html = e(warn).replace(e(ban), f'<b class="ban">{e(ban)}</b>')
env_icons = ['thermo', 'drop', 'wave', 'zap', 'flask', 'ground']
env_items = adv[6:12]
env_html = ''.join(
    f'<div class="env">{icon(ic)}<p>{e(t.strip().rstrip("；;"))}</p></div>' for t, ic in zip(env_items, env_icons))

install_svg = '''
<svg class="plan" viewBox="0 0 300 230" font-family="Inter, NSC, sans-serif">
  <defs>
    <marker id="ar" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 1 L9 5 L0 9 z" fill="#2E94A6"/></marker>
    <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="#9FB4BB" stroke-width="1.2"/></pattern>
  </defs>
  <rect x="8" y="6" width="284" height="8" fill="url(#hatch)"/>
  <rect x="8" y="6" width="8" height="218" fill="url(#hatch)"/>
  <rect x="284" y="6" width="8" height="218" fill="url(#hatch)"/>
  <rect x="8" y="216" width="284" height="8" fill="url(#hatch)"/>
  <rect x="62" y="50" width="176" height="96" rx="3" fill="#EAF4F6" stroke="#0F4C5C" stroke-width="1.6"/>
  <line x1="64" y1="146" x2="236" y2="146" stroke="#2E94A6" stroke-width="4"/>
  <line x1="150" y1="140" x2="150" y2="152" stroke="#fff" stroke-width="1.6"/>
  <text x="150" y="103" text-anchor="middle" font-size="12" font-weight="700" fill="#0F4C5C">设备</text>
  <text x="150" y="138" text-anchor="middle" font-size="8" font-weight="600" fill="#2E94A6">正面</text>
  <line x1="150" y1="16" x2="150" y2="48" stroke="#2E94A6" stroke-width="1.2" marker-start="url(#ar)" marker-end="url(#ar)"/>
  <text x="156" y="35" font-size="9" font-weight="600" fill="#10252E">≥ 700 mm</text>
  <line x1="18" y1="98" x2="60" y2="98" stroke="#2E94A6" stroke-width="1.2" marker-start="url(#ar)" marker-end="url(#ar)"/>
  <text x="39" y="91" text-anchor="middle" font-size="9" font-weight="600" fill="#10252E">≥ 700</text>
  <line x1="240" y1="98" x2="282" y2="98" stroke="#2E94A6" stroke-width="1.2" marker-start="url(#ar)" marker-end="url(#ar)"/>
  <text x="261" y="91" text-anchor="middle" font-size="9" font-weight="600" fill="#10252E">≥ 700</text>
  <line x1="150" y1="148" x2="150" y2="214" stroke="#E2662B" stroke-width="1.4" marker-start="url(#ar)" marker-end="url(#ar)"/>
  <text x="156" y="186" font-size="10" font-weight="800" fill="#C2511C">≥ 1000 mm</text>
</svg>'''
# fix marker colour for front arrow
install_svg = install_svg.replace('</defs>', '<marker id="ar2" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 1 L9 5 L0 9 z" fill="#E2662B"/></marker></defs>')
install_svg = install_svg.replace('stroke="#E2662B" stroke-width="1.4" marker-start="url(#ar)" marker-end="url(#ar)"',
                                  'stroke="#E2662B" stroke-width="1.4" marker-start="url(#ar2)" marker-end="url(#ar2)"')

pages.append(f'''
<section class="page">
  {deco()}
  {header(e(lab(adv[0])))}
  <div class="content fill">
    {sec(11, lab(adv[0]))}
    <div class="note warn">{icon('alert')}<p>{warn_html}</p></div>
    <div class="two g1">
      <div>
        <h3>{e(lab(adv[2]))}</h3>
        <div class="install">
          {install_svg}
          <ul class="dash">
            <li>{e(adv[3])}</li>
            <li>{e(adv[4])}</li>
          </ul>
        </div>
      </div>
      <div>
        <h3>{e(lab(adv[5]))}</h3>
        <div class="envs">{env_html}</div>
      </div>
    </div>
    <div class="closing">
      <div class="thanks">{e(adv[12]).replace('，', '，<br>', 1)}</div>
      <div class="sig">
        <div class="co">{e(adv[13])}</div>
        <div class="dt">{e(date_t)}</div>
        <img class="seal" src="assets/seal.png" alt="">
      </div>
    </div>
  </div>
  {footer(len(pages)+1)}
</section>''')

CSS = open(sys.argv[4] if len(sys.argv) > 4 else 'style.css', encoding='utf8').read()
doc = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{e(pname)} {e(model)} 报价单 - {e(COMPANY)}</title>
<style>{CSS}</style></head>
<body>{''.join(pages)}</body></html>'''
open(OUT, 'w', encoding='utf8').write(doc)
print('pages', len(pages))
