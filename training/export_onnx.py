#!/usr/bin/env python3
"""导出 ONNX 并写出 smartview 读取的 ``model.json``（类别、输入尺寸、输出布局）。

示例::

    python training/export_onnx.py --weights runs/smartview/exp/weights/best.pt --out models/smartview.onnx --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import yaml


def export(weights: str, out: str, imgsz: int = 640, opset: int = 17, check: bool = False) -> Path:
    from ultralytics import YOLO

    model = YOLO(weights)
    exported = model.export(format="onnx", imgsz=imgsz, opset=opset, simplify=True, dynamic=False, half=False)
    src = Path(exported)
    dst = Path(out)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dst.resolve():
        dst.write_bytes(src.read_bytes())
    names = model.names if isinstance(model.names, dict) else dict(enumerate(model.names))
    classes = [names[i] for i in sorted(names)]
    layout = "unknown"
    try:
        import onnx

        m = onnx.load(str(dst))
        dims = [d.dim_value for d in m.graph.output[0].type.tensor_type.shape.dim]
        layout = "1x(4+nc)xN" if len(dims) == 3 and dims[1] == 4 + len(classes) else "1xNx(4+nc)"
    except Exception as exc:  # noqa: BLE001
        print(f"读取 ONNX 输出形状失败: {exc}", file=sys.stderr)
    meta = {"classes": classes, "input_size": imgsz, "layout": layout, "opset": opset, "source": str(weights)}
    dst.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ONNX → {dst}\nmodel.json → {dst.with_suffix('.json')}\n{json.dumps(meta, ensure_ascii=False)}")
    if check:
        _parity(model, dst, imgsz)
    return dst


def _parity(model, onnx_path: Path, imgsz: int) -> None:
    """与 PyTorch 结果比对（最大绝对误差），需要 torch + onnxruntime。"""
    try:
        import onnxruntime as ort
        import torch
    except ImportError:
        print("跳过一致性校验（缺 torch/onnxruntime）")
        return
    x = np.random.default_rng(0).random((1, 3, imgsz, imgsz), dtype=np.float32)
    with torch.no_grad():
        ref = model.model(torch.from_numpy(x))
        ref = ref[0] if isinstance(ref, (list, tuple)) else ref
        ref = ref.cpu().numpy()
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    out = sess.run(None, {sess.get_inputs()[0].name: x})[0]
    if out.shape != ref.shape:
        print(f"形状不同（可能是布局转置）: onnx {out.shape} vs torch {ref.shape}")
        return
    print(f"一致性校验：最大绝对误差 {np.abs(out - ref).max():.5f}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--opset", type=int, default=17)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--classes", default=None, help="覆盖类别列表（classes.yaml）")
    args = ap.parse_args()
    dst = export(args.weights, args.out, args.imgsz, args.opset, args.check)
    if args.classes:
        meta = json.loads(dst.with_suffix(".json").read_text(encoding="utf-8"))
        meta["classes"] = list(yaml.safe_load(Path(args.classes).read_text(encoding="utf-8"))["names"])
        dst.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
