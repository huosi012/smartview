"""RGB → CMYK conversion of a PDF that keeps every object editable.

Ghostscript can convert colours too, but it rasterises gradients while doing so, which
turns an editable gradient into a picture once the file is opened in Illustrator. Here
the PDF is rewritten in place instead: colour operators in content streams, gradient
(shading) functions, transparency-group colour spaces and RGB images.
"""

from __future__ import annotations

import glob
import os
import zlib
from decimal import Decimal
from pathlib import Path

import pikepdf
from pikepdf import Array, ContentStreamInlineImage, ContentStreamInstruction, Dictionary, Name, Operator
from PIL import Image, ImageCms

RGB, GRAY, CMYK, PATTERN, INDEXED, SPOT, OTHER = "rgb", "gray", "cmyk", "pattern", "indexed", "spot", "other"

# Ranked by how likely a Chinese / Asian print shop expects them (matched on letters and
# digits only, so "Japan Color 2001 Coated" and "JapanColor2001Coated.icc" both hit).
_PROFILE_PREFERENCE = (
    "Japan Color 2001 Coated",
    "Coated FOGRA39",
    "ISO Coated v2",
    "U.S. Web Coated (SWOP)",
    "US Web Coated SWOP",
    "Generic CMYK",
    "default_cmyk",
)

_PROFILE_DIRS = (
    "/Library/Application Support/Adobe/Color/Profiles/Recommended",
    "/Library/Application Support/Adobe/Color/Profiles",
    "/Library/ColorSync/Profiles",
    "~/Library/ColorSync/Profiles",
    "/System/Library/ColorSync/Profiles",
    r"C:\Program Files (x86)\Common Files\Adobe\Color\Profiles\Recommended",
    r"C:\Program Files\Common Files\Adobe\Color\Profiles\Recommended",
    r"C:\Windows\System32\spool\drivers\color",
    "/usr/share/color/icc",
    "/usr/local/share/color/icc",
    "~/.local/share/color/icc",
    "/usr/share/ghostscript/*/iccprofiles",
    "/usr/local/share/ghostscript/*/iccprofiles",
    "/opt/homebrew/share/ghostscript/*/iccprofiles",
    r"C:\Program Files\gs\gs*\iccprofiles",
)


def _build_transform(path: Path):
    """sRGB → CMYK transform, or None when ``path`` is not a usable CMYK output profile."""
    try:
        profile = ImageCms.getOpenProfile(str(path))
        if profile.profile.xcolor_space.strip() != "CMYK":
            return None
        transform = ImageCms.buildTransform(
            ImageCms.createProfile("sRGB"),
            profile,
            "RGB",
            "CMYK",
            renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
            flags=ImageCms.Flags.BLACKPOINTCOMPENSATION,
        )
        ImageCms.applyTransform(Image.new("RGB", (1, 1)), transform)  # some profiles only fail here
    except (OSError, ValueError, ImageCms.PyCMSError):
        return None
    return transform


def find_cmyk_profile() -> Path | None:
    """Best CMYK ICC profile installed on this machine (Adobe's, the OS's or Ghostscript's)."""
    override = os.environ.get("AIEXPORT_CMYK_PROFILE")
    if override:
        return Path(override)
    found: list[Path] = []
    for pattern in _PROFILE_DIRS:
        for directory in glob.glob(os.path.expanduser(pattern)):
            root = Path(directory)
            if root.is_dir():
                found += [p for p in root.rglob("*") if p.suffix.lower() in (".icc", ".icm")]

    def rank(path: Path) -> int:
        name = "".join(ch for ch in path.stem.lower() if ch.isalnum())
        for i, key in enumerate(_PROFILE_PREFERENCE):
            if "".join(ch for ch in key if ch.isalnum()) in name:
                return i
        return len(_PROFILE_PREFERENCE)

    for path in sorted(found, key=rank):
        if _build_transform(path) is not None:
            return path
    return None


