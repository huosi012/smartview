"""地面单应性标定（像素 → 车体地面坐标）。

现场流程：在相机前方地面摆放 ≥4 个标志物（建议 5 / 10 / 15 / 20 m 处、左右各一，覆盖关注区），
用卷尺 / RTK 量出每个标志物相对割台前缘中心的 (x_fwd, y_lat)，在图像中点出对应像素，求解 H。
"""

from __future__ import annotations

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore


def solve_homography(pixels: list[tuple[float, float]], ground: list[tuple[float, float]]) -> tuple[np.ndarray, float]:
    """返回 (H 3x3 像素→地面, 重投影 RMS 误差 m)。至少 4 组点；>4 组时最小二乘（RANSAC 关闭以保证可复现）。"""
    if len(pixels) != len(ground) or len(pixels) < 4:
        raise ValueError("至少需要 4 组对应点")
    src = np.asarray(pixels, dtype=np.float64).reshape(-1, 1, 2)
    dst = np.asarray(ground, dtype=np.float64).reshape(-1, 1, 2)
    H, _ = cv2.findHomography(src, dst, 0)
    if H is None:
        raise ValueError("单应性求解失败（点共线？）")
    H = H / H[2, 2]
    proj = cv2.perspectiveTransform(src, H).reshape(-1, 2)
    rms = float(np.sqrt(np.mean(np.sum((proj - dst.reshape(-1, 2)) ** 2, axis=1))))
    return H, rms


def parse_points(spec: str) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """解析 ``"u,v,x,y;u,v,x,y;..."``。"""
    px, gd = [], []
    for item in spec.split(";"):
        item = item.strip()
        if not item:
            continue
        u, v, x, y = (float(t) for t in item.split(","))
        px.append((u, v))
        gd.append((x, y))
    return px, gd
