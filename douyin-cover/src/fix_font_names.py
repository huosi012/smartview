"""Give the merged Noto Black fonts clean family names.

The fontsource slices carry names inherited from a variable-font instance
("Noto Serif SC ExtraLight Black"), which PowerPoint/WPS would show as an
odd family. Rewrite them so the deck can reference "Noto Serif SC Black".
Usage: python3 -I fix_font_names.py <merged.woff2> <out.ttf> "<Family>" <PostScriptName>
"""
import sys
from fontTools.ttLib import TTFont

src, dst, family, ps = sys.argv[1:5]
font = TTFont(src)
font.flavor = None
name = font["name"]
name.names = [r for r in name.names if r.nameID not in (1, 2, 3, 4, 6, 16, 17, 21, 22, 25)]
base, weight = family.rsplit(" ", 1)
for nid, value in {
    1: family, 2: "Regular", 3: f"{ps};merged", 4: family, 6: ps,
    16: base, 17: weight,
}.items():
    name.setName(value, nid, 3, 1, 0x409)
    name.setName(value, nid, 1, 0, 0)
font["OS/2"].usWeightClass = 900
font["OS/2"].fsSelection = (font["OS/2"].fsSelection & ~0b1100001) | 0b1000000  # REGULAR
font["head"].macStyle = 0
font.save(dst)
print(dst, name.getDebugName(1), "/", name.getDebugName(4))
