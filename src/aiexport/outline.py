"""Converting text to outlines (转曲) with Ghostscript, keeping everything else vector."""

from __future__ import annotations

from pathlib import Path

import pikepdf

from . import tools
from .tools import ToolMissing


def pdf_has_fonts(path: Path) -> bool:
    with pikepdf.open(path) as pdf:
        return any(isinstance(obj, pikepdf.Dictionary) and obj.get("/Type") == "/Font" for obj in pdf.objects)


def outline_text(src: Path, dst: Path) -> None:
    gs = tools.find_ghostscript()
    if not gs:
        raise ToolMissing(
            "文字转曲需要 Ghostscript（macOS: brew install ghostscript；Windows: 从 ghostscript.com 安装；"
            "Linux: apt install ghostscript），或者用 Inkscape 渲染 SVG。也可以关闭转曲（outline_text=false）。"
        )
    tools.run(
        [
            gs, "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER",
            "-sDEVICE=pdfwrite",
            "-dNoOutputFonts",  # glyphs become filled paths
            "-dCompatibilityLevel=1.7",
            "-dAutoRotatePages=/None",
            # Keep placed images untouched: no downsampling, no lossy re-encoding.
            "-dDownsampleColorImages=false", "-dDownsampleGrayImages=false", "-dDownsampleMonoImages=false",
            "-dAutoFilterColorImages=false", "-dAutoFilterGrayImages=false",
            "-dColorImageFilter=/FlateEncode", "-dGrayImageFilter=/FlateEncode",
            f"-sOutputFile={dst}",
            str(src),
        ],
        what="Ghostscript 转曲",
    )
