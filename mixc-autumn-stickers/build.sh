#!/usr/bin/env bash
# Rebuilds everything in output/: backgrounds, layered SVG, print PDF, previews.
# Needs: node + playwright (Chromium), python3 with pillow, fonttools, uharfbuzz, reportlab, potracer.
set -euo pipefail
cd "$(dirname "$0")"
FONT_DIR=${FONT_DIR:-.fonts}
PX_PER_CM=${PX_PER_CM:-40}   # 40 px/cm ≈ 102 dpi at 1:1
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

src/fetch_fonts.sh "$FONT_DIR"
node src/render-bg.js "$tmp" "$PX_PER_CM"

mkdir -p output/backgrounds
python3 - "$tmp" "$PX_PER_CM" <<'PY'
import sys
from PIL import Image
tmp, s = sys.argv[1], float(sys.argv[2])
for k, size in zip("ABCD", ["150x45", "150x45", "110x50", "110x50"]):
    Image.open(f"{tmp}/bg_{k}.png").convert("RGB").save(
        f"output/backgrounds/bg_{k}_{size}cm.jpg", quality=93, subsampling=0, dpi=(s * 2.54, s * 2.54))
PY

python3 src/layout.py "$FONT_DIR" output
node src/render-mockups.js output/layered "$tmp/mockups" "$FONT_DIR" 2

mkdir -p output/preview
python3 - "$tmp/mockups" <<'PY'
import sys, pathlib
from PIL import Image
for f in pathlib.Path(sys.argv[1]).glob("*.png"):
    Image.open(f).convert("RGB").save(f"output/preview/{f.stem}.jpg", quality=90)
PY
ls -la output/*
