import zlib
from pathlib import Path

import pikepdf
import pytest
from pikepdf import Dictionary, Name

from aiexport import ExportOptions, export_ai
from aiexport.cmyk import ColorConverter, PdfCmykConverter
from aiexport.render import css_page_size_mm, svg_size_mm
from aiexport.report import inspect_pdf
from aiexport.tools import ToolMissing, cairosvg_available, find_ghostscript, find_inkscape

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "business-card.svg"
needs_svg_renderer = pytest.mark.skipif(
    not (find_inkscape() or (cairosvg_available() and find_ghostscript())),
    reason="needs Inkscape, or cairosvg + Ghostscript",
)


def _rgb_test_pdf(path: Path) -> None:
    """One page using every kind of RGB colour the converter rewrites."""
    pdf = pikepdf.new()
    image = pdf.make_stream(
        zlib.compress(bytes([255, 0, 0, 0, 0, 255]) * 2), Filter=Name.FlateDecode,
        Type=Name.XObject, Subtype=Name.Image, Width=2, Height=2, ColorSpace=Name.DeviceRGB, BitsPerComponent=8,
    )
    stops = [Dictionary(FunctionType=2, Domain=[0, 1], N=1, C0=[1, 0, 0], C1=[0, 1, 0]),
             Dictionary(FunctionType=2, Domain=[0, 1], N=1, C0=[0, 1, 0], C1=[0, 0, 1])]
    shading = Dictionary(
        ShadingType=2, ColorSpace=Name.DeviceRGB, Coords=[0, 0, 100, 0],
        Function=Dictionary(FunctionType=3, Domain=[0, 1], Functions=stops, Bounds=[0.5], Encode=[0, 1, 0, 1]),
    )
    form = pdf.make_stream(
        b"0 0 1 RG 0.5 0.5 0.5 rg 0 0 5 5 re B", Type=Name.XObject, Subtype=Name.Form, BBox=[0, 0, 10, 10],
        Group=Dictionary(S=Name.Transparency, CS=Name.DeviceRGB),
    )
    page = pdf.add_blank_page(page_size=(100, 100))
    page.obj.Resources = Dictionary(XObject=Dictionary(Im0=image, Fx0=form), Shading=Dictionary(Sh0=shading))
    page.obj.Contents = pdf.make_stream(
        b"1 0 0 rg 0 0 10 10 re f 0 g 10 10 5 5 re f /DeviceRGB cs 0 0 1 sc 20 20 5 5 re f "
        b"q 20 0 0 20 40 40 cm /Im0 Do Q /Fx0 Do /Sh0 sh"
    )
    pdf.save(path)


def test_rgb_pdf_becomes_cmyk_with_vector_gradients(tmp_path):
    src = tmp_path / "rgb.pdf"
    _rgb_test_pdf(src)
    with pikepdf.open(src, allow_overwriting_input=True) as pdf:
        PdfCmykConverter(ColorConverter()).convert(pdf)
        pdf.save(src)

    with pikepdf.open(src) as pdf:
        page = pdf.pages[0]
        ops = [(str(i.operator), [float(v) if not isinstance(v, Name) else str(v) for v in i.operands])
               for i in pikepdf.parse_content_stream(page)]
        names = {op for op, _ in ops}
        assert not names & {"rg", "RG", "g", "G"}
        assert ("k", [0.0, 0.0, 0.0, 1.0]) in ops  # 0 g → K100
        assert ("cs", ["/DeviceCMYK"]) in ops
        assert all(len(args) == 4 for op, args in ops if op in ("k", "sc"))

        res = page.obj.Resources
        shading = res.Shading.Sh0
        assert shading.ColorSpace == Name.DeviceCMYK
        assert shading.ShadingType == 2  # still a vector gradient
        assert all(len(f.C0) == 4 and len(f.C1) == 4 for f in shading.Function.Functions)

        image = res.XObject.Im0
        assert image.ColorSpace == Name.DeviceCMYK
        assert len(image.read_bytes()) == 2 * 2 * 4

        form = res.XObject.Fx0
        assert form.Group.CS == Name.DeviceCMYK
        form_ops = [(str(i.operator), [float(v) for v in i.operands]) for i in pikepdf.parse_content_stream(form)]
        assert ("k", [0.0, 0.0, 0.0, 0.498]) in form_ops  # neutral grey → K only


