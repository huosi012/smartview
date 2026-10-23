#!/usr/bin/env bash
# Rebuild everything: assets -> sample covers -> mockups -> final deck ->
# preview JPGs. Needs python3 (Pillow, numpy, fontTools), node, LibreOffice
# and poppler, with the fonts in ../fonts installed. Set SOFFICE to override
# the LibreOffice command.
set -euo pipefail
cd "$(dirname "$0")"
SOFFICE=${SOFFICE:-soffice}

python3 -I make_assets.py
[ -d node_modules ] || npm install --no-audit --no-fund
node build.js --preview

rm -f build/preview.pdf build/cover-*.png
$SOFFICE --headless --convert-to pdf --outdir build build/preview.pptx >/dev/null
pdftoppm -png -scale-to-x 1080 -scale-to-y 1440 build/preview.pdf build/cover
python3 -I make_mockups.py

node build.js

rm -f build/deck.pdf build/deck-*.png
cp ../抖音封面模板.pptx build/deck.pptx
$SOFFICE --headless --convert-to pdf --outdir build build/deck.pptx >/dev/null
pdftoppm -png -scale-to-x 1080 -scale-to-y 1440 build/deck.pdf build/deck
python3 -I export_previews.py
