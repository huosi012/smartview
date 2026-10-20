#!/usr/bin/env bash
# Rebuilds output/<variant>/: backgrounds, layered SVG, print PDF, previews.
#   v1 = red-brown macro leaf, v2 = 大兴安岭 autumn forest
# Needs: node + playwright (Chromium), python3 with pillow, fonttools, uharfbuzz, reportlab.
set -euo pipefail
cd "$(dirname "$0")"
FONT_DIR=${FONT_DIR:-.fonts}
PX_PER_CM=${PX_PER_CM:-40}   # 40 px/cm ≈ 102 dpi at 1:1
VARIANTS=${VARIANTS:-v1 v2}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

src/fetch_fonts.sh "$FONT_DIR"

for v in $VARIANTS; do
  out=output/$v
  node src/render-bg.js "$tmp/$v" "$PX_PER_CM" ABCD "$v"

  mkdir -p "$out/backgrounds"
  python3 - "$tmp/$v" "$PX_PER_CM" "$out" <<'PY'
import sys
from PIL import Image
tmp, s, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
for k, size in zip("ABCD", ["150x45", "150x45", "110x50", "110x50"]):
    Image.open(f"{tmp}/bg_{k}.png").convert("RGB").save(
        f"{out}/backgrounds/bg_{k}_{size}cm.jpg", quality=93, subsampling=0, dpi=(s * 2.54, s * 2.54))
PY

  python3 src/layout.py "$FONT_DIR" "$out" "$v"
  title=$([ "$v" = v2 ] && echo "万象城车贴 · 秋冬 · 大兴安岭秋林 · 每个×2" || echo "万象城车贴 · 秋冬 · 红棕叶片 · 每个×2")
  node src/render-mockups.js "$out/layered" "$tmp/$v/mockups" "$FONT_DIR" 2 "$title"

  mkdir -p "$out/preview"
  python3 - "$tmp/$v/mockups" "$out" <<'PY'
import sys, pathlib
from PIL import Image
for f in pathlib.Path(sys.argv[1]).glob("*.png"):
    Image.open(f).convert("RGB").save(f"{sys.argv[2]}/preview/{f.stem}.jpg", quality=90)
PY
done
ls -la output/*/*
