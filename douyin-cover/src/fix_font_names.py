"""Give a merged/subset webfont clean names so PowerPoint and WPS list it as
one predictable family (fontsource files carry odd variable-instance names
such as "Noto Serif SC ExtraLight Black").

Usage: python3 -I fix_font_names.py <in.woff2> <out.ttf> "<Family>" <Weight> [italic]
  e.g. ... NotoSerifSC-600.woff2 NotoSerifSC-SemiBold.ttf "Noto Serif SC" SemiBold
The font is then referenced in the deck as "<Family> <Weight>" (plus italic).
"""
import sys

from fontTools.ttLib import TTFont

WEIGHTS = {"Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700, "Black": 900}

src, dst, family, weight = sys.argv[1:5]
italic = len(sys.argv) > 5 and sys.argv[5] == "italic"
legacy_family = family if weight == "Regular" else f"{family} {weight}"
style = "Italic" if italic else "Regular"
typo_sub = f"{weight} Italic" if italic and weight != "Regular" else ("Italic" if italic else weight)
full = f"{legacy_family} Italic" if italic else legacy_family
ps = (family + "-" + typo_sub).replace(" ", "")

font = TTFont(src)
font.flavor = None
name = font["name"]
name.names = [r for r in name.names if r.nameID not in (1, 2, 3, 4, 6, 16, 17, 21, 22, 25)]
for nid, value in {1: legacy_family, 2: style, 3: f"{ps};fixed", 4: full, 6: ps,
                   16: family, 17: typo_sub}.items():
    name.setName(value, nid, 3, 1, 0x409)
    name.setName(value, nid, 1, 0, 0)
os2 = font["OS/2"]
os2.usWeightClass = WEIGHTS[weight]
os2.fsSelection &= ~0b1100001          # clear ITALIC, BOLD, REGULAR
os2.fsSelection |= 0b1 if italic else 0b1000000
font["head"].macStyle = 0b10 if italic else 0
font.save(dst)
print(dst, "->", legacy_family, "/", style)
