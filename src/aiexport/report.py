"""Pre-flight report for a finished .ai / .pdf: size, boxes, fonts, colour spaces, image resolution."""

from __future__ import annotations

import io
import math
from pathlib import Path

import pikepdf
from pikepdf import ContentStreamInlineImage, Dictionary, Name

from .cmyk import CMYK, GRAY, PATTERN, RGB, SPOT, colorspace_kind

PT_TO_MM = 25.4 / 72
MIN_PRINT_PPI = 300
_KIND_LABEL = {RGB: "RGB", CMYK: "CMYK", GRAY: "灰度", SPOT: "专色", "indexed": "索引色", "lab": "Lab", "other": "其他"}


def _mul(m, n):
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (a * a2 + b * c2, a * b2 + b * d2, c * a2 + d * c2, c * b2 + d * d2, e * a2 + f * c2 + e2, e * b2 + f * d2 + f2)


def _box_mm(box) -> list[float]:
    x0, y0, x1, y1 = (float(v) for v in box)
    return [round(abs(x1 - x0) * PT_TO_MM, 2), round(abs(y1 - y0) * PT_TO_MM, 2)]


class _Walker:
    def __init__(self):
        self.kinds: set[str] = set()
        self.images: list[dict] = []
        self.transparency = False
        self._active: set[tuple[int, int]] = set()

    def walk(self, obj, resources, ctm) -> None:
        key = obj.objgen if obj.is_indirect else None
        if key in self._active:
            return
        if key:
            self._active.add(key)
        stack = []
        try:
            instructions = pikepdf.parse_content_stream(obj)
        except pikepdf.PdfError:
            instructions = []
        for inst in instructions:
            if isinstance(inst, ContentStreamInlineImage):
                continue
            op, ops = str(inst.operator), inst.operands
            if op == "q":
                stack.append(ctm)
            elif op == "Q" and stack:
                ctm = stack.pop()
            elif op == "cm" and len(ops) == 6:
                ctm = _mul(tuple(float(v) for v in ops), ctm)
            elif op in ("rg", "RG"):
                self.kinds.add(RGB)
            elif op in ("k", "K"):
                self.kinds.add(CMYK)
            elif op in ("g", "G"):
                self.kinds.add(GRAY)
            elif op in ("cs", "CS") and ops:
                kind = colorspace_kind(ops[0], resources)
                if kind != PATTERN:
                    self.kinds.add(kind)
            elif op == "sh" and ops:
                shading = self._lookup(resources, "/Shading", ops[0])
                if shading is not None:
                    self.kinds.add(colorspace_kind(shading.get("/ColorSpace")))
            elif op in ("scn", "SCN") and ops and isinstance(ops[-1], Name):
                pattern = self._lookup(resources, "/Pattern", ops[-1])
                if pattern is not None and pattern.get("/PatternType") == 2:
                    self.kinds.add(colorspace_kind(pattern.Shading.get("/ColorSpace")))
                elif pattern is not None:
                    self.walk(pattern, pattern.get("/Resources"), ctm)
            elif op == "gs" and ops:
                state = self._lookup(resources, "/ExtGState", ops[0])
                if state is not None and (
                    float(state.get("/ca", 1)) < 1 or float(state.get("/CA", 1)) < 1 or str(state.get("/SMask", "/None")) != "/None"
                ):
                    self.transparency = True
            elif op == "Do" and ops:
                xobj = self._lookup(resources, "/XObject", ops[0])
                if xobj is None:
                    continue
                if xobj.get("/Subtype") == "/Image":
                    self._image(xobj, ctm)
                elif xobj.get("/Subtype") == "/Form":
                    matrix = tuple(float(v) for v in xobj.get("/Matrix", [1, 0, 0, 1, 0, 0]))
                    self.walk(xobj, xobj.get("/Resources", resources), _mul(matrix, ctm))
        if key:
            self._active.discard(key)

    @staticmethod
    def _lookup(resources, category, name):
        if resources is None or category not in resources:
            return None
        return resources[category].get(name)

    def _image(self, image, ctm) -> None:
        if image.get("/ImageMask"):
            return
        kind = colorspace_kind(image.get("/ColorSpace"))
        self.kinds.add(kind)
        width_px, height_px = int(image.Width), int(image.Height)
        width_in = math.hypot(ctm[0], ctm[1]) / 72
        height_in = math.hypot(ctm[2], ctm[3]) / 72
        ppi = min(width_px / width_in, height_px / height_in) if width_in and height_in else 0
        self.images.append({"pixels": f"{width_px}x{height_px}", "color": _KIND_LABEL.get(kind, kind), "ppi": round(ppi)})


