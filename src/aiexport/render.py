"""Rendering SVG / HTML sources to a vector PDF."""

from __future__ import annotations

import re
import shutil
import threading
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from . import tools
from .tools import ToolMissing

SVG_SUFFIXES = {".svg", ".svgz"}
HTML_SUFFIXES = {".html", ".htm", ".xhtml"}
PDF_SUFFIXES = {".pdf", ".ai"}  # a PDF-compatible .ai is itself a PDF

_UNIT_MM = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72, "pc": 25.4 / 6, "px": 25.4 / 96, "": 25.4 / 96}
_PAPER_MM = {
    "a3": (297, 420), "a4": (210, 297), "a5": (148, 210), "a6": (105, 148),
    "b4": (250, 353), "b5": (176, 250), "letter": (215.9, 279.4), "legal": (215.9, 355.6), "ledger": (279.4, 431.8),
}
# Reads the first CSS `@page { size: … }` so Chromium's rounded page can be snapped back to it.
_PAGE_SIZE_JS = """() => {
  for (const sheet of document.styleSheets) {
    let rules; try { rules = sheet.cssRules } catch (e) { continue }
    for (const rule of rules) if (rule.type === CSSRule.PAGE_RULE && rule.style.size) return rule.style.size
  }
  return null
}"""


def _length_mm(value: str | None) -> float | None:
    if not value:
        return None
    match = re.fullmatch(r"\s*([0-9.]+(?:e[-+]?\d+)?)\s*(mm|cm|in|pt|pc|px|)\s*", value, re.I)
    return float(match.group(1)) * _UNIT_MM[match.group(2).lower()] if match else None


def css_page_size_mm(value: str | None) -> tuple[float, float] | None:
    """Parse a CSS page size such as "148mm 210mm", "A4" or "A4 landscape"."""
    words = (value or "").lower().split()
    landscape = "landscape" in words
    words = [w for w in words if w not in ("portrait", "landscape")]
    size = None
    if len(words) == 1 and words[0] in _PAPER_MM:
        size = _PAPER_MM[words[0]]
    elif len(words) in (1, 2) and all(_length_mm(w) for w in words):
        size = (_length_mm(words[0]), _length_mm(words[-1]))
    if size and landscape:
        size = (max(size), min(size))
    return size