class ColorConverter:
    """sRGB → CMYK through an ICC profile (relative colorimetric + black point compensation,
    Illustrator's default), with neutral greys mapped to pure K so black text prints as K100."""

    def __init__(self, profile: str | Path | None = None, gray_to_k: bool = True):
        self.gray_to_k = gray_to_k
        self.profile_path = Path(profile).expanduser() if profile else find_cmyk_profile()
        self._transform = None
        self._cache: dict[tuple[int, int, int], tuple[float, ...]] = {}
        if self.profile_path:
            self._transform = _build_transform(self.profile_path)
            if self._transform is None:
                raise ValueError(f"不是可用的 CMYK ICC 配置文件：{self.profile_path}")

    @property
    def description(self) -> str:
        if self._transform is None:
            return "简单公式（未找到 CMYK ICC 配置文件）"
        try:
            name = ImageCms.getProfileDescription(ImageCms.getOpenProfile(str(self.profile_path))).strip()
        except ImageCms.PyCMSError:
            name = ""
        return f"{name or self.profile_path.name}（{self.profile_path}）"

    def rgb(self, r: float, g: float, b: float) -> tuple[float, float, float, float]:
        key = tuple(round(min(max(v, 0.0), 1.0) * 255) for v in (r, g, b))
        if self.gray_to_k and key[0] == key[1] == key[2]:
            return (0.0, 0.0, 0.0, round(1 - key[0] / 255, 4))
        if key not in self._cache:
            if self._transform is not None:
                pixel = ImageCms.applyTransform(Image.new("RGB", (1, 1), key), self._transform).getpixel((0, 0))
            else:
                pixel = _naive_cmyk(*key)
            self._cache[key] = tuple(round(v / 255, 4) for v in pixel)
        return self._cache[key]

    def gray(self, level: float) -> tuple[float, float, float, float]:
        return (0.0, 0.0, 0.0, round(1 - min(max(level, 0.0), 1.0), 4))

    def image(self, im: Image.Image) -> Image.Image:
        im = im.convert("RGB")
        if self._transform is not None:
            return ImageCms.applyTransform(im, self._transform)
        out = Image.new("CMYK", im.size)
        out.putdata([_naive_cmyk(*px) for px in im.getdata()])
        return out


def _naive_cmyk(r: int, g: int, b: int) -> tuple[int, int, int, int]:
    k = 255 - max(r, g, b)
    if k == 255:
        return (0, 0, 0, 255)
    return tuple(round((255 - v - k) * 255 / (255 - k)) for v in (r, g, b)) + (k,)


def colorspace_kind(cs, resources: Dictionary | None = None) -> str:
    """Classify a colour space (a name, a resource name or an array) as rgb/gray/cmyk/…"""
    if isinstance(cs, Name):
        name = str(cs)
        if name in ("/DeviceRGB", "/CalRGB", "/RGB"):
            return RGB
        if name in ("/DeviceGray", "/CalGray", "/G"):
            return GRAY
        if name in ("/DeviceCMYK", "/CMYK"):
            return CMYK
        if name == "/Pattern":
            return PATTERN
        named = resources.get("/ColorSpace") if resources is not None else None
        if named is not None and name in named:
            return colorspace_kind(named[name])
        return OTHER
    if isinstance(cs, Array) and len(cs):
        family = str(cs[0])
        if family == "/ICCBased":
            return {1: GRAY, 3: RGB, 4: CMYK}.get(int(cs[1].get("/N", 0)), OTHER)
        if family == "/CalRGB":
            return RGB
        if family == "/CalGray":
            return GRAY
        if family == "/Pattern":
            return PATTERN
        if family == "/Indexed":
            return INDEXED
        if family in ("/Separation", "/DeviceN"):
            return SPOT
    return OTHER


