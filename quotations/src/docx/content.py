"""Export the quotation text (source docx + fixes.py) as JSON for the Word build.

Mirrors the selections made in build.py so the .docx carries exactly the PDF's wording.
"""
import sys, json, re
import docx
from fixes import fix

SRC, OUT = sys.argv[1], sys.argv[2]
TOTAL_PAGES = int(sys.argv[3]) if len(sys.argv) > 3 else 8

d = docx.Document(SRC)
T = d.tables


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
INFO, PRICE, R = rows_of(T[0]), rows_of(T[1]), rows_of(T[2])
lab = lambda s: s.strip().rstrip('：:').strip()
kv = lambda i: (lab(R[i][0]), R[i][1].strip())

BRANDS = ['宇电', '正泰·施耐德', '正泰', '白云机电', 'APT/AD16', 'HS48S-99.99', 'K型']


def runs(s):
    """split text into [{t, b}] runs, bolding the first brand mentions (same rule as the PDF)"""
    marks, done = [], set()
    for b in BRANDS:
        if any(b in x for x in done):
            continue
        i = s.find(b)
        if i >= 0 and not any(i < e and i + len(b) > a for a, e in marks):
            marks.append((i, i + len(b)))
            done.add(b)
    marks.sort()
    out, pos = [], 0
    for a, e in marks:
        if a > pos:
            out.append({'t': s[pos:a]})
        out.append({'t': s[a:e], 'b': True})
        pos = e
    if pos < len(s):
        out.append({'t': s[pos:]})
    return out


def info_cell(s):
    k, _, v = s.strip().partition('：')
    v = v.strip()
    if k == 'Page' and not v:
        v = f'共 {TOTAL_PAGES} 页'
    return [k, v]


door_head, _, door_rest = R[14][1].strip().partition('：')
door_items = [x.strip() for x in re.split(r'(?=（[一二三四五六七八九十]）)', door_rest) if x.strip()]
ov_lead, _, ov_body = R[7][0].partition('：')
adv = R[54][0].split('\n')
el_head, _, el_note = R[35][0].partition('：')
tn_k, _, tn_v = R[34][0].partition('：')
inner_k, inner_v = R[4][0], R[4][1]

C = {
    'company': paras[0], 'doctitle': paras[1], 'quote_title': paras[2], 'spec_title': lab(paras[3]),
    'company_en': 'WUJIANG CHANGSHENG OVEN EQUIPMENT MANUFACTURING CO., LTD',
    'tel': INFO[1][1].strip(), 'fax': INFO[2][1].strip(),
    'date': INFO[0][0].strip(), 'ref': INFO[0][1].strip(),
    'info': [info_cell(c) for row in INFO for c in row],
    'price_header': PRICE[0],
    'price_row': [PRICE[1][0].strip().rstrip('：:'), PRICE[1][1], PRICE[1][2], PRICE[1][3], PRICE[1][4]],
    'price_sub': f'{inner_k} {inner_v} {R[4][2]}',
    'total': [lab(PRICE[2][0]), PRICE[2][1], PRICE[2][2]],
    'terms_title': lab(R[47][0]),
    'terms': [list(kv(i)) + [ic] for i, ic in zip([48, 49, 50, 51, 52, 53], ['clock', 'box', 'shield', 'truck', 'card', 'cal'])],
    'tiles': [
        [dict(k=lab(R[0][0]), big='常温-300℃', small='（任意可调）', cls='feature', w=1.3),
         dict(k=lab(R[3][0]), big='室温-200℃', small='可调', cls='hot', w=1.3),
         dict(k=lab(R[1][0]), big='±1℃', small='', cls='hot', w=.7),
         dict(k=lab(R[2][0]), big='±3℃', small='（空载状态下）', cls='hot', w=.7)],
        [dict(k=lab(R[4][0]), big='1200×1500×1500', unit=R[4][2], small=R[4][3], cls='dim', w=1),
         dict(k=lab(R[5][0]), big='1400×2200×2200', unit=R[5][2], small='（以实际为准）', cls='dim', w=1)],
        [dict(k=lab(R[1][2]), big=R[1][3], small='', cls='el', w=1.5),
         dict(k=lab(R[2][2]), big='21KW', pre='功率', small='', cls='el', w=1),
         dict(k=lab(R[3][2]), big='1100W', small='（380V）', cls='el', w=1),
         dict(k=lab(R[0][2]), big=R[0][3], small='', cls='el', w=1)],
    ],
    'overview_title': lab(R[6][0]), 'overview_lead': ov_lead + '：',
    'overview': [x + '。' for x in ov_body.split('。') if x.strip()],
    'materials_title': lab(R[8][0]),
    'materials': [],
    'air_title': lab(R[23][0]), 'air': [[kv(i)[0], runs(kv(i)[1])] for i in (24, 25)],
    'circ_title': lab(R[26][0]), 'circ': [[kv(i)[0], runs(kv(i)[1])] for i in (27, 28, 29)],
    'heat_title': lab(R[30][0]), 'heat': [[kv(i)[0], runs(kv(i)[1])] for i in (31, 32, 33)],
    'test_note': [tn_k + '：', tn_v],
    'el_title': el_head, 'el_note': el_note, 'el': [[kv(i)[0], runs(kv(i)[1])] for i in range(36, 47)],
    'prod_title': '产品实物图', 'gal_note': '图片仅供参考，以实物为准', 'co_title': '公司设备',
    'adv_title': lab(adv[0]), 'warn': adv[1], 'ban': '严禁直接烘烤酒精等易燃易爆物品！',
    'install_title': lab(adv[2]), 'install': [adv[3], adv[4]],
    'env_title': lab(adv[5]),
    'env': [[t.strip().rstrip('；;'), ic] for t, ic in zip(adv[6:12], ['thermo', 'drop', 'wave', 'zap', 'flask', 'ground'])],
    'thanks': adv[12].split('，', 1), 'closing_company': adv[13],
    'headers': ['报价单 · ' + paras[2], '规格参数 · 设备概述', lab(R[8][0]), '进气排气 · 循环 · 加热系统',
                el_head + ' · 产品实物图', '公司设备', lab(adv[0])],
    'total_pages': TOTAL_PAGES,
}
C['thanks'][0] += '，'
for i in range(9, 23):
    k, v = kv(i)
    if i == 14:
        C['materials'].append({'k': k, 'door_head': door_head + '：', 'door': [[it[:3], it[3:].strip()] for it in door_items]})
    elif i == 19:
        C['materials'].append({'k': k, 'chip': v})
    else:
        C['materials'].append({'k': k, 'v': runs(v)})

json.dump(C, open(OUT, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
print('ok', len(C['materials']), len(C['el']), len(C['overview']))
