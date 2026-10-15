#!/usr/bin/env bash
# Build the client PDF from renders/final: python with Pillow, Chromium (headless) for printing.
#   bash pdf/make_pdf.sh [python] [chrome]
set -e
cd "$(dirname "$0")"
PY=${1:-python3}
CHROME=${2:-$(ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome 2>/dev/null | head -1)}
mkdir -p img
"$PY" - <<'PYEOF'
from PIL import Image
import os
src = "../renders/final"
for fn in sorted(os.listdir(src)):
    im = Image.open(os.path.join(src, fn)).convert("RGB")
    im.thumbnail((3000, 3000) if fn.startswith(("10_", "11_")) else (2200, 2200))
    im.save(os.path.join("img", fn), quality=88)
im = Image.open("../renders/plan2d_clean.jpg").convert("RGB"); im.thumbnail((3000, 3000)); im.save("img/plan2d_clean.jpg", quality=88)
for s, name in (("../renders/comp_p_platform.jpg", "cover.jpg"), ("../renders/aerial.png", "aerial_clean.jpg")):
    im = Image.open(s).convert("RGB"); im.thumbnail((2200, 2200)); im.save(os.path.join("img", name), quality=88)
PYEOF
"$CHROME" --headless=new --no-sandbox --disable-gpu --no-pdf-header-footer --virtual-time-budget=15000 \
  --print-to-pdf="$PWD/智慧农业科普展厅设计方案.pdf" "file://$PWD/proposal.html"
