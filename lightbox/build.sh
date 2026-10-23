#!/usr/bin/env bash
# 一键重建：下载字体（缺失时）→ 生成 SVG → 打印 PDF → 导出预览图
# 依赖：python3 + fonttools，node + playwright（Chromium），poppler-utils（pdftoppm）
set -euo pipefail
cd "$(dirname "$0")"

FONTS=src/fonts
mkdir -p "$FONTS"
fetch() { [ -s "$FONTS/$1" ] || curl -sSfL -o "$FONTS/$1" "$2"; }
# 站酷快乐体、思源黑体（Noto Sans SC），均为 SIL OFL 开源字体，可免费商用
fetch KuaiLe.ttf         https://fonts.gstatic.com/s/zcoolkuaile/v22/tssqApdaRQokwFjFJjvM6h2Wpg.ttf
fetch NotoSansSC-500.ttf https://fonts.gstatic.com/s/notosanssc/v41/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaG-3FnYw.ttf
fetch NotoSansSC-700.ttf https://fonts.gstatic.com/s/notosanssc/v41/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaGzjCnYw.ttf
fetch NotoSansSC-900.ttf https://fonts.gstatic.com/s/notosanssc/v41/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaG3bCnYw.ttf

python3 -I src/build.py "$FONTS" lightbox.svg
node src/render.cjs lightbox.svg .
pdftoppm -jpeg -jpegopt quality=90 -scale-to-x 1260 -scale-to-y 2660 -singlefile lightbox_1260x2660mm.pdf preview
echo "完成：lightbox_1260x2660mm.pdf / lightbox_bleed30_1320x2720mm.pdf / lightbox.svg / preview.jpg"