def svg_size_mm(path: Path) -> tuple[float, float] | None:
    """Physical size of an SVG from its root width/height (falling back to the viewBox in px)."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None
    width, height = _length_mm(root.get("width")), _length_mm(root.get("height"))
    if width and height:
        return width, height
    view_box = (root.get("viewBox") or "").replace(",", " ").split()
    if len(view_box) == 4:
        vb_w, vb_h = float(view_box[2]), float(view_box[3])
        if width:
            return width, width * vb_h / vb_w
        if height:
            return height * vb_w / vb_h, height
        return vb_w * _UNIT_MM["px"], vb_h * _UNIT_MM["px"]
    return None


@dataclass
class Rendered:
    renderer: str
    text_outlined: bool = False
    # Intended page size when the renderer rounds it (Chromium snaps pages to whole CSS pixels).
    page_size_mm: tuple[float, float] | None = None


def render_to_pdf(
    src: Path,
    out: Path,
    *,
    renderer: str = "auto",
    outline_text: bool = False,
    page_size_mm: tuple[float, float] | None = None,
) -> Rendered:
    """Render ``src`` into ``out``."""
    suffix = src.suffix.lower()
    if suffix in PDF_SUFFIXES:
        shutil.copyfile(src, out)
        return Rendered("pdf")
    if suffix in HTML_SUFFIXES:
        if renderer not in ("auto", "chromium"):
            raise ValueError("HTML 只能用 chromium 渲染")
        return Rendered("chromium", page_size_mm=_render_chromium(src, out, page_size_mm=page_size_mm, html=True))
    if suffix not in SVG_SUFFIXES:
        raise ValueError(f"不支持的源文件类型：{src.suffix}（支持 .svg / .html / .pdf）")

    if renderer == "inkscape" or (renderer == "auto" and tools.find_inkscape()):
        _render_inkscape(src, out, outline_text=outline_text)
        return Rendered("inkscape", text_outlined=outline_text)
    if renderer == "auto":
        errors = []
        for name, fn in (("chromium", _render_chromium), ("cairosvg", _render_cairosvg)):
            try:
                return Rendered(name, page_size_mm=fn(src, out))
            except ToolMissing as exc:
                errors.append(str(exc))
        raise ToolMissing(
            "没有可用的 SVG 渲染器。请安装 Inkscape 1.x（推荐），或 `pip install 'aiexport[html]'` 并装好 Chrome，"
            "或 `pip install 'aiexport[cairo]'`。\n" + "\n".join(errors)
        )
    if renderer == "chromium":
        return Rendered("chromium", page_size_mm=_render_chromium(src, out))
    if renderer == "cairosvg":
        _render_cairosvg(src, out)
        return Rendered("cairosvg")
    raise ValueError(f"未知渲染器：{renderer}（可选 auto / inkscape / chromium / cairosvg）")


def _render_inkscape(src: Path, out: Path, *, outline_text: bool) -> None:
    exe = tools.find_inkscape()
    if not exe:
        raise ToolMissing("未找到 Inkscape 1.x（可设置环境变量 AIEXPORT_INKSCAPE 指定路径）")
    cmd = [exe, str(src), "--export-type=pdf", f"--export-filename={out}", "--export-area-page", "--export-pdf-version=1.5"]
    if outline_text:
        cmd.append("--export-text-to-path")
    tools.run(cmd, what="Inkscape 渲染")
    if not out.exists():
        raise RuntimeError("Inkscape 没有生成 PDF")


def _render_cairosvg(src: Path, out: Path) -> None:
    if not tools.cairosvg_available():
        raise ToolMissing("cairosvg 不可用（pip install cairosvg，并需要系统里有 cairo 库）")
    import cairosvg

    cairosvg.svg2pdf(url=str(src), write_to=str(out))


def _render_chromium(
    src: Path, out: Path, *, page_size_mm: tuple[float, float] | None = None, html: bool = False
) -> tuple[float, float] | None:
    """Print ``src`` to PDF; returns the intended page size in mm when known."""
    if not tools.playwright_available():
        raise ToolMissing("未安装 playwright（pip install playwright）")
    # The sync Playwright API refuses to run inside an asyncio loop (the MCP server has one),
    # so the browser always gets a thread of its own.
    result: list = []
    errors: list[BaseException] = []

    def work() -> None:
        try:
            result.append(_chromium_pdf(src, out, page_size_mm=page_size_mm, html=html))
        except BaseException as exc:  # re-raised in the caller's thread
            errors.append(exc)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join()
    if errors:
        raise errors[0]
    return result[0]


def _chromium_pdf(src: Path, out: Path, *, page_size_mm, html: bool) -> tuple[float, float] | None:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser, errors = None, []
        for options in tools.chromium_launch_options():
            try:
                browser = p.chromium.launch(**options)
                break
            except PlaywrightError as exc:
                errors.append(str(exc).splitlines()[0])
        if browser is None:
            raise ToolMissing(
                "无法启动 Chromium/Chrome/Edge（可运行 `playwright install chromium`，"
                "或设置 AIEXPORT_CHROMIUM 指向浏览器可执行文件）：" + "；".join(errors)
            )
        try:
            page = browser.new_page()
            pdf_options = {"path": str(out), "print_background": True, "margin": dict.fromkeys(("top", "right", "bottom", "left"), "0")}
            if html:
                page.goto(src.as_uri(), wait_until="networkidle")
                if page_size_mm:
                    size = page_size_mm
                    pdf_options.update(width=f"{size[0]}mm", height=f"{size[1]}mm")
                else:
                    size = css_page_size_mm(page.evaluate(_PAGE_SIZE_JS))
                    pdf_options["prefer_css_page_size"] = True
            else:
                size = svg_size_mm(src)
                if not size:
                    raise ValueError("SVG 缺少 width/height/viewBox，无法确定尺寸")
                wrapper = out.with_suffix(".html")
                wrapper.write_text(_svg_wrapper(src, size), encoding="utf-8")
                page.goto(wrapper.as_uri(), wait_until="networkidle")
                pdf_options.update(prefer_css_page_size=True, page_ranges="1")
            page.evaluate("document.fonts.ready")
            page.pdf(**pdf_options)
        finally:
            browser.close()
    return size


def _svg_wrapper(src: Path, size: tuple[float, float]) -> str:
    markup = src.read_text(encoding="utf-8")
    markup = re.sub(r"<\?xml[^>]*\?>|<!DOCTYPE[^>]*>", "", markup, flags=re.I)
    width, height = size
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<base href="{src.parent.as_uri()}/">'
        f"<style>@page{{size:{width}mm {height}mm;margin:0}}html,body{{margin:0;padding:0}}"
        f"body>svg{{display:block;width:{width}mm;height:{height}mm}}</style>"
        f"</head><body>{markup}</body></html>"
    )
