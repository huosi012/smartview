"""Post-process docx-js output: unique docPr ids (it emits id=1 for all) and schema order inside w:pBdr."""
import sys, zipfile, re, shutil
src, dst = sys.argv[1], sys.argv[2]
zin = zipfile.ZipFile(src)
zout = zipfile.ZipFile(dst + '.tmp', 'w', zipfile.ZIP_DEFLATED)
counter = [100]
def renum(m):
    counter[0] += 1
    return f'<wp:docPr id="{counter[0]}"'
ORDER = ['top', 'left', 'bottom', 'right', 'between', 'bar']


def fix_pbdr(m):
    kids = re.findall(r'<w:(\w+) [^>]*/>', m.group(1))
    els = re.findall(r'(<w:(\w+) [^>]*/>)', m.group(1))
    if len(els) != len(kids):
        return m.group(0)
    els.sort(key=lambda e: ORDER.index(e[1]))
    return '<w:pBdr>' + ''.join(e[0] for e in els) + '</w:pBdr>'


for item in zin.infolist():
    data = zin.read(item.filename)
    if item.filename.startswith('word/') and item.filename.endswith('.xml'):
        t = data.decode('utf8')
        t = re.sub(r'<wp:docPr id="\d+"', renum, t)
        t = re.sub(r'<w:pBdr>(.*?)</w:pBdr>', fix_pbdr, t)
        data = t.encode('utf8')
    zout.writestr(item, data)
zout.close()
shutil.move(dst + '.tmp', dst)
print('docPr ids assigned:', counter[0] - 100)
