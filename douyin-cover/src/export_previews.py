"""Save the rendered final deck (build/deck-NN.png) and the grid mockups as
the JPGs in ../previews, ready to send to the client.

Run after the final deck has been rendered; see render.sh.
"""
import os
import shutil

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "previews")
PAGES = ["1-三种风格", "2-主页九宫格效果", "3-出封面流程", "4-拍摄建议",
         "封面A-暗夜画廊", "封面B-象牙画册", "封面C-维修档案"]
GRIDS = {"noir": "A-暗夜画廊", "ivory": "B-象牙画册", "dossier": "C-维修档案"}

shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT)
for i, name in enumerate(PAGES, start=1):
    Image.open(os.path.join(HERE, "build", f"deck-{i}.png")).convert("RGB").save(
        os.path.join(OUT, f"{name}.jpg"), quality=88, optimize=True)
for style, name in GRIDS.items():
    shutil.copy(os.path.join(HERE, "assets", f"grid-mockup-{style}.jpg"), os.path.join(OUT, f"主页效果-{name}.jpg"))
print("previews written to", os.path.abspath(OUT))
