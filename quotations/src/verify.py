import sys, re, docx, subprocess, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fixes import fix
src, pdf = sys.argv[1], sys.argv[2]
txt = subprocess.run(['pdftotext', '-raw', pdf, '-'], capture_output=True, text=True).stdout
norm = lambda s: re.sub(r'\s+', '', s)
P = norm(txt)
d = docx.Document(src)
segs = [fix(p.text) for p in d.paragraphs if p.text.strip()]
for t in d.tables:
    for row in t.rows:
        prev = None
        for c in row.cells:
            if c._tc is prev: continue
            prev = c._tc
            segs += fix(c.text).split('\n')
miss = []
for s in segs:
    s = norm(s)
    if not s: continue
    if s in P: continue
    s2 = s.rstrip('：:；;')
    if s2 and s2 in P: continue
    # split into sub-pieces on enumerations/colons and test each
    parts = [x for x in re.split(r'（[一二三四五六七八九十]）|：', s) if x]
    if parts and all(x.rstrip('：:；;') in P for x in parts):
        continue
    # long paragraphs laid out as separate points: check sentence by sentence
    sents = [x for x in re.split(r'[：。]', s) if x]
    if len(sents) > 1 and all(x in P for x in sents):
        continue
    miss.append(s)
print('segments checked:', len([x for x in segs if x.strip()]))
print('not found verbatim:', len(miss))
for m in miss: print('  -', m)