def inspect_pdf(path: str | Path) -> dict:
    path = Path(path)
    with pikepdf.open(path) as pdf:
        fonts = sorted({
            str(obj.get("/BaseFont", "?")).lstrip("/")
            for obj in pdf.objects
            if isinstance(obj, Dictionary) and obj.get("/Type") == "/Font"
            and obj.get("/Subtype") not in ("/CIDFontType0", "/CIDFontType2")  # descendants of a Type0 font
        })
        pages, walker = [], _Walker()
        for page in pdf.pages:
            walker.walk(page.obj, page.obj.get("/Resources"), (1, 0, 0, 1, 0, 0))
            if (group := page.obj.get("/Group")) is not None and group.get("/S") == "/Transparency":
                walker.transparency = True
            media = page.obj.MediaBox
            info = {"size_mm": _box_mm(media)}
            if "/TrimBox" in page.obj:
                trim = [float(v) for v in page.obj.TrimBox]
                info["trim_mm"] = _box_mm(trim)
                info["bleed_mm"] = round((trim[0] - float(media[0])) * PT_TO_MM, 2)
            pages.append(info)
        version = pdf.pdf_version
    kinds = sorted(_KIND_LABEL.get(k, k) for k in walker.kinds)
    return {
        "file": str(path),
        "bytes": path.stat().st_size,
        "pdf_version": version,
        "pages": pages,
        "fonts": fonts,
        "text_outlined": not fonts,
        "color_spaces": kinds,
        "images": walker.images,
        "low_res_images": sum(1 for img in walker.images if img["ppi"] < MIN_PRINT_PPI),
        "transparency": walker.transparency,
    }


def warnings_for(report: dict, *, expect_cmyk: bool, expect_outlines: bool) -> list[str]:
    warnings = []
    if expect_outlines and report["fonts"]:
        warnings.append(f"仍有字体未转曲：{', '.join(report['fonts'])}")
    if expect_cmyk and "RGB" in report["color_spaces"]:
        warnings.append("仍有 RGB 颜色残留（见上方转换提示）")
    if report["low_res_images"]:
        worst = min(img["ppi"] for img in report["images"])
        warnings.append(f"{report['low_res_images']} 张图片印刷分辨率低于 {MIN_PRINT_PPI} ppi（最低 {worst} ppi）")
    return warnings


def format_report(report: dict) -> str:
    lines = [f"文件：{report['file']}（{report['bytes'] / 1024:.0f} KB，PDF {report['pdf_version']}）"]
    for i, page in enumerate(report["pages"], 1):
        line = f"第 {i} 页：{page['size_mm'][0]} × {page['size_mm'][1]} mm"
        if "trim_mm" in page:
            line += f"（成品 {page['trim_mm'][0]} × {page['trim_mm'][1]} mm，出血 {page['bleed_mm']} mm）"
        lines.append(line)
    lines.append("文字：" + ("已全部转曲" if report["text_outlined"] else "保留字体 " + ", ".join(report["fonts"])))
    lines.append("颜色：" + (" / ".join(report["color_spaces"]) or "无"))
    if report["images"]:
        lines.append("图片：" + "；".join(f"{img['pixels']} {img['color']} {img['ppi']}ppi" for img in report["images"]))
    lines.append("透明效果：" + ("有" if report["transparency"] else "无"))
    return "\n".join(lines)


def render_preview(path: str | Path, *, page: int = 0, max_px: int = 1200) -> bytes:
    """PNG preview of one page (for a quick visual check)."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(path))
    try:
        pg = doc[page]
        width, height = pg.get_size()
        image = pg.render(scale=max_px / max(width, height)).to_pil()
    finally:
        doc.close()
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()
