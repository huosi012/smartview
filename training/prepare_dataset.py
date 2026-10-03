#!/usr/bin/env python3
"""整理标注数据为 YOLO 格式并按"序列"划分训练 / 验证 / 测试集。

支持两种输入：
* LabelMe JSON（与图片同名，矩形标注，label 为类别名）；
* 已是 YOLO txt（``labels/`` 目录，与图片同名）。

按序列划分：同一段视频抽出的帧高度相似，必须整段进入同一子集，否则验证指标虚高。
序列 id = 文件名去掉最后一个 ``_`` 之后的部分（例如 ``field03_cam1_000123.jpg`` → ``field03_cam1``）。

示例::

    python training/prepare_dataset.py --src data/raw --out datasets/smartview_v1 --split 0.7 0.2 0.1
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import shutil
from pathlib import Path

import yaml

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp"}


def load_classes(path: Path) -> list[str]:
    return list(yaml.safe_load(path.read_text(encoding="utf-8"))["names"])


def labelme_to_yolo(js: dict, classes: list[str], w: int, h: int, min_box_px: int) -> list[str]:
    lines = []
    for sh in js.get("shapes", []):
        if sh.get("shape_type", "rectangle") not in ("rectangle", "polygon"):
            continue
        label = sh["label"]
        if label not in classes:
            continue
        pts = sh["points"]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x1, x2, y1, y2 = max(0, min(xs)), min(w, max(xs)), max(0, min(ys)), min(h, max(ys))
        if x2 - x1 < min_box_px or y2 - y1 < min_box_px:
            continue
        cid = classes.index(label)
        lines.append(f"{cid} {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} {(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--classes", default=str(Path(__file__).with_name("classes.yaml")))
    ap.add_argument("--split", nargs=3, type=float, default=[0.7, 0.2, 0.1])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--copy", action="store_true", help="复制图片而不是软链接")
    args = ap.parse_args()

    src, out = Path(args.src), Path(args.out)
    cls_cfg = yaml.safe_load(Path(args.classes).read_text(encoding="utf-8"))
    classes = list(cls_cfg["names"])
    min_box = int(cls_cfg.get("min_box_px", 8))
    images = sorted(p for p in src.rglob("*") if p.suffix.lower() in IMG_EXT)
    if not images:
        raise SystemExit(f"{src} 下没有图片")

    import cv2

    samples: dict[str, list[tuple[Path, list[str]]]] = collections.defaultdict(list)
    class_count = collections.Counter()
    height_hist = collections.Counter()
    for img in images:
        stem = img.stem
        seq = stem.rsplit("_", 1)[0] if "_" in stem else stem
        lines: list[str] | None = None
        lm = img.with_suffix(".json")
        yolo_txt = img.parent.parent / "labels" / f"{stem}.txt" if img.parent.name == "images" else img.with_suffix(".txt")
        if lm.exists():
            im = cv2.imread(str(img))
            if im is None:
                continue
            h, w = im.shape[:2]
            lines = labelme_to_yolo(json.loads(lm.read_text(encoding="utf-8")), classes, w, h, min_box)
        elif yolo_txt.exists():
            lines = [ln.strip() for ln in yolo_txt.read_text().splitlines() if ln.strip()]
            im = cv2.imread(str(img))
            h = im.shape[0] if im is not None else 1080
        else:
            lines = []  # 负样本（无异物的背景帧同样重要）
            h = 1080
        for ln in lines:
            cid, _cx, _cy, _bw, bh = ln.split()
            class_count[classes[int(cid)]] += 1
            px = float(bh) * h
            bucket = "<16px" if px < 16 else "<32px" if px < 32 else "<64px" if px < 64 else ">=64px"
            height_hist[bucket] += 1
        samples[seq].append((img, lines))

    seqs = sorted(samples)
    rnd = random.Random(args.seed)
    rnd.shuffle(seqs)
    n = len(seqs)
    n_train = int(round(n * args.split[0]))
    n_val = int(round(n * args.split[1]))
    parts = {"train": seqs[:n_train], "val": seqs[n_train : n_train + n_val], "test": seqs[n_train + n_val :]}
    for part, part_seqs in parts.items():
        (out / "images" / part).mkdir(parents=True, exist_ok=True)
        (out / "labels" / part).mkdir(parents=True, exist_ok=True)
        for seq in part_seqs:
            for img, lines in samples[seq]:
                dst = out / "images" / part / img.name
                if dst.exists() or dst.is_symlink():
                    dst.unlink()
                if args.copy:
                    shutil.copy2(img, dst)
                else:
                    dst.symlink_to(img.resolve())
                (out / "labels" / part / f"{img.stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
    data = {
        "path": str(out.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": dict(enumerate(classes)),
    }
    (out / "data.yaml").write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"序列 {n} 段 → train {len(parts['train'])} / val {len(parts['val'])} / test {len(parts['test'])}；图片 {len(images)} 张")
    print("类别计数:", dict(class_count))
    print("目标像素高度分布（距离代理）:", dict(height_hist))
    print(f"data.yaml → {out / 'data.yaml'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
