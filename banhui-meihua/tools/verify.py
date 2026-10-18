"""Check every original paragraph/table cell text appears, in order, in the new docx (body text or heading-image alt text)."""
import sys, json, re, zipfile
from lxml import etree
items = json.load(open(sys.argv[1], encoding='utf8'))
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
WP = 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
x = etree.fromstring(zipfile.ZipFile(sys.argv[2]).read('word/document.xml'))
stream = []
for el in x.iter('{%s}t' % W, '{%s}docPr' % WP):
    if el.tag.endswith('}t'):
        stream.append(el.text or '')
    else:
        d = el.get('descr') or ''
        if d.startswith(('【', '环节', '导入', '队伍侦探社  ')):
            stream.append(d)
new = re.sub(r'\s', '', ''.join(stream))
orig = []
for it in items:
    if it['t'] == 'p':
        orig.append(it['text'])
    else:
        orig += [c for r in it['rows'] for c in r]
pos, bad = 0, []
for t in orig:
    t = re.sub(r'\s', '', t)
    if not t:
        continue
    k = new.find(t, pos)
    if k < 0:
        bad.append(t[:30])
    else:
        pos = k + len(t)
total_orig = sum(len(re.sub(r'\s', '', t)) for t in orig)
print('original chars', total_orig, '| new chars', len(new), '| missing paragraphs:', len(bad))
for b in bad: print('  MISSING:', b)
extra = len(new) - total_orig
print('extra chars in new doc (should be 0):', extra)
