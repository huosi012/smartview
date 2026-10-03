#!/usr/bin/env python3
"""训练封装（Ultralytics YOLO）。

⚠ 许可证提示：Ultralytics YOLOv5/v8/v11 代码与预训练权重为 **AGPL-3.0**，用于商用产品需购买
Ultralytics Enterprise License，或改用 Apache-2.0 架构（YOLOX、PP-YOLOE+/RT-DETR、DAMO-YOLO、D-FINE），
导出的 ONNX 只要是 ``(1, 4+nc, N)`` / ``(1, N, 4+nc)`` 布局即可被 smartview 直接加载。

示例::

    python training/train.py --data datasets/smartview_v1/data.yaml --model yolov8s.pt --epochs 120 --imgsz 640
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--model", default="yolov8s.pt")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default="0")
    ap.add_argument("--project", default="runs/smartview")
    ap.add_argument("--name", default="exp")
    ap.add_argument("--no-export", action="store_true")
    args = ap.parse_args()
    print("提示：Ultralytics 为 AGPL-3.0，商用需企业授权或迁移到 Apache-2.0 架构（见文件头）", file=sys.stderr)
    try:
        from ultralytics import YOLO
    except ImportError:
        raise SystemExit("请先安装：pip install 'smartview[train]'") from None
    model = YOLO(args.model)
    model.train(
        data=args.data,
        imgsz=args.imgsz,
        epochs=args.epochs,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        # 田间增强：mosaic + HSV + 运动模糊/雾化由 albumentations 自动启用（若已安装）
        hsv_h=0.015,
        hsv_s=0.6,
        hsv_v=0.5,
        degrees=3.0,
        translate=0.1,
        scale=0.5,
        fliplr=0.5,
        mosaic=1.0,
        close_mosaic=10,
        patience=30,
    )
    best = Path(args.project) / args.name / "weights" / "best.pt"
    print(f"最佳权重: {best}")
    if not args.no_export and best.exists():
        from export_onnx import export  # type: ignore

        export(str(best), str(best.with_suffix(".onnx")), args.imgsz, 17, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
