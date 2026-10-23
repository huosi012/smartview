"""Merge the unicode-range slices Google Fonts serves for a CJK font back
into one installable font (fontsource ships them as files/*-900-normal.woff2).

Layout tables are dropped: the covers only need the glyphs and cmap.
Usage: python3 -I merge_font_slices.py <slice-dir> <out.woff2>
"""
import glob
import os
import sys
import tempfile

from fontTools.merge import Merger, Options
from fontTools.ttLib import TTFont

src, out = sys.argv[1:3]
with tempfile.TemporaryDirectory() as tmp:
    parts = []
    for i, f in enumerate(sorted(glob.glob(os.path.join(src, "*.woff2")))):
        font = TTFont(f)
        font.flavor = None
        parts.append(os.path.join(tmp, f"{i}.ttf"))
        font.save(parts[-1])
    merged = Merger(options=Options(drop_tables=["GSUB", "GPOS", "GDEF", "vhea", "vmtx", "VORG"])).merge(parts)
merged.flavor = "woff2"
merged.save(out)
print(out, len(merged.getBestCmap()), "codepoints")
