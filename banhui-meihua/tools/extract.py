import sys, json
from lxml import etree
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
MC='http://schemas.openxmlformats.org/markup-compatibility/2006'
ns={'w':W,'mc':MC}
doc=etree.parse(sys.argv[1])
body=doc.getroot().find('w:body',ns)
def strip_fallback(el):
    for fb in el.iter('{%s}Fallback'%MC):
        pass
    for fb in list(el.iter('{%s}Fallback'%MC)):
        fb.getparent().remove(fb)
strip_fallback(body)
def ptext(p, include_txbx=False):
    out=[]
    for t in p.iter('{%s}t'%W, '{%s}tab'%W, '{%s}br'%W):
        # skip text inside textboxes unless asked
        anc=[a for a in t.iterancestors() if a.tag=='{%s}txbxContent'%W]
        if anc and not include_txbx: continue
        if t.tag.endswith('}t'): out.append(t.text or '')
        elif t.tag.endswith('}tab'): out.append('\t')
        else: out.append('\n')
    return ''.join(out)
items=[]
for el in body:
    tag=etree.QName(el).localname
    if tag=='p':
        txbx=[]
        for tb in el.iter('{%s}txbxContent'%W):
            # skip nested txbx duplicates
            if any(a.tag=='{%s}txbxContent'%W for a in tb.iterancestors()): continue
            txbx.append([ptext(p,True) for p in tb.findall('w:p',ns)])
        ndraw=len(list(el.iter('{%s}drawing'%W)))
        blips=[b.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed') for b in el.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}blip')]
        items.append({'t':'p','text':ptext(el),'txbx':txbx,'draw':ndraw,'img':blips})
    elif tag=='tbl':
        rows=[]
        for tr in el.findall('w:tr',ns):
            rows.append(['\n'.join(ptext(p) for p in tc.findall('.//w:p',ns)) for tc in tr.findall('w:tc',ns)])
        items.append({'t':'tbl','rows':rows})
json.dump(items,open(sys.argv[2],'w'),ensure_ascii=False,indent=1)
for i,it in enumerate(items):
    if it['t']=='p':
        print(i, repr(it['text'][:70]), ('TXBX:'+repr(it['txbx'])[:300]) if it['txbx'] else '', ('IMG'+str(it['img'])) if it['img'] else '')
    else: print(i,'TABLE',it['rows'])
