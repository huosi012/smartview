"""经典视觉基线检测器（离线占位，不用于量产）。

思路：玉米收获期画面主要由土壤（棕）与干秸秆/叶片（黄）构成，饱和度较高；石块、钢管、
水泥桩等异物多为低饱和的灰 / 暗色。粉尘与雾化会整体压低远处饱和度，因此阈值相对
"同一图像行的稳健背景（中值）"而不是绝对值。再用针孔几何做尺度门限：候选区域的像素高度
必须与该行处 0.10~0.70 m 物体的期望像素高度相符。
"""

from __future__ import annotations

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore

from smartview.detect.base import Detector
from smartview.detect.mask import RegionMask
from smartview.types import Detection

CLASSES = ["unknown_obstacle", "pipe_like"]


class ClassicalDetector(Detector):
    class_names = CLASSES

    def __init__(
        self,
        projector=None,
        region: RegionMask | None = None,
        conf_thr: float = 0.35,
        min_object_m: float = 0.10,
        max_object_m: float = 0.70,
        sat_ratio: float = 0.45,
        dark_ratio: float = 0.55,
        min_area_px: int = 12,
        min_height_px: int = 4,
    ) -> None:
        self.projector = projector
        self.region = region
        self.conf_thr = conf_thr
        self.min_object_m = min_object_m
        self.max_object_m = max_object_m
        self.sat_ratio = sat_ratio
        self.dark_ratio = dark_ratio
        self.min_area_px = min_area_px
        self.min_height_px = min_height_px
        self._gate_cache: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}

    # ------------------------------------------------------------- scale gate
    def _gates(self, h: int, w: int) -> tuple[np.ndarray, np.ndarray] | None:
        """每个图像行 v：最小 / 最大允许像素高度。"""
        if self.projector is None:
            return None
        key = (h, w)
        if key not in self._gate_cache:
            proj = self.projector.for_size(w, h)
            lo = np.full(h, np.nan, dtype=np.float32)
            hi = np.full(h, np.nan, dtype=np.float32)
            for v in range(h):
                a = proj.expected_height_px(float(v), self.min_object_m)
                b = proj.expected_height_px(float(v), self.max_object_m)
                if a is not None and b is not None:
                    lo[v], hi[v] = a, b
            self._gate_cache[key] = (lo, hi)
        return self._gate_cache[key]

    # ---------------------------------------------------------------- detect
    def detect(self, image: np.ndarray) -> list[Detection]:
        h, w = image.shape[:2]
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        S = hsv[..., 1].astype(np.float32)
        V = hsv[..., 2].astype(np.float32)
        eff = self.region.for_size(w, h).effective.astype(bool) if self.region is not None else np.ones((h, w), bool)

        # 逐行稳健背景（中值），只统计有效区像素；像素不足的行沿用邻近行
        s_med = np.full(h, np.nan, dtype=np.float32)
        v_med = np.full(h, np.nan, dtype=np.float32)
        counts = eff.sum(axis=1)
        for v in range(h):
            if counts[v] >= 8:
                row = eff[v]
                s_med[v] = np.median(S[v][row])
                v_med[v] = np.median(V[v][row])
        if np.all(np.isnan(s_med)):
            return []
        s_med = _fill_nan(s_med)
        v_med = _fill_nan(v_med)
        k = 9
        s_med = np.convolve(np.pad(s_med, k // 2, mode="edge"), np.ones(k) / k, mode="valid")
        v_med = np.convolve(np.pad(v_med, k // 2, mode="edge"), np.ones(k) / k, mode="valid")

        low_sat = S < np.maximum(self.sat_ratio * s_med[:, None], 6.0)
        dark = V < self.dark_ratio * v_med[:, None]
        not_sky = V < 235
        anomaly = (low_sat | dark) & not_sky & eff
        m = anomaly.astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

        n, labels, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
        gates = self._gates(h, w)
        dets: list[Detection] = []
        for i in range(1, n):
            x, y, bw, bh, area = (int(v) for v in stats[i])
            if area < self.min_area_px or bh < self.min_height_px or bw < 2:
                continue
            foot_v = min(y + bh - 1, h - 1)
            if gates is not None:
                lo, hi = gates[0][foot_v], gates[1][foot_v]
                if np.isnan(lo) or np.isnan(hi):
                    continue
                if bh < 0.5 * lo or bh > 1.6 * hi:
                    continue
                if bw > 2.2 * hi:  # 过宽（土块带、阴影带）
                    continue
            fill = area / float(bw * bh)
            if fill < 0.3:
                continue
            comp = labels[y : y + bh, x : x + bw] == i
            s_mean = float(S[y : y + bh, x : x + bw][comp].mean())
            v_mean = float(V[y : y + bh, x : x + bw][comp].mean())
            s_bg = float(np.mean(s_med[y : y + bh])) + 1e-6
            v_bg = float(np.mean(v_med[y : y + bh])) + 1e-6
            contrast = min(1.0, max(abs(s_mean - s_bg) / s_bg, abs(v_mean - v_bg) / v_bg))
            aspect = bh / float(bw)
            is_pipe = aspect >= 1.6 and v_mean < 0.8 * v_bg
            score = 0.30 + 0.25 * fill + 0.30 * contrast + (0.10 if is_pipe else 0.0)
            score = float(min(0.95, score))
            if score < self.conf_thr:
                continue
            cls_id = 1 if is_pipe else 0
            dets.append(
                Detection(
                    bbox=np.array([x, y, x + bw - 1, y + bh - 1], dtype=np.float32),
                    score=score,
                    cls_id=cls_id,
                    cls_name=CLASSES[cls_id],
                )
            )
        if self.region is not None:
            dets = self.region.for_size(w, h).filter(dets)
        return dets


def _fill_nan(a: np.ndarray) -> np.ndarray:
    a = a.copy()
    idx = np.flatnonzero(~np.isnan(a))
    if idx.size == 0:
        return a
    a[: idx[0]] = a[idx[0]]
    a[idx[-1] + 1 :] = a[idx[-1]]
    nan_pos = np.flatnonzero(np.isnan(a))
    if nan_pos.size:
        a[nan_pos] = np.interp(nan_pos, idx, a[idx])
    return a
