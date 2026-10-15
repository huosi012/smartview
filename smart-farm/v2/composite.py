"""Composite montage renders (RGBA, existing walls as holdouts) over the client's site photos."""
import os
import sys

from PIL import Image, ImageEnhance, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))


def comp(photo, render, out, grade=True):
    bg = Image.open(photo).convert("RGB")
    fg = Image.open(render).convert("RGBA").resize(bg.size, Image.LANCZOS)
    if grade:
        rgb = fg.convert("RGB")
        rgb = ImageEnhance.Color(rgb).enhance(0.88)          # photos are overcast and slightly desaturated
        rgb = rgb.filter(ImageFilter.GaussianBlur(0.6))       # match phone-camera softness
        fg = Image.merge("RGBA", (*rgb.split(), fg.split()[3]))
    out_im = Image.alpha_composite(bg.convert("RGBA"), fg).convert("RGB")
    out_im.save(out, quality=93)


if __name__ == "__main__":
    rdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "renders")
    for name in ("p_platform", "p_corr_across", "p_corr_far"):
        r = os.path.join(rdir, f"m_{name}.png")
        if os.path.exists(r):
            comp(os.path.join(HERE, "photos", f"{name}.jpg"), r, os.path.join(rdir, f"comp_{name}.jpg"))
            print("composited", name)
