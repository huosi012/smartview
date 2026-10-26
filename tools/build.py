#!/usr/bin/env python3
"""把 index.html + config.js + importer.js + 所有图片打包成一个文件：output/<标题>-大屏.html

打包后的文件不依赖其他文件，拷到播放电脑上双击即可打开。

用法：  python3 tools/build.py
依赖：  pip install Pillow
"""
import base64
import copy
import io
import json
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

BACKGROUND_MAX_SIDE = 7000   # 底图最长边上限（像素），超过则缩小以控制文件体积
PHOTO_MAX_SIDE = 2000        # 照片、标志等最长边上限


def load_config():
    text = (ROOT / "config.js").read_text("utf-8")
    text = "\n".join(l for l in text.splitlines() if not l.strip().startswith("//"))
    return json.loads(text[text.index("=") + 1:text.rindex(";")])


def data_uri(rel_path, max_side):
    """读取图片：按 EXIF 方向摆正、限制尺寸，返回 data: URI。"""
    raw = (ROOT / rel_path).read_bytes()
    im = Image.open(io.BytesIO(raw))
    rotated = im.getexif().get(0x0112, 1) != 1
    if im.format in ("JPEG", "PNG") and not rotated and max(im.size) <= max_side:
        mime = Image.MIME[im.format]
    else:
        im = ImageOps.exif_transpose(im)
        im.thumbnail((max_side, max_side), Image.LANCZOS)
        buf = io.BytesIO()
        if im.mode in ("RGBA", "LA", "P"):
            im.save(buf, "PNG", optimize=True)
            mime = "image/png"
        else:
            im.convert("RGB").save(buf, "JPEG", quality=90)
            mime = "image/jpeg"
        raw = buf.getvalue()
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def build_html(cfg, out_path):
    html = (ROOT / "index.html").read_text("utf-8")
    c = copy.deepcopy(cfg)
    if c.get("background"):
        c["background"] = data_uri(c["background"], BACKGROUND_MAX_SIDE)
    for key in ("logo", "titleImage"):
        if c.get(key):
            c[key] = data_uri(c[key], PHOTO_MAX_SIDE)
    for p in c["people"]:
        if p.get("photo"):
            p["photo"] = data_uri(p["photo"], PHOTO_MAX_SIDE)
    inline = json.dumps(c, ensure_ascii=False).replace("</", "<\\/")
    html = replace_once(html, '<script id="sv-config" src="config.js"></script>',
                        f'<script id="sv-config">window.SMARTVIEW_CONFIG = {inline};</script>')
    importer = (ROOT / "importer.js").read_text("utf-8")
    if "</script" in importer.lower():
        raise SystemExit("importer.js 里不能出现 </script")
    html = replace_once(html, '<script src="importer.js"></script>', f"<script>\n{importer}</script>")
    out_path.write_text(html, "utf-8")


def replace_once(html, tag, new):
    if html.count(tag) != 1:
        raise SystemExit(f"index.html 中找不到（或有多处）：{tag}")
    return html.replace(tag, new)


def main():
    cfg = load_config()
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.html"):   # 只清理旧的网页版；PPT 由 build_pptx.py 生成
        old.unlink()
    out_path = OUT / f"{cfg.get('title', 'smartview')}-大屏.html"
    build_html(cfg, out_path)
    print(f"已生成 {out_path.relative_to(ROOT)}  ({out_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
