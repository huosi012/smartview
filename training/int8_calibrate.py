#!/usr/bin/env python3
"""TensorRT INT8 熵校准：用田间图片生成 calib.cache（在目标 Jetson 上运行，TensorRT ≥ 10）。

示例::

    python training/int8_calibrate.py --images data/calib --onnx models/smartview.onnx --out models/smartview_int8.calib.cache
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images", required=True)
    ap.add_argument("--onnx", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--max-images", type=int, default=500)
    args = ap.parse_args()
    try:
        import tensorrt as trt
        from cuda import cudart
    except ImportError:
        raise SystemExit("需要在 Jetson 上运行（tensorrt + cuda-python）") from None
    import cv2

    from smartview.detect.postprocess import letterbox

    files = sorted(p for p in Path(args.images).rglob("*") if p.suffix.lower() in {".jpg", ".png"})[: args.max_images]
    if not files:
        raise SystemExit("没有校准图片")

    class Calib(trt.IInt8EntropyCalibrator2):
        def __init__(self):
            super().__init__()
            self.i = 0
            self.nbytes = args.batch * 3 * args.imgsz * args.imgsz * 4
            _, self.dev = cudart.cudaMalloc(self.nbytes)

        def get_batch_size(self):
            return args.batch

        def get_batch(self, names):
            if self.i + args.batch > len(files):
                return None
            batch = []
            for p in files[self.i : self.i + args.batch]:
                img = cv2.imread(str(p))
                lb, _, _ = letterbox(img, args.imgsz)
                batch.append(lb[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0)
            self.i += args.batch
            arr = np.ascontiguousarray(np.stack(batch))
            cudart.cudaMemcpy(self.dev, arr.ctypes.data, arr.nbytes, cudart.cudaMemcpyKind.cudaMemcpyHostToDevice)
            return [int(self.dev)]

        def read_calibration_cache(self):
            p = Path(args.out)
            return p.read_bytes() if p.exists() else None

        def write_calibration_cache(self, cache):
            Path(args.out).write_bytes(cache)

    logger = trt.Logger(trt.Logger.INFO)
    builder = trt.Builder(logger)
    network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    parser = trt.OnnxParser(network, logger)
    if not parser.parse(Path(args.onnx).read_bytes()):
        for i in range(parser.num_errors):
            print(parser.get_error(i))
        raise SystemExit("ONNX 解析失败")
    config = builder.create_builder_config()
    config.set_flag(trt.BuilderFlag.INT8)
    config.set_flag(trt.BuilderFlag.FP16)
    config.int8_calibrator = Calib()
    engine = builder.build_serialized_network(network, config)
    if engine is None:
        raise SystemExit("构建失败")
    Path(args.out).with_suffix(".engine").write_bytes(engine)
    print(f"校准缓存 → {args.out}；INT8 引擎 → {Path(args.out).with_suffix('.engine')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
