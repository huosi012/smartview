"""Per page: lowest text line above the footer (mm from top), to tune how full each Word page is."""
import sys, re, subprocess, html
pdf = sys.argv[1]
x = subprocess.run(['pdftotext', '-bbox', pdf, '-'], capture_output=True, text=True).stdout
pages = x.split('<page ')[1:]
for i, pg in enumerate(pages, 1):
    H = float(re.search(r'height="([\d.]+)"', pg).group(1))
    k = 297 / H
    ys = [(float(m.group(2)) * k, html.unescape(m.group(3))) for m in re.finditer(r'yMin="([\d.]+)" xMax="[\d.]+" yMax="([\d.]+)">([^<]*)<', pg)]
    body = [y for y in ys if y[0] < 281]
    last = max(body, default=(0, ''))
    print(f'page {i}: content ends {last[0]:6.1f} mm  (free to 278: {278 - last[0]:5.1f})  last word: {last[1][:20]}')
