#!/usr/bin/env python3
"""生成 PDF 渲染用的“宋体”替代字体。

LibreOffice 环境中没有 Windows 宋体（SimSun）。AR PL UMing CN 与宋体字宽完全相同
（汉字 1 em、西文 0.5 em），只是行距较紧。本脚本把它的行高调为 1.25 em，
使 LibreOffice 中 7.5–10 号字的行距与 Excel 屏幕上宋体的行距一致，
从而让 PDF 与 Excel 的换行、行高、分页保持一致。

用法：python3 make_song_font.py ~/.local/share/fonts/UMingSongXL.ttf
然后把 fonts.conf 放到 ~/.config/fontconfig/ 并执行 fc-cache -f。
"""
import sys

from fontTools.ttLib import TTCollection

SRC = "/usr/share/fonts/truetype/arphic/uming.ttc"   # apt: fonts-arphic-uming
FAMILY = "UMing Song XL"
LINE_EM = 1.25


def main(out):
    font = TTCollection(SRC).fonts[0]                  # AR PL UMing CN
    upm = font["head"].unitsPerEm
    hhea, os2 = font["hhea"], font["OS/2"]
    extra = (LINE_EM * upm - (hhea.ascent - hhea.descent)) / 2
    asc, desc = round(hhea.ascent + extra), round(-hhea.descent + extra)
    hhea.ascent, hhea.descent, hhea.lineGap = asc, -desc, 0
    os2.usWinAscent, os2.usWinDescent = asc, desc
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = asc, -desc, 0
    name = font["name"]
    for nid in (1, 2, 3, 4, 6, 16, 17, 18, 21, 22):
        name.removeNames(nameID=nid)
    ps = FAMILY.replace(" ", "")
    for pid, eid, lid in ((3, 1, 0x409), (1, 0, 0)):
        name.setName(FAMILY, 1, pid, eid, lid)
        name.setName("Regular", 2, pid, eid, lid)
        name.setName(ps, 3, pid, eid, lid)
        name.setName(FAMILY + " Regular", 4, pid, eid, lid)
        name.setName(ps + "-Regular", 6, pid, eid, lid)
    font.save(out)


if __name__ == "__main__":
    main(sys.argv[1])
