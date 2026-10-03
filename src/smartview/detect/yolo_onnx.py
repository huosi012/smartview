"""YOLO ONNX 后端（onnxruntime，CPU / CUDA EP）。"""

from __future__ import annotations

import logging

import numpy as np

from smartview.detect.base import Detector
from smartview.detect.postprocess import clip_boxes, decode_yolo, letterbox, nms_numpy, unletterbox
from smartview.types import Detection

log = logging.getLogger(__name__)


class YoloOnnxDetector(Detector):
    def __init__(
        self,
        model_path: str,
        classes: list[str],
        input_size: int = 640,
        conf_thr: float = 0.35,
        iou_thr: float = 0.5,
        num_threads: int = 2,
        providers: list[str] | None = None,
    ) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("onnx 后端需要安装 onnxruntime：pip install 'smartview[onnx]'") from exc
        so = ort.SessionOptions()
        so.intra_op_num_threads = int(num_threads)
        so.inter_op_num_threads = 1
        so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        if providers is None:
            avail = ort.get_available_providers()
            providers = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in avail]
        self.session = ort.InferenceSession(model_path, sess_options=so, providers=providers)
        inp = self.session.get_inputs()[0]
        self.input_name = inp.name
        shape = inp.shape
        if len(shape) == 4 and isinstance(shape[2], int) and shape[2] > 0:
            input_size = int(shape[2])
        self.input_size = input_size
        self.output_names = [o.name for o in self.session.get_outputs()]
        self.class_names = list(classes)
        self.conf_thr = conf_thr
        self.iou_thr = iou_thr
        self.model_path = model_path
        log.info("ONNX 模型 %s 输入 %s providers=%s", model_path, shape, self.session.get_providers())

    def preprocess(self, image: np.ndarray):
        lb, scale, pad = letterbox(image, self.input_size)
        x = lb[:, :, ::-1].astype(np.float32) / 255.0  # BGR→RGB
        x = np.ascontiguousarray(x.transpose(2, 0, 1)[None])
        return x, scale, pad

    def detect(self, image: np.ndarray) -> list[Detection]:
        h, w = image.shape[:2]
        x, scale, pad = self.preprocess(image)
        out = self.session.run(self.output_names, {self.input_name: x})[0]
        boxes, scores, cls = decode_yolo(out, num_classes=len(self.class_names), conf_thr=self.conf_thr)
        if len(boxes) == 0:
            return []
        keep = nms_numpy(boxes, scores, self.iou_thr, class_ids=cls)
        boxes = clip_boxes(unletterbox(boxes[keep], scale, pad), w, h)
        scores, cls = scores[keep], cls[keep]
        dets = []
        for b, s, c in zip(boxes, scores, cls, strict=True):
            if b[2] - b[0] < 1 or b[3] - b[1] < 1:
                continue
            c = int(c)
            name = self.class_names[c] if c < len(self.class_names) else str(c)
            dets.append(Detection(bbox=b.astype(np.float32), score=float(s), cls_id=c, cls_name=name))
        return dets

    def warmup(self) -> None:
        dummy = np.zeros((self.input_size, self.input_size, 3), dtype=np.uint8)
        for _ in range(2):
            self.detect(dummy)
