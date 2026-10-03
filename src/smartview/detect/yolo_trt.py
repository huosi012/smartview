"""YOLO TensorRT 后端（Jetson，TensorRT 10 API）。**需真机验证。**

引擎由 ``training/export_trt.sh`` 在目标 Jetson 上用 ``trtexec`` 构建（引擎与设备/TRT 版本绑定）。
JetPack 6.0 自带 TensorRT 8.6，6.1/6.2 为 TensorRT 10；本实现按 TRT 10 的 tensor-name API 编写，
在 8.x 上会给出明确错误而不是静默失败。
"""

from __future__ import annotations

import logging

import numpy as np

from smartview.detect.base import Detector
from smartview.detect.postprocess import clip_boxes, decode_yolo, letterbox, nms_numpy, unletterbox
from smartview.types import Detection

log = logging.getLogger(__name__)


class YoloTrtDetector(Detector):
    def __init__(self, engine_path: str, classes: list[str], input_size: int = 640, conf_thr: float = 0.35, iou_thr: float = 0.5) -> None:
        try:
            import tensorrt as trt  # type: ignore
            from cuda import cudart  # type: ignore
        except ImportError as exc:
            raise RuntimeError("TensorRT 后端需要 JetPack 自带的 tensorrt 与 cuda-python（pip install 'smartview[jetson]'）") from exc
        major = int(trt.__version__.split(".")[0])
        if major < 10:
            raise RuntimeError(f"检测到 TensorRT {trt.__version__}，本后端需要 TensorRT >= 10（JetPack 6.1+）")
        self.trt, self.cudart = trt, cudart
        logger = trt.Logger(trt.Logger.WARNING)
        with open(engine_path, "rb") as f, trt.Runtime(logger) as runtime:
            self.engine = runtime.deserialize_cuda_engine(f.read())
        if self.engine is None:
            raise RuntimeError(f"无法加载 TensorRT 引擎 {engine_path}")
        self.context = self.engine.create_execution_context()
        self.input_name = None
        self.output_name = None
        for i in range(self.engine.num_io_tensors):
            name = self.engine.get_tensor_name(i)
            if self.engine.get_tensor_mode(name) == trt.TensorIOMode.INPUT:
                self.input_name = name
            else:
                self.output_name = name
        assert self.input_name and self.output_name
        in_shape = tuple(self.engine.get_tensor_shape(self.input_name))
        if in_shape[2] > 0:
            input_size = int(in_shape[2])
        self.input_size = input_size
        self.in_shape = (1, 3, input_size, input_size)
        self.context.set_input_shape(self.input_name, self.in_shape)
        self.out_shape = tuple(self.context.get_tensor_shape(self.output_name))
        self.out_dtype = trt.nptype(self.engine.get_tensor_dtype(self.output_name))
        self.h_in = np.zeros(self.in_shape, dtype=np.float32)
        self.h_out = np.zeros(self.out_shape, dtype=self.out_dtype)
        err, self.d_in = cudart.cudaMalloc(self.h_in.nbytes)
        err2, self.d_out = cudart.cudaMalloc(self.h_out.nbytes)
        err3, self.stream = cudart.cudaStreamCreate()
        self.context.set_tensor_address(self.input_name, int(self.d_in))
        self.context.set_tensor_address(self.output_name, int(self.d_out))
        self.class_names = list(classes)
        self.conf_thr, self.iou_thr = conf_thr, iou_thr
        log.info("TensorRT 引擎 %s 输入 %s 输出 %s", engine_path, self.in_shape, self.out_shape)

    def detect(self, image: np.ndarray) -> list[Detection]:
        cudart = self.cudart
        h, w = image.shape[:2]
        lb, scale, pad = letterbox(image, self.input_size)
        x = lb[:, :, ::-1].astype(np.float32) / 255.0
        self.h_in[0] = x.transpose(2, 0, 1)
        kind = cudart.cudaMemcpyKind
        cudart.cudaMemcpyAsync(self.d_in, self.h_in.ctypes.data, self.h_in.nbytes, kind.cudaMemcpyHostToDevice, self.stream)
        self.context.execute_async_v3(self.stream)
        cudart.cudaMemcpyAsync(self.h_out.ctypes.data, self.d_out, self.h_out.nbytes, kind.cudaMemcpyDeviceToHost, self.stream)
        cudart.cudaStreamSynchronize(self.stream)
        boxes, scores, cls = decode_yolo(self.h_out.astype(np.float32), num_classes=len(self.class_names), conf_thr=self.conf_thr)
        if len(boxes) == 0:
            return []
        keep = nms_numpy(boxes, scores, self.iou_thr, class_ids=cls)
        boxes = clip_boxes(unletterbox(boxes[keep], scale, pad), w, h)
        return [
            Detection(bbox=b.astype(np.float32), score=float(s), cls_id=int(c), cls_name=self.class_names[int(c)])
            for b, s, c in zip(boxes, scores[keep], cls[keep], strict=True)
        ]

    def close(self) -> None:
        try:
            self.cudart.cudaFree(self.d_in)
            self.cudart.cudaFree(self.d_out)
            self.cudart.cudaStreamDestroy(self.stream)
        except Exception:  # noqa: BLE001  pragma: no cover
            pass
