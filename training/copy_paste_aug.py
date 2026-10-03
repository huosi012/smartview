#!/usr/bin/env python3
"""Copy-Paste 合成增强：把井口钢管 / 石块等抠图按相机几何贴入真实田间背景帧，自动生成 YOLO 标签。

真实数据中井口钢管样本极少（一块地通常只有几口井），用抠图合成快速扩充；贴入位置与尺寸
由相机模型决定（地面点 → 像素脚点、真实高度 → 像素高度），保证远近尺度合理。

抠图文件：PNG（RGBA），文件名以类别名开头，如 ``well_pipe_01.png``、``stone_07.png``。

示例::

    python training/copy_paste_aug.py --backgrounds data/bg --cutouts data/cutouts --out datasets/synth_cp \
        --config configs/jetson_4row.yaml --cam fwd --n-per-image 2 --count 2000
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import cv2
import numpy as np
import yaml

from smartview.config import SmartViewConfig
from smartview.geometry.camera import PinholeCamera

HEIGHT_RANGE_M = {  # 真实高度采样范围（米）
    "well_pipe": (0.25, 0.6),
    "stone": (0.10, 0.35),
    "stake": (0.5, 1.2),
    "concrete_pile": (0.3, 0.9),
    "person": (1.5, 1.85),
    "animal": (0.4, 0.9),
}


def load_cutouts(d: Path, classes: list[str]) -> list[tuple[str, np.ndarray]]:
    out = []
    for p in sorted(d.glob("*.png")):
        cls = next((c for c in sorted(classes, key=len, reverse=True) if p.stem.startswith(c)), None)
        img = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
        if cls is None or img is None or img.ndim != 3 or img.shape[2] != 4:
            continue
        out.append((cls, img))
    if not out:
        raise SystemExit(f"{d} 下没有合法的 RGBA 抠图（文件名需以类别名开头）")
    return out


def paste(bg: np.ndarray, cut: np.ndarray, foot_uv: tuple[float, float], height_px: float, rng: random.Random):
    h, w = cut.shape[:2]
    s = height_px / h
    nw, nh = max(2, int(round(w * s))), max(2, int(round(h * s)))
    c = cv2.resize(cut, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
    if rng.random() < 0.5:
        c = c[:, ::-1]
    u, v = foot_uv
    x1, y1 = int(round(u - nw / 2)), int(round(v - nh))
    x2, y2 = x1 + nw, y1 + nh
    H, W = bg.shape[:2]
    if x1 < 0 or y1 < 0 or x2 > W or y2 > H:
        return None
    rgb = c[..., :3].astype(np.float32)
    alpha = (c[..., 3].astype(np.float32) / 255.0)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 0.8)[..., None]
    region = bg[y1:y2, x1:x2].astype(np.float32)
    # 颜色/亮度匹配：按背景局部均值调整抠图亮度，再按比例保留自身对比
    gain = (region.mean() + 1e-6) / (rgb.mean() + 1e-6)
    rgb = np.clip(rgb * (0.6 + 0.4 * gain), 0, 255)
    # 远处增加雾化
    out = region * (1 - alpha) + rgb * alpha
    bg[y1:y2, x1:x2] = out.astype(np.uint8)
    return (x1, y1, x2 - 1, y2 - 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backgrounds", required=True)
    ap.add_argument("--cutouts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", required=True, help="smartview 配置（取相机 mount / 尺寸 / ROI）")
    ap.add_argument("--cam", required=True)
    ap.add_argument("--classes", default=str(Path(__file__).with_name("classes.yaml")))
    ap.add_argument("--n-per-image", type=int, default=2)
    ap.add_argument("--count", type=int, default=1000, help="生成图片数（循环使用背景）")
    ap.add_argument("--x-range", nargs=2, type=float, default=[3.0, 22.0])
    ap.add_argument("--y-range", nargs=2, type=float, default=[-2.5, 2.5])
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    classes = list(yaml.safe_load(Path(args.classes).read_text(encoding="utf-8"))["names"])
    cfg = SmartViewConfig.load(args.config)
    cam_cfg = cfg.camera(args.cam)
    cutouts = load_cutouts(Path(args.cutouts), classes)
    bgs = sorted(p for p in Path(args.backgrounds).rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not bgs:
        raise SystemExit("没有背景图片")
    out = Path(args.out)
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "labels").mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    made = 0
    for i in range(args.count):
        bg_path = bgs[i % len(bgs)]
        bg = cv2.imread(str(bg_path))
        if bg is None:
            continue
        H, W = bg.shape[:2]
        cam = PinholeCamera.from_mount(W, H, cam_cfg.mount)
        lines = []
        for _ in range(args.n_per_image):
            cls, cut = rng.choice(cutouts)
            for _try in range(10):
                x = rng.uniform(*args.x_range)
                y = rng.uniform(*args.y_range)
                hgt = rng.uniform(*HEIGHT_RANGE_M.get(cls, (0.2, 0.6)))
                uv = cam.ground_to_image(x, y)
                hp = cam.object_height_px(x, y, hgt)
                if uv is None or hp is None or hp < 6:
                    continue
                box = paste(bg, cut, uv, hp, rng)
                if box is None:
                    continue
                x1, y1, x2, y2 = box
                lines.append(f"{classes.index(cls)} {(x1 + x2) / 2 / W:.6f} {(y1 + y2) / 2 / H:.6f} {(x2 - x1) / W:.6f} {(y2 - y1) / H:.6f}")
                break
        name = f"cp_{i:06d}"
        cv2.imwrite(str(out / "images" / f"{name}.jpg"), bg, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        (out / "labels" / f"{name}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
        made += 1
    print(f"生成 {made} 张 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
