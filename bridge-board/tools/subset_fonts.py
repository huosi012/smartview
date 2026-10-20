"""Subset the board fonts to the characters used in the page.

usage: python subset_fonts.py <full fonts dir> <source dir>
Re-run after changing any text in source/index.html, otherwise new
characters fall back to a system font in the PDF.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from fontTools.ttLib import TTFont

FONTS = [
    "NotoSansSC-400.ttf",
    "NotoSansSC-500.ttf",
    "NotoSansSC-700.ttf",
    "NotoSansSC-900.ttf",
    "ZCOOLQingKeHuangYou.ttf",
]

full_dir = Path(sys.argv[1])
source = Path(sys.argv[2])
text = (source / "index.html").read_text(encoding="utf-8")
chars = "".join(sorted(set(text) | set(map(chr, range(32, 127)))))

with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
    f.write(chars)
for name in FONTS:
    subprocess.run(
        [
            "pyftsubset", str(full_dir / name),
            f"--text-file={f.name}",
            f"--output-file={source / 'fonts' / name}",
            "--layout-features=*",
        ],
        check=True,
    )

cmap = TTFont(source / "fonts" / "NotoSansSC-500.ttf").getBestCmap()
missing = sorted({c for c in text if ord(c) > 127 and ord(c) not in cmap})
print("missing:", missing or "none")
