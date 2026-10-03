"""相机健康监测：帧率、延迟、冻结 / 黑屏 / 离线、镜头脏污。

镜头脏污按 **分块** 判定（泥点 / 灰尘通常只遮住画面一部分）：把缩略图分成 16×10 块，
某块同时满足以下两条即视为"脏块"：
1. 该块清晰度（拉普拉斯能量）相对自身 60 s 滚动基线显著下降（ratio < dirty_sharp_ratio）；
2. 该块中"时间上几乎不变"的像素占比高（> dirty_block_static）：车辆前进时地面在流动而污点不动。
脏块占比 ≥ dirty_block_frac 时上报 ``lens_dirty``（并可触发吹扫）。
"""

from __future__ import annotations

from collections import deque

import cv2
import numpy as np

from smartview.clock import Clock, MonotonicClock
from smartview.types import CamHealth, Frame


class HealthMonitor:
    def __init__(
        self,
        cam_id: str,
        clock: Clock | None = None,
        small: tuple[int, int] = (160, 90),
        grid: tuple[int, int] = (16, 10),
        frozen_s: float = 2.0,
        offline_s: float = 2.0,
        baseline_s: float = 60.0,
        baseline_step_s: float = 0.5,
        dirty_sharp_ratio: float = 0.3,
        dirty_block_static: float = 0.5,
        dirty_block_frac: float = 0.15,
        black_luma: float = 15.0,
    ) -> None:
        self.cam_id = cam_id
        self.clock = clock or MonotonicClock()
        self.small = small
        self.grid = grid
        self.frozen_s, self.offline_s = frozen_s, offline_s
        self.baseline_s, self.baseline_step_s = baseline_s, baseline_step_s
        self.dirty_sharp_ratio = dirty_sharp_ratio
        self.dirty_block_static = dirty_block_static
        self.dirty_block_frac = dirty_block_frac
        self.black_luma = black_luma
        self._prev: np.ndarray | None = None
        self._last_ts: float | None = None
        self._fps = 0.0
        self._lat = 0.0
        self._frozen_since: float | None = None
        self._hist: deque[tuple[float, np.ndarray]] = deque()
        self._last_hist_ts = -1e9
        self._var: np.ndarray | None = None
        self._mean: np.ndarray | None = None
        self.health = CamHealth(cam_id=cam_id)
        self.dirty_blocks: np.ndarray | None = None

    # ------------------------------------------------------------------ utils
    def _blocks(self, a: np.ndarray) -> np.ndarray:
        """(H,W) → (gy,gx) 分块均值。"""
        gx, gy = self.grid
        h, w = a.shape
        bh, bw = h // gy, w // gx
        a = a[: bh * gy, : bw * gx]
        return a.reshape(gy, bh, gx, bw).mean(axis=(1, 3))

    # --------------------------------------------------------------- observe
    def observe(self, frame: Frame, infer_ms: float = 0.0) -> CamHealth:
        now = frame.ts
        g = cv2.cvtColor(frame.image, cv2.COLOR_BGR2GRAY) if frame.image.ndim == 3 else frame.image
        g = cv2.resize(g, self.small, interpolation=cv2.INTER_AREA).astype(np.float32)
        h = self.health
        if self._last_ts is not None:
            dt = max(now - self._last_ts, 1e-3)
            self._fps = 0.8 * self._fps + 0.2 * (1.0 / dt) if self._fps else 1.0 / dt
        self._last_ts = now
        self._lat = 0.8 * self._lat + 0.2 * infer_ms if self._lat else infer_ms
        h.fps, h.latency_ms = self._fps, self._lat
        h.last_frame_age_s = 0.0
        h.offline = False

        h.black = float(g.mean()) < self.black_luma

        if self._prev is not None:
            diff = float(np.abs(g - self._prev).mean())
            if diff < 0.5:
                self._frozen_since = self._frozen_since if self._frozen_since is not None else now
            else:
                self._frozen_since = None
        h.frozen = self._frozen_since is not None and (now - self._frozen_since) >= self.frozen_s

        # 像素时间方差（EMA）→ 静止像素
        if self._mean is None:
            self._mean = g.copy()
            self._var = np.full_like(g, 100.0)
        else:
            a = 0.1
            d = g - self._mean
            self._mean += a * d
            self._var = (1 - a) * (self._var + a * d * d)
        static_px = (self._var < 4.0).astype(np.float32)
        static_block = self._blocks(static_px)
        h.static_ratio = float(static_px.mean()) if self._prev is not None else 0.0

        # 分块清晰度与基线
        lap = cv2.Laplacian(g, cv2.CV_32F)
        sharp_block = self._blocks(lap * lap)
        while self._hist and now - self._hist[0][0] > self.baseline_s:
            self._hist.popleft()
        baseline = np.median(np.stack([b for _, b in self._hist]), axis=0) if len(self._hist) >= 10 else None
        if baseline is not None:
            ratio_block = sharp_block / np.maximum(baseline, 1e-3)
            h.sharpness_ratio = float(np.mean(ratio_block))
            dirty = (ratio_block < self.dirty_sharp_ratio) & (static_block > self.dirty_block_static)
            self.dirty_blocks = dirty
            frac = float(dirty.mean())
            h.lens_dirty = bool(frac >= self.dirty_block_frac and not h.black and not h.frozen)
        else:
            h.sharpness_ratio = 1.0
            h.lens_dirty = False
        healthy = not (h.lens_dirty or h.black or h.frozen)
        if healthy and now - self._last_hist_ts >= self.baseline_step_s:
            self._hist.append((now, sharp_block))
            self._last_hist_ts = now
        self._prev = g
        return h

    def check_offline(self, now: float | None = None) -> CamHealth:
        now = self.clock.now() if now is None else now
        h = self.health
        if self._last_ts is None:
            h.offline = True
            h.last_frame_age_s = float("inf")
        else:
            h.last_frame_age_s = now - self._last_ts
            h.offline = h.last_frame_age_s > self.offline_s
        return h

    def faults(self) -> list[str]:
        """需要上报为"传感器故障"的原因（中文）。"""
        h = self.health
        out = []
        if h.offline:
            out.append("相机离线")
        if h.frozen:
            out.append("画面冻结")
        if h.black:
            out.append("黑屏/遮挡")
        if h.lens_dirty:
            out.append("镜头脏污，请清洁")
        return out
