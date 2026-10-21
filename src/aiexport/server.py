"""MCP server: lets Claude (Desktop / Code / any MCP client) deliver designs as .ai files."""

from __future__ import annotations

import tempfile
from functools import partial
from pathlib import Path

import anyio

try:
    from mcp.server.mcpserver import Image, MCPServer as _Server
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server, Image
    from mcp.server.fastmcp.exceptions import ToolError

from .pipeline import ExportOptions
from .pipeline import export_ai as _export_ai
from .report import format_report, inspect_pdf, render_preview
from .tools import environment_report

INSTRUCTIONS = """\
把设计稿交付成客户要的 Adobe Illustrator .ai 文件。

工作流：
1. 用 SVG（首选）或 HTML 做设计。SVG 根元素写物理尺寸，例如名片
   <svg width="90mm" height="54mm" viewBox="0 0 900 540">；需要出血时按「成品 + 2×出血」做画布
   （如 96×60mm），再在 export_ai 里传 bleed_mm=3。HTML 用 CSS @page { size: 210mm 297mm; margin: 0 }。
2. 调用 export_ai 生成 .ai（默认 CMYK、文字转曲、黑色单 K）。
3. 看返回的预览图和检查报告，确认版面、尺寸、分辨率没问题再交付。

生成的是 PDF 兼容的 .ai：Illustrator 能直接打开，路径、渐变、透明度、图片都可编辑；
但不含 Illustrator 私有数据，所以没有图层，转曲后文字不能再改字。客户若要可改文字/分图层的原生 .ai，
需要在装有 Illustrator 的电脑上运行仓库里的 illustrator/save_as_native_ai.jsx。
"""

server = _Server("ai-export", instructions=INSTRUCTIONS)


def _preview(path: Path) -> Image:
    return Image(data=render_preview(path, max_px=1000), format="png")


async def _in_thread(fn, *args):
    """Run blocking work off the event loop; expected failures go back to the model as text."""
    try:
        return await anyio.to_thread.run_sync(partial(fn, *args))
    except (OSError, ValueError, RuntimeError) as exc:
        raise ToolError(str(exc)) from exc


@server.tool(structured_output=False)
async def export_ai(
    output_path: str,
    source_path: str | None = None,
    content: str | None = None,
    cmyk: bool = True,
    outline_text: bool = True,
    gray_to_k: bool = True,
    bleed_mm: float = 0.0,
    width_mm: float | None = None,
    height_mm: float | None = None,
    renderer: str = "auto",
    cmyk_profile: str | None = None,
    preview: bool = True,
) -> list:
    """Export an SVG / HTML / PDF design as an Illustrator-compatible .ai file (or a print .pdf).

    Args:
        output_path: Absolute path of the file to write; must end in .ai or .pdf. A multi-page
            source written as .ai becomes name-1.ai, name-2.ai, … (one artboard per file).
        source_path: Absolute path of an existing .svg, .html or .pdf file.
        content: Inline SVG or HTML markup, used instead of source_path. Relative links inside it
            do not resolve, so embed images as data: URIs or use absolute file paths.
        cmyk: Convert colours to CMYK for print (gradients stay editable vectors).
        outline_text: Convert text to outlines (转曲) so the file does not depend on fonts.
        gray_to_k: Print black and neutral greys with K ink only (black text = K100).
        bleed_mm: Bleed the artwork already includes on every side; marks the trim box.
        width_mm: Finished (trim) width in mm, excluding bleed. Content is scaled to fit;
            the aspect ratio must match. Must be given together with height_mm.
        height_mm: Finished (trim) height in mm, excluding bleed.
        renderer: auto | inkscape | chromium | cairosvg (SVG only; HTML always uses chromium).
        cmyk_profile: Path of a CMYK .icc profile; found automatically when omitted.
        preview: Also return a PNG preview of the first page.
    """
    if bool(source_path) == bool(content):
        raise ToolError("source_path 和 content 必须且只能提供一个")
    options = ExportOptions(
        cmyk=cmyk,
        outline_text=outline_text,
        gray_to_k=gray_to_k,
        bleed_mm=bleed_mm,
        width_mm=width_mm,
        height_mm=height_mm,
        renderer=renderer,
        cmyk_profile=cmyk_profile,
    )
    with tempfile.TemporaryDirectory(prefix="aiexport-src-") as tmp:
        if content:
            is_html = "<html" in content[:2000].lower() or "<!doctype html" in content[:200].lower()
            source = Path(tmp) / ("design.html" if is_html else "design.svg")
            source.write_text(content, encoding="utf-8")
        else:
            source = Path(source_path).expanduser()
        result = await _in_thread(_export_ai, source, output_path, options)

    lines = [f"已生成：{', '.join(str(p) for p in result.outputs)}", f"渲染器：{result.renderer}"]
    if result.color_profile:
        lines.append(f"CMYK 配置文件：{result.color_profile}")
    lines += [format_report(report) for report in result.reports]
    lines += [f"⚠ {warning}" for warning in result.warnings]
    out: list = ["\n".join(lines)]
    if preview:
        out.append(await _in_thread(_preview, result.outputs[0]))
    return out


@server.tool(structured_output=False)
async def inspect_ai(path: str, preview: bool = True) -> list:
    """Pre-flight check of an .ai / .pdf file: page and trim size, bleed, remaining fonts,
    colour spaces, image resolution and transparency, plus an optional PNG preview.

    Args:
        path: Absolute path of the .ai or .pdf file.
        preview: Also return a PNG preview of the first page.
    """
    file = Path(path).expanduser()
    out: list = [format_report(await _in_thread(inspect_pdf, file))]
    if preview:
        out.append(await _in_thread(_preview, file))
    return out


@server.tool()
async def check_environment() -> str:
    """Report which renderers (Inkscape / Chromium / cairosvg), Ghostscript and CMYK profile
    this machine has, with install hints for anything missing."""
    return await _in_thread(environment_report)


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