def _numbers(operands) -> list[float] | None:
    if all(isinstance(v, (int, float, Decimal)) and not isinstance(v, bool) for v in operands):
        return [float(v) for v in operands]
    return None


class PdfCmykConverter:
    """Rewrites every RGB / grey colour reachable from the pages of a PDF as CMYK."""

    def __init__(self, colors: ColorConverter):
        self.colors = colors
        self.warnings: list[str] = []
        self._seen: set[tuple[int, int]] = set()

    def convert(self, pdf: pikepdf.Pdf) -> None:
        for page in pdf.pages:
            resources = page.obj.get("/Resources")
            self._convert_group(page.obj)
            self._convert_resources(resources)
            self._convert_content(page.obj, resources, pdf)

    def _first_visit(self, obj) -> bool:
        if not obj.is_indirect:
            return True
        if obj.objgen in self._seen:
            return False
        self._seen.add(obj.objgen)
        return True

    def _warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def _convert_group(self, obj) -> None:
        group = obj.get("/Group")
        if group is not None and group.get("/S") == "/Transparency" and colorspace_kind(group.get("/CS")) == RGB:
            group.CS = Name.DeviceCMYK

    def _convert_resources(self, resources: Dictionary | None) -> None:
        if resources is None:
            return
        for xobj in (resources.get("/XObject") or {}).values():
            if not self._first_visit(xobj):
                continue
            if xobj.get("/Subtype") == "/Image":
                self._convert_image(xobj)
            elif xobj.get("/Subtype") == "/Form":
                own = xobj.get("/Resources", resources)
                self._convert_group(xobj)
                self._convert_resources(own)
                self._convert_content(xobj, own)
        for pattern in (resources.get("/Pattern") or {}).values():
            if not self._first_visit(pattern):
                continue
            if pattern.get("/PatternType") == 2:
                self._convert_shading(pattern.Shading)
            elif pattern.get("/PaintType") == 1:  # coloured tiling pattern
                own = pattern.get("/Resources")
                self._convert_resources(own)
                self._convert_content(pattern, own)
        for shading in (resources.get("/Shading") or {}).values():
            self._convert_shading(shading)

    def _convert_content(self, obj, resources: Dictionary | None, pdf: pikepdf.Pdf | None = None) -> None:
        try:
            instructions = pikepdf.parse_content_stream(obj)
        except pikepdf.PdfError as exc:
            self._warn(f"无法解析内容流，部分颜色未转换：{exc}")
            return
        out: list = []
        fill = stroke = GRAY  # the initial colour space of every content stream
        saved: list[tuple[str, str]] = []
        changed = False
        for inst in instructions:
            if isinstance(inst, ContentStreamInlineImage):
                self._warn("内嵌（inline）图片保留了原色彩空间")
                out.append(inst)
                continue
            op, operands = str(inst.operator), inst.operands
            replacement = None
            if op == "q":
                saved.append((fill, stroke))
            elif op == "Q" and saved:
                fill, stroke = saved.pop()
            elif op in ("rg", "RG") and (nums := _numbers(operands)) and len(nums) == 3:
                replacement = (self.colors.rgb(*nums), "k" if op == "rg" else "K")
            elif op in ("g", "G") and (nums := _numbers(operands)) and len(nums) == 1:
                replacement = (self.colors.gray(nums[0]), "k" if op == "g" else "K")
            elif op in ("cs", "CS") and operands:
                kind = colorspace_kind(operands[0], resources)
                if op == "cs":
                    fill = kind
                else:
                    stroke = kind
                if kind in (RGB, GRAY):
                    replacement = ([Name.DeviceCMYK], op)
            elif op in ("sc", "scn", "SC", "SCN"):
                kind = fill if op in ("sc", "scn") else stroke
                nums = _numbers(operands)
                if nums and kind == RGB and len(nums) == 3:
                    replacement = (self.colors.rgb(*nums), op)
                elif nums and kind == GRAY and len(nums) == 1:
                    replacement = (self.colors.gray(nums[0]), op)
            if replacement is None:
                out.append(inst)
            else:
                values, new_op = replacement
                out.append(ContentStreamInstruction(list(values), Operator(new_op)))
                changed = True
        if not changed:
            return
        data = pikepdf.unparse_content_stream(out)
        if pdf is not None:  # a page: its /Contents may be an array of streams
            obj.Contents = pdf.make_stream(data)
        else:
            obj.write(data)

    def _convert_shading(self, shading) -> None:
        if not self._first_visit(shading) or colorspace_kind(shading.get("/ColorSpace")) != RGB:
            return
        if int(shading.get("/ShadingType", 0)) not in (1, 2, 3):
            self._warn("网格渐变（mesh shading）保留了 RGB")
            return
        function = self._convert_function(shading.get("/Function"))
        if function is None:
            self._warn("有渐变使用了不支持的函数类型，保留了 RGB")
            return
        shading.Function = function
        if "/Background" in shading and (nums := _numbers(shading.Background)) and len(nums) == 3:
            shading.Background = Array(self.colors.rgb(*nums))
        shading.ColorSpace = Name.DeviceCMYK

    def _convert_function(self, function):
        if not isinstance(function, Dictionary):  # arrays of 1-output functions, sampled streams
            return None
        kind = int(function.get("/FunctionType", -1))
        if kind == 2:
            c0, c1 = _numbers(function.get("/C0", [])), _numbers(function.get("/C1", []))
            if not c0 or not c1 or len(c0) != 3 or len(c1) != 3:
                return None
            converted = Dictionary(
                FunctionType=2,
                Domain=function.Domain,
                N=function.N,
                C0=Array(self.colors.rgb(*c0)),
                C1=Array(self.colors.rgb(*c1)),
            )
        elif kind == 3:
            parts = [self._convert_function(f) for f in function.Functions]
            if any(p is None for p in parts):
                return None
            converted = Dictionary(
                FunctionType=3,
                Domain=function.Domain,
                Functions=Array(parts),
                Bounds=function.Bounds,
                Encode=function.Encode,
            )
        else:
            return None
        if "/Range" in function:
            converted.Range = Array([0, 1] * 4)
        return converted

    def _convert_image(self, image) -> None:
        if image.get("/ImageMask"):
            return  # stencil masks are painted with the (already converted) fill colour
        cs = image.get("/ColorSpace")
        kind = colorspace_kind(cs)
        if kind == INDEXED and colorspace_kind(cs[1]) == RGB:
            self._convert_palette(image, cs)
            return
        if kind != RGB:
            return
        if int(image.get("/BitsPerComponent", 8)) != 8:
            self._warn("有非 8 位的 RGB 图片保留了 RGB")
            return
        try:
            pil = pikepdf.PdfImage(image).as_pil_image()
        except Exception as exc:  # unsupported filters such as JBIG2/JPX
            self._warn(f"有图片无法解码，保留了 RGB：{exc}")
            return
        cmyk = self.colors.image(pil)
        image.write(zlib.compress(cmyk.tobytes(), 6), filter=Name.FlateDecode)
        image.ColorSpace = Name.DeviceCMYK
        image.BitsPerComponent = 8
        for key in ("/DecodeParms", "/Decode"):
            if key in image:
                del image[key]

    def _convert_palette(self, image, cs: Array) -> None:
        hival = int(cs[2])
        lookup = cs[3]
        table = lookup.read_bytes() if isinstance(lookup, pikepdf.Stream) else bytes(lookup)
        table = table[: (hival + 1) * 3].ljust((hival + 1) * 3, b"\0")
        swatch = Image.frombytes("RGB", (hival + 1, 1), table)
        image.ColorSpace = Array([Name.Indexed, Name.DeviceCMYK, hival, pikepdf.String(self.colors.image(swatch).tobytes())])