def test_gray_to_k_switch():
    assert ColorConverter(gray_to_k=True).rgb(0, 0, 0) == (0.0, 0.0, 0.0, 1.0)
    rich = ColorConverter(gray_to_k=False).rgb(0, 0, 0)
    if ColorConverter().profile_path:
        assert rich[0] > 0.3 and rich[3] > 0.5  # ICC rich black


def test_size_parsing(tmp_path):
    svg = tmp_path / "a.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="96mm" height="60mm" viewBox="0 0 960 600"/>')
    assert svg_size_mm(svg) == (96.0, 60.0)
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540"/>')
    assert svg_size_mm(svg) == pytest.approx((254.0, 142.875))
    assert css_page_size_mm("A4 landscape") == (297, 210)
    assert css_page_size_mm("148mm 210mm") == (148.0, 210.0)
    assert css_page_size_mm("auto") is None


def test_pdf_input_scaled_to_size_and_bleed(tmp_path):
    src = tmp_path / "in.pdf"
    _rgb_test_pdf(src)  # 100 × 100 pt
    out = tmp_path / "out.ai"
    result = export_ai(src, out, ExportOptions(width_mm=50, height_mm=50, bleed_mm=2, outline_text=False))
    page = result.reports[0]["pages"][0]
    assert page["size_mm"] == [54.0, 54.0]
    assert page["trim_mm"] == [50.0, 50.0]
    assert page["bleed_mm"] == 2.0
    assert result.reports[0]["color_spaces"] == ["CMYK"]
    assert out.read_bytes().startswith(b"%PDF")

    with pytest.raises(ValueError):
        export_ai(src, tmp_path / "bad.ai", ExportOptions(width_mm=90, height_mm=54, outline_text=False))


@needs_svg_renderer
def test_example_card_to_ai(tmp_path):
    out = tmp_path / "card.ai"
    result = export_ai(EXAMPLE, out, ExportOptions(bleed_mm=3))
    assert result.outputs == [out]
    report = inspect_pdf(out)
    assert report["text_outlined"]
    assert report["color_spaces"] == ["CMYK"]
    assert report["pages"][0]["size_mm"] == [96.0, 60.0]
    assert report["pages"][0]["trim_mm"] == [90.0, 54.0]
    with pikepdf.open(out) as pdf:
        assert b"application/vnd.adobe.illustrator" in pdf.Root.Metadata.read_bytes()


def test_html_multi_page_splits(tmp_path):
    html = tmp_path / "flyer.html"
    html.write_text(
        '<!doctype html><meta charset="utf-8"><style>@page{size:A5;margin:0}body{margin:0}'
        "section{height:210mm;page-break-after:always;background:linear-gradient(#0f4c81,#e9c46a)}</style>"
        "<section>一</section><section>二</section>",
        encoding="utf-8",
    )
    try:
        result = export_ai(html, tmp_path / "flyer.ai", ExportOptions(outline_text=bool(find_ghostscript())))
    except ToolMissing as exc:
        pytest.skip(str(exc))
    assert [p.name for p in result.outputs] == ["flyer-1.ai", "flyer-2.ai"]
    assert result.reports[0]["pages"][0]["size_mm"] == [148.0, 210.0]
    assert result.reports[0]["color_spaces"] == ["CMYK"]


def test_mcp_server_exposes_tools():
    import anyio

    from aiexport.server import server

    names = {tool.name for tool in anyio.run(server.list_tools)}
    assert {"export_ai", "inspect_ai", "check_environment"} <= names
