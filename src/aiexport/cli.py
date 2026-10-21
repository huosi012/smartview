"""Command line: aiexport convert / inspect / doctor."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .pipeline import ExportOptions, export_ai
from .report import format_report, inspect_pdf, render_preview
from .tools import environment_report


def _size(value: str) -> tuple[float, float]:
    match = re.fullmatch(r"\s*([0-9.]+)\s*[x×*]\s*([0-9.]+)\s*(mm)?\s*", value, re.I)
    if not match:
        raise argparse.ArgumentTypeError("尺寸格式应为 宽x高（毫米），例如 90x54")
    return float(match.group(1)), float(match.group(2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aiexport", description="把 SVG / HTML / PDF 设计稿导出为 Illustrator 可编辑的 .ai 文件")
    sub = parser.add_subparsers(dest="command", required=True)

    convert = sub.add_parser("convert", help="导出 .ai（或印刷用 .pdf）")
    convert.add_argument("source", type=Path, help="源文件：.svg / .html / .pdf")
    convert.add_argument("-o", "--output", type=Path, help="输出路径，默认与源文件同名的 .ai（源文件本身是 .ai 时加 -print 后缀）")
    convert.add_argument("--rgb", action="store_true", help="保留 RGB（默认转 CMYK）")
    convert.add_argument("--keep-text", action="store_true", help="不转曲，保留字体（默认转曲）")
    convert.add_argument("--rich-black", action="store_true", help="黑/灰色也按 ICC 换算成四色（默认单 K）")
    convert.add_argument("--bleed", type=float, default=0.0, metavar="MM", help="设计稿四周已包含的出血（毫米），用于标记成品线")
    convert.add_argument("--size", type=_size, metavar="WxH", help="成品尺寸（毫米，不含出血），例如 90x54；内容等比缩放到该尺寸")
    convert.add_argument("--renderer", default="auto", choices=["auto", "inkscape", "chromium", "cairosvg"])
    convert.add_argument("--profile", help="CMYK ICC 配置文件路径（默认自动查找）")
    convert.add_argument("--title", help="文档标题")
    convert.add_argument("--preview", type=Path, metavar="PNG", help="另存一张预览图")

    inspect = sub.add_parser("inspect", help="检查 .ai/.pdf：尺寸、出血、字体、色彩、图片分辨率")
    inspect.add_argument("file", type=Path)
    inspect.add_argument("--preview", type=Path, metavar="PNG", help="另存一张预览图")

    sub.add_parser("doctor", help="检查本机可用的渲染器、Ghostscript 和 CMYK 配置文件")

    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            print(environment_report())
        elif args.command == "inspect":
            print(format_report(inspect_pdf(args.file)))
            if args.preview:
                args.preview.write_bytes(render_preview(args.file))
        else:
            options = ExportOptions(
                cmyk=not args.rgb,
                outline_text=not args.keep_text,
                gray_to_k=not args.rich_black,
                bleed_mm=args.bleed,
                width_mm=args.size[0] if args.size else None,
                height_mm=args.size[1] if args.size else None,
                renderer=args.renderer,
                cmyk_profile=args.profile,
                title=args.title,
            )
            output = args.output or args.source.with_suffix(".ai")
            if not args.output and output.resolve() == args.source.resolve():
                output = args.source.with_name(f"{args.source.stem}-print.ai")  # never overwrite the source
            result = export_ai(args.source, output, options)
            print(f"渲染器：{result.renderer}" + (f"；CMYK 配置文件：{result.color_profile}" if result.color_profile else ""))
            for report in result.reports:
                print(format_report(report))
            for warning in result.warnings:
                print(f"⚠ {warning}", file=sys.stderr)
            if args.preview:
                args.preview.write_bytes(render_preview(result.outputs[0]))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
