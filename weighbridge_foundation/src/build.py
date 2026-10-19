# -*- coding: utf-8 -*-
"""生成汽车衡基础施工图：单张及合并 DXF、PDF 预览。

用法：python3 build.py [输出目录] [--only 结施-02]
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from ezdxf.addons.drawing import Frontend, RenderContext  # noqa: E402
from ezdxf.addons.drawing.config import (BackgroundPolicy, ColorPolicy,  # noqa: E402
                                         Configuration)
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # noqa: E402

import geom as G  # noqa: E402
from cadlib import A1, CAD, SHEET_SCALE, draw_frame, mask_texts  # noqa: E402

SHEETS = []


def register():
    from s01_notes import sheet_notes
    from s02_plan import sheet_plan
    from s03_sections import sheet_sections
    from s04_rebar import sheet_rebar
    from s05_details import sheet_details
    SHEETS[:] = [
        ("结施-01", "结构设计总说明", "—", sheet_notes),
        ("结施-02", "基础平面布置图", "1:50", sheet_plan),
        ("结施-03", "基础剖面图", "1:50、1:30", sheet_sections),
        ("结施-04", "基础配筋图及钢筋表", "1:50、1:30、1:20", sheet_rebar),
        ("结施-05", "预埋件及节点详图", "1:5~1:30", sheet_details),
    ]


GAP = 46000  # 合并文件中图框间距（模型单位）
DWG_FONT = "simfang.ttf"      # 交付 DXF 字体：仿宋
PREVIEW_FONT = "NotoSansCJK-Regular.ttc"


def build_sheet(number, title, scale, func, x0=0.0, cad=None, size=A1, mask=True):
    """绘制一张图（预览字体），并做文字遮罩。cad 给出时追加到该文件中。"""
    cad = cad or CAD(font=PREVIEW_FONT)
    sh = cad.sheet(x0, 0.0)
    draw_frame(sh, title, number, scale, G.PROJECT, G.SUBITEM, size=size)
    func(sh)
    if mask:
        mask_texts(cad.msp)
    return cad


def save_dxf(cad, path):
    """以交付字体（仿宋）保存 DXF；图形与预览完全一致，仅字体文件不同。"""
    style = cad.doc.styles.get("HZ")
    style.dxf.font = DWG_FONT
    cad.doc.saveas(path)
    style.dxf.font = PREVIEW_FONT


def render(cad, x0=0.0, png=None, pdf_pages=None, dpi=200, size=A1):
    fig = plt.figure(figsize=(size[0] / 25.4, size[1] / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ctx = RenderContext(cad.doc)
    cfg = Configuration(color_policy=ColorPolicy.BLACK,
                        background_policy=BackgroundPolicy.WHITE,
                        lineweight_scaling=1.0)
    Frontend(ctx, MatplotlibBackend(ax, adjust_figure=False), config=cfg).draw_layout(cad.msp, finalize=True)
    ax.set_xlim(x0, x0 + size[0] * SHEET_SCALE)
    ax.set_ylim(0, size[1] * SHEET_SCALE)
    ax.set_aspect("equal")
    ax.axis("off")
    if png:
        fig.savefig(png, dpi=dpi)
    if pdf_pages is not None:
        pdf_pages.savefig(fig)
    plt.close(fig)


def main():
    register()
    out = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "out"
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]
    os.makedirs(out, exist_ok=True)
    prev_dir = os.path.join(out, "preview")
    os.makedirs(prev_dir, exist_ok=True)

    if only in (None, "一张图"):
        build_combined(out, prev_dir)
        if only:
            return

    sel = [s for s in SHEETS if only is None or s[0] == only]
    pdf = None if only else PdfPages(os.path.join(out, "汽车衡基础施工图(预览).pdf"))
    for number, title, scale, func in sel:
        cad = build_sheet(number, title, scale, func)
        render(cad, png=os.path.join(prev_dir, f"{number}.png"), pdf_pages=pdf)
        save_dxf(cad, os.path.join(out, f"{number} {title}.dxf"))
        print("built", number)
    if pdf is not None:
        pdf.close()
    if only:
        return
    # 五张图并排的合并文件
    combined = CAD(font=PREVIEW_FONT)
    for i, (number, title, scale, func) in enumerate(SHEETS):
        build_sheet(number, title, scale, func, x0=i * GAP, cad=combined, mask=False)
    mask_texts(combined.msp)
    save_dxf(combined, os.path.join(out, "汽车衡基础施工图(全套).dxf"))
    print("saved dxf")


def build_combined(out, prev_dir):
    """全部内容合并为一张 A0 加长图。"""
    import combined as C
    cad = build_sheet("结施-01", "汽车衡基础施工图", "见各图", C.sheet_all, size=C.SIZE)
    with PdfPages(os.path.join(out, "汽车衡基础施工图(一张图).pdf")) as pdf:
        render(cad, png=os.path.join(prev_dir, "一张图.png"), pdf_pages=pdf, dpi=150, size=C.SIZE)
    save_dxf(cad, os.path.join(out, "汽车衡基础施工图(一张图).dxf"))
    print("saved combined")


if __name__ == "__main__":
    main()
