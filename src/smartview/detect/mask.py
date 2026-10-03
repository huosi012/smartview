"""识别有效区域：ROI 多边形 − 需剔除的自身区域（割台分禾器、机身等）。"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from smartview.config import CameraConfig
from smartview.types import Detection

Polygon = list[tuple[float, float]]


class RegionMask:
    def __init__(
        self,
        width: int,
        height: int,
        roi_polygon: Polygon | None = None,
        exclude_polygons: list[Polygon] | None = None,
        exclude_mask: np.ndarray | None = None,
    ) -> None:
        self.width, self.height = int(width), int(height)
        self.roi_polygon = roi_polygon
        self.exclude_polygons = list(exclude_polygons or [])
        roi = np.zeros((self.height, self.width), dtype=np.uint8)
        if roi_polygon:
            cv2.fillPoly(roi, [self._to_px(roi_polygon)], 1)
        else:
            roi[:] = 1
        excl = np.zeros_like(roi)
        for poly in self.exclude_polygons:
            cv2.fillPoly(excl, [self._to_px(poly)], 1)
        if exclude_mask is not None:
            m = exclude_mask
            if m.ndim == 3:
                m = m[..., 0]
            if m.shape != excl.shape:
                m = cv2.resize(m, (self.width, self.height), interpolation=cv2.INTER_NEAREST)
            excl |= (m > 127).astype(np.uint8)
        self.excluded = excl
        self.effective = (roi & (1 - excl)).astype(np.uint8)
        self.has_exclusions = bool(excl.any())

    def _to_px(self, poly: Polygon) -> np.ndarray:
        pts = [(x * (self.width - 1), y * (self.height - 1)) for x, y in poly]
        return np.round(np.array(pts, dtype=np.float32)).astype(np.int32).reshape(-1, 1, 2)

    @classmethod
    def from_camera(cls, cam: CameraConfig, width: int | None = None, height: int | None = None, base_dir: str | Path | None = None) -> RegionMask:
        w = width or cam.width
        h = height or cam.height
        excl_img = None
        if cam.exclude_mask_png:
            p = Path(cam.exclude_mask_png)
            if not p.is_absolute() and base_dir is not None:
                p = Path(base_dir) / p
            excl_img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            if excl_img is None:
                raise FileNotFoundError(f"排除遮罩文件不存在或无法读取: {p}")
        return cls(w, h, cam.roi_polygon, cam.exclude_polygons, excl_img)

    def for_size(self, width: int, height: int) -> RegionMask:
        if (width, height) == (self.width, self.height):
            return self
        excl = cv2.resize(self.excluded * 255, (width, height), interpolation=cv2.INTER_NEAREST)
        return RegionMask(width, height, self.roi_polygon, [], excl)

    # ------------------------------------------------------------------ queries
    def contains(self, u: float, v: float) -> bool:
        x, y = int(round(u)), int(round(v))
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        return bool(self.effective[y, x])

    def excluded_overlap(self, bbox: np.ndarray) -> float:
        """框与排除区的重叠面积占框面积的比例。"""
        if not self.has_exclusions:
            return 0.0
        x1, y1, x2, y2 = (int(round(float(v))) for v in bbox)
        x1, x2 = max(0, x1), min(self.width, x2 + 1)
        y1, y2 = max(0, y1), min(self.height, y2 + 1)
        if x2 <= x1 or y2 <= y1:
            return 1.0
        patch = self.excluded[y1:y2, x1:x2]
        return float(patch.mean())

    def filter(self, dets: list[Detection], max_excluded_overlap: float = 0.5) -> list[Detection]:
        """丢弃脚点不在有效区内、或与排除区重叠超过阈值的检测。"""
        out = []
        for d in dets:
            x1, _y1, x2, y2 = (float(v) for v in d.bbox)
            foot = ((x1 + x2) / 2.0, min(y2, self.height - 1))
            if not self.contains(*foot):
                continue
            if self.excluded_overlap(d.bbox) > max_excluded_overlap:
                continue
            out.append(d)
        return out

    def overlay(self, img: np.ndarray, alpha: float = 0.35) -> np.ndarray:
        """在图像上叠加 ROI 边界（绿）与排除区（红），供 HMI / 标定核对。"""
        out = img.copy()
        if self.has_exclusions:
            red = np.zeros_like(out)
            red[..., 2] = 255
            m = self.excluded.astype(bool)
            out[m] = (out[m] * (1 - alpha) + red[m] * alpha).astype(np.uint8)
        if self.roi_polygon:
            cv2.polylines(out, [self._to_px(self.roi_polygon)], True, (0, 200, 0), 1, cv2.LINE_AA)
        return out
