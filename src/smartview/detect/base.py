from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from smartview.config import DetectorConfig
from smartview.types import Detection

log = logging.getLogger(__name__)

# 训练类别顺序（与 training/classes.yaml 一致）
DEFAULT_CLASSES: list[str] = ["stone", "well_pipe", "stake", "concrete_pile", "person", "animal"]


class Detector(ABC):
    class_names: list[str]
    input_size: int = 640

    @abstractmethod
    def detect(self, image: np.ndarray) -> list[Detection]:
        """输入 BGR 全帧（或裁剪帧），返回该图像坐标系下的检测。"""

    def warmup(self) -> None:
        return None

    def close(self) -> None:
        return None


def load_model_meta(model_path: str | Path) -> dict:
    """读取与模型同名的 ``model.json``（由 training/export_onnx.py 写出）。"""
    p = Path(model_path)
    for cand in (p.with_suffix(".json"), p.parent / "model.json"):
        if cand.exists():
            try:
                return json.loads(cand.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                log.warning("模型元数据 %s 不是合法 JSON，忽略", cand)
    return {}


def build_detector(cfg: DetectorConfig, projector=None, region=None, base_dir: str | Path | None = None) -> Detector:
    """按配置构造检测器。projector / region 供 classical 基线做尺度门限与区域限制。"""
    classes = cfg.classes
    if cfg.backend == "classical":
        from smartview.detect.classical import ClassicalDetector

        return ClassicalDetector(
            projector=projector,
            region=region,
            conf_thr=cfg.conf_thr,
            min_object_m=cfg.min_object_m,
            max_object_m=cfg.max_object_m,
        )
    if not cfg.model_path:
        raise ValueError(f"detector.backend={cfg.backend} 需要 model_path")
    model_path = Path(cfg.model_path)
    if not model_path.is_absolute() and base_dir is not None:
        model_path = Path(base_dir) / model_path
    meta = load_model_meta(model_path)
    classes = classes or meta.get("classes") or DEFAULT_CLASSES
    input_size = int(meta.get("input_size", cfg.input_size))
    if cfg.backend == "onnx":
        from smartview.detect.yolo_onnx import YoloOnnxDetector

        return YoloOnnxDetector(
            str(model_path),
            classes,
            input_size=input_size,
            conf_thr=cfg.conf_thr,
            iou_thr=cfg.iou_thr,
            num_threads=cfg.num_threads,
        )
    if cfg.backend == "tensorrt":
        from smartview.detect.yolo_trt import YoloTrtDetector

        return YoloTrtDetector(str(model_path), classes, input_size=input_size, conf_thr=cfg.conf_thr, iou_thr=cfg.iou_thr)
    raise ValueError(f"未知 detector backend: {cfg.backend}")
