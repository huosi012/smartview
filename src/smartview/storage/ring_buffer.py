"""JPEG 环形缓存（事件前滚）与片段写出。"""

from __future__ import annotations

import threading
from collections import deque
from pathlib import Path

import cv2
import numpy as np


class RingBuffer:
    def __init__(self, seconds: float = 8.0, fps: float = 10.0, max_width: int = 960, jpeg_quality: int = 70) -> None:
        self.seconds = seconds
        self.fps = fps
        self.max_width = max_width
        self.jpeg_quality = jpeg_quality
        self._buf: deque[tuple[float, bytes]] = deque(maxlen=max(2, int(seconds * fps) + 2))
        self._last_ts: float | None = None
        self._lock = threading.Lock()
        self.size: tuple[int, int] | None = None

    def encode(self, image: np.ndarray) -> bytes:
        h, w = image.shape[:2]
        if w > self.max_width:
            s = self.max_width / w
            image = cv2.resize(image, (self.max_width, int(round(h * s))), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
        if not ok:
            raise RuntimeError("JPEG 编码失败")
        self.size = (image.shape[1], image.shape[0])
        return buf.tobytes()

    def push(self, ts: float, image: np.ndarray, jpeg: bytes | None = None) -> bytes | None:
        """按 ring fps 抽样写入；返回本次编码的 JPEG（未抽中返回 None）。"""
        with self._lock:
            if self._last_ts is not None and ts - self._last_ts < (1.0 / self.fps) * 0.98:
                return None
            self._last_ts = ts
        data = jpeg if jpeg is not None else self.encode(image)
        with self._lock:
            self._buf.append((ts, data))
        return data

    def snapshot(self, t_from: float, t_to: float) -> list[tuple[float, bytes]]:
        with self._lock:
            return [(t, b) for t, b in self._buf if t_from <= t <= t_to]

    def latest(self) -> tuple[float, bytes] | None:
        with self._lock:
            return self._buf[-1] if self._buf else None

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)


def write_clip(path: str | Path, frames: list[tuple[float, bytes]], fps: float) -> Path | None:
    """把 JPEG 帧序列写成 MJPG AVI（pip 版 OpenCV 均可用；Jetson 可改用 GStreamer H.264）。"""
    if not frames:
        return None
    path = Path(path).with_suffix(".avi")
    path.parent.mkdir(parents=True, exist_ok=True)
    first = cv2.imdecode(np.frombuffer(frames[0][1], np.uint8), cv2.IMREAD_COLOR)
    h, w = first.shape[:2]
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), max(fps, 1.0), (w, h))
    if not writer.isOpened():
        return None
    try:
        for _ts, b in frames:
            img = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                continue
            if img.shape[:2] != (h, w):
                img = cv2.resize(img, (w, h))
            writer.write(img)
    finally:
        writer.release()
    return path


def write_snapshot(path: str | Path, jpeg: bytes) -> Path:
    path = Path(path).with_suffix(".jpg")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(jpeg)
    return path


def prune_dir(directory: str | Path, max_bytes: float) -> int:
    """按最旧优先删除，直到目录总大小不超过 max_bytes；返回删除文件数。"""
    d = Path(directory)
    if not d.exists():
        return 0
    files = sorted((p for p in d.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in files)
    removed = 0
    for p in files:
        if total <= max_bytes:
            break
        total -= p.stat().st_size
        p.unlink(missing_ok=True)
        removed += 1
    return removed
