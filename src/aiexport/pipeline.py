"""SVG / HTML / PDF → Illustrator-compatible .ai.

Since Illustrator 9 an .ai file is a PDF with Illustrator's private data appended; when that
private part is absent Illustrator opens the PDF part, with vectors, gradients, transparency
and images all editable. That is what is produced here, prepared the way print clients ask
for it: CMYK colours, text converted to outlines (转曲), trim and bleed boxes marked.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pikepdf
from pikepdf import Array, Name

from . import __version__
from .cmyk import ColorConverter, PdfCmykConverter
from .outline import outline_text, pdf_has_fonts
from .render import HTML_SUFFIXES, render_to_pdf
from .report import inspect_pdf, warnings_for

MM_TO_PT = 72 / 25.4
_BOXES = ("/CropBox", "/BleedBox", "/TrimBox", "/ArtBox")


@dataclass
class ExportOptions:
    cmyk: bool = True
    outline_text: bool = True
    gray_to_k: bool = True
    bleed_mm: float = 0.0
    # Finished (trim) size; artwork is scaled to it (plus bleed). For HTML it sets the page size.
    width_mm: float | None = None
    height_mm: float | None = None
    renderer: str = "auto"
    cmyk_profile: str | None = None
    title: str | None = None


@dataclass
class ExportResult:
    outputs: list[Path]
    renderer: str
    color_profile: str | None
    reports: list[dict]
    warnings: list[str] = field(default_factory=list)


def export_ai(source: str | Path, output: str | Path, options: ExportOptions | None = None) -> ExportResult:
    opts = options or ExportOptions()
    src = Path(source).expanduser().resolve()
    out = Path(output).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(f"找不到源文件：{src}")
    if out.suffix.lower() not in (".ai", ".pdf"):
        raise ValueError("输出文件扩展名必须是 .ai 或 .pdf")
    if (opts.width_mm is None) != (opts.height_mm is None):
        raise ValueError("width_mm 和 height_mm 需要同时提供")
    if opts.bleed_mm < 0:
        raise ValueError("bleed_mm 不能为负数")
    out.parent.mkdir(parents=True, exist_ok=True)

    size = None
    if opts.width_mm is not None:
        size = (opts.width_mm + 2 * opts.bleed_mm, opts.height_mm + 2 * opts.bleed_mm)
    is_html = src.suffix.lower() in HTML_SUFFIXES
    warnings: list[str] = []
    profile = None

    with tempfile.TemporaryDirectory(prefix="aiexport-") as tmp:
        current = Path(tmp) / "render.pdf"
        rendered = render_to_pdf(
            src, current, renderer=opts.renderer, outline_text=opts.outline_text, page_size_mm=size if is_html else None
        )
        boxes = _read_boxes(current)
        if opts.outline_text and not rendered.text_outlined and pdf_has_fonts(current):
            outlined_pdf = Path(tmp) / "outlined.pdf"
            outline_text(current, outlined_pdf)
            current = outlined_pdf

        size = size or rendered.page_size_mm
        with pikepdf.open(current) as pdf:
            _restore_boxes(pdf, boxes)
            if size:
                _fit_pages(pdf, *size)
            if opts.cmyk:
                colors = ColorConverter(opts.cmyk_profile, gray_to_k=opts.gray_to_k)
                profile = colors.description
                converter = PdfCmykConverter(colors)
                converter.convert(pdf)
                warnings += converter.warnings
            if opts.bleed_mm:
                _mark_bleed(pdf, opts.bleed_mm)
            outputs = _save(pdf, out, opts.title or out.stem)

    reports = [inspect_pdf(path) for path in outputs]
    for report in reports:
        warnings += [w for w in warnings_for(report, expect_cmyk=opts.cmyk, expect_outlines=opts.outline_text) if w not in warnings]
    return ExportResult(outputs, rendered.renderer, profile, reports, warnings)


def _relative_boxes(page) -> dict[str, list[float]]:
    x0, y0 = float(page.MediaBox[0]), float(page.MediaBox[1])
    return {
        key: [float(v) - (x0 if i % 2 == 0 else y0) for i, v in enumerate(page[key])]
        for key in _BOXES
        if key in page
    }


def _read_boxes(path: Path) -> list[dict[str, list[float]]]:
    """Trim/bleed boxes relative to the media box (Ghostscript drops them and may move the origin)."""
    with pikepdf.open(path) as pdf:
        return [_relative_boxes(page.obj) for page in pdf.pages]


def _restore_boxes(pdf: pikepdf.Pdf, boxes: list[dict[str, list[float]]]) -> None:
    for page, page_boxes in zip(pdf.pages, boxes):
        x0, y0 = float(page.obj.MediaBox[0]), float(page.obj.MediaBox[1])
        for key, box in page_boxes.items():
            page.obj[key] = Array([v + (x0 if i % 2 == 0 else y0) for i, v in enumerate(box)])


def _fit_pages(pdf: pikepdf.Pdf, width_mm: float, height_mm: float) -> None:
    """Scale every page to exactly width × height mm (the aspect ratio must already match)."""
    target_w, target_h = width_mm * MM_TO_PT, height_mm * MM_TO_PT
    for page in pdf.pages:
        x0, y0, x1, y1 = (float(v) for v in page.obj.MediaBox)
        sx, sy = target_w / (x1 - x0), target_h / (y1 - y0)
        if abs(sx / sy - 1) > 0.01:
            raise ValueError(
                f"原稿比例 {(x1 - x0) / MM_TO_PT:.1f}×{(y1 - y0) / MM_TO_PT:.1f}mm 与目标 {width_mm:g}×{height_mm:g}mm"
                "（含出血）不一致，请先在设计稿里改好比例"
            )
        if abs(sx - 1) < 1e-4 and abs(sy - 1) < 1e-4 and x0 == y0 == 0:
            continue
        boxes = _relative_boxes(page.obj)
        page.contents_add(f"q {sx:.6f} 0 0 {sy:.6f} {-x0 * sx:.4f} {-y0 * sy:.4f} cm\n".encode(), prepend=True)
        page.contents_add(b"\nQ")
        page.obj.MediaBox = Array([0, 0, round(target_w, 4), round(target_h, 4)])
        for key, (bx0, by0, bx1, by1) in boxes.items():
            page.obj[key] = Array([round(bx0 * sx, 4), round(by0 * sy, 4), round(bx1 * sx, 4), round(by1 * sy, 4)])


def _mark_bleed(pdf: pikepdf.Pdf, bleed_mm: float) -> None:
    """The artwork already includes the bleed: the trim box sits bleed_mm inside the media box."""
    bleed = bleed_mm * MM_TO_PT
    for page in pdf.pages:
        x0, y0, x1, y1 = (float(v) for v in page.obj.MediaBox)
        if x1 - x0 <= 2 * bleed or y1 - y0 <= 2 * bleed:
            raise ValueError("出血尺寸大于页面")
        for key in _BOXES:
            if key in page.obj:
                del page.obj[key]
        page.obj.BleedBox = Array([x0, y0, x1, y1])
        page.obj.TrimBox = Array([round(x0 + bleed, 4), round(y0 + bleed, 4), round(x1 - bleed, 4), round(y1 - bleed, 4)])


def _save(pdf: pikepdf.Pdf, out: Path, title: str) -> list[Path]:
    """Write the file. Illustrator opens one page per document, so a multi-page .ai is split."""
    if out.suffix.lower() == ".pdf" or len(pdf.pages) == 1:
        _write(pdf, out, title)
        return [out]
    outputs = []
    for i, page in enumerate(pdf.pages, 1):
        single = pikepdf.new()
        single.pages.append(page)
        path = out.with_name(f"{out.stem}-{i}{out.suffix}")
        _write(single, path, f"{title} {i}")
        outputs.append(path)
    return outputs


def _write(pdf: pikepdf.Pdf, path: Path, title: str) -> None:
    is_ai = path.suffix.lower() == ".ai"
    with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
        meta["dc:title"] = title
        meta["dc:format"] = "application/vnd.adobe.illustrator" if is_ai else "application/pdf"
        meta["xmp:CreatorTool"] = f"aiexport {__version__}"
    pdf.docinfo[Name.Title] = title
    pdf.docinfo[Name.Creator] = f"aiexport {__version__}"
    pdf.save(path, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.disable, min_version="1.6")
