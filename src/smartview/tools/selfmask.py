"""自动学习"自身区域"（割台 / 分禾器 / 机身）遮罩。

原理：车辆行驶时地面与作物在画面中流动，而固定在相机前方的割台部件几乎不动。
统计一段行驶视频中每个像素的"静止比例"与时间标准差，静止且低方差的连通区域即为自身区域；
再做形态学整理、去小块，并转成归一化多边形写回配置的 ``exclude_polygons``。

用法::

    smartview calib-mask --video header_drive.mp4 --out configs/masks/hdr_l.png
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import cv2
import numpy as np


def learn_static_mask(
    frames: Iterable[np.ndarray],
    motion_thr: float = 3.0,
    static_frac: float = 0.97,
    max_std: float = 8.0,
    small_w: int = 320,
    min_area_frac: float = 0.002,
    require_border: bool = True,
) -> tuple[np.ndarray, int]:
    """返回 (mask uint8 255=自身区域, 使用的帧数)。mask 尺寸为缩略尺寸 (small_w × h')。"""
    prev = None
    n = 0
    static_cnt = None
    mean = None
    m2 = None
    for img in frames:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        h, w = g.shape
        if w != small_w:
            g = cv2.resize(g, (small_w, int(round(h * small_w / w))), interpolation=cv2.INTER_AREA)
        g = g.astype(np.float32)
        if prev is None:
            static_cnt = np.zeros_like(g)
            mean = g.copy()
            m2 = np.zeros_like(g)
            prev = g
            n = 1
            continue
        n += 1
        static_cnt += (np.abs(g - prev) < motion_thr).astype(np.float32)
        delta = g - mean
        mean += delta / n
        m2 += delta * (g - mean)
        prev = g
    if prev is None or n < 3:
        raise ValueError("帧数不足（至少 3 帧）")
    std = np.sqrt(m2 / max(n - 1, 1))
    mask = ((static_cnt / (n - 1)) >= static_frac) & (std <= max_std)
    m = (mask.astype(np.uint8)) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    cnt, labels, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    out = np.zeros_like(m)
    hh, ww = m.shape
    min_area = min_area_frac * hh * ww
    for i in range(1, cnt):
        x, y, bw, bh, area = stats[i]
        if area < min_area:
            continue
        touches = x == 0 or y + bh >= hh or x + bw >= ww or y == 0
        if require_border and not touches:
            continue
        out[labels == i] = 255
    return out, n


def mask_to_polygons(mask: np.ndarray, epsilon_frac: float = 0.01, min_area_frac: float = 0.002) -> list[list[tuple[float, float]]]:
    """二值遮罩 → 归一化多边形列表（可直接写入 exclude_polygons）。"""
    h, w = mask.shape[:2]
    contours, _ = cv2.findContours((mask > 127).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polys = []
    for c in contours:
        if cv2.contourArea(c) < min_area_frac * h * w:
            continue
        eps = epsilon_frac * cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, eps, True).reshape(-1, 2)
        if len(approx) < 3:
            continue
        poly = [(round(float(x) / (w - 1), 4), round(float(y) / (h - 1), 4)) for x, y in approx]
        poly = [(min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)) for x, y in poly]
        polys.append(poly)
    return polys


def dilate_mask(mask: np.ndarray, margin_frac: float = 0.01) -> np.ndarray:
    """给遮罩加安全裕量（相机抖动）。"""
    k = max(1, int(round(margin_frac * max(mask.shape))))
    return cv2.dilate(mask, np.ones((2 * k + 1, 2 * k + 1), np.uint8))


def iter_video(path: str | Path, max_frames: int = 300, stride: int = 1):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"无法打开 {path}")
    i = 0
    used = 0
    try:
        while used < max_frames:
            ok, img = cap.read()
            if not ok:
                break
            if i % stride == 0:
                used += 1
                yield img
            i += 1
    finally:
        cap.release()


def learn_from_video(path: str | Path, max_frames: int = 300, stride: int = 1, margin_frac: float = 0.01):
    frames = list(iter_video(path, max_frames, stride))
    if not frames:
        raise ValueError("视频为空")
    mask, n = learn_static_mask(frames)
    mask = dilate_mask(mask, margin_frac)
    h, w = frames[0].shape[:2]
    full = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
    polys = mask_to_polygons(full)
    preview = frames[len(frames) // 2].copy()
    red = np.zeros_like(preview)
    red[..., 2] = 255
    sel = full > 127
    preview[sel] = (preview[sel] * 0.55 + red[sel] * 0.45).astype(np.uint8)
    for poly in polys:
        pts = np.array([(x * (w - 1), y * (h - 1)) for x, y in poly], dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(preview, [pts], True, (0, 255, 255), 2)
    return full, polys, preview, n
