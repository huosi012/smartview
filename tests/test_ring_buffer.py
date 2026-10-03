import cv2
import numpy as np

from smartview.storage import RingBuffer, write_clip
from smartview.storage.ring_buffer import prune_dir, write_snapshot


def _img(i):
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    img[:, :, 1] = (i * 5) % 255
    return img


def test_ring_subsamples_and_snapshot_window():
    ring = RingBuffer(seconds=4.0, fps=10.0, max_width=320)
    for i in range(120):  # 30 fps × 4 s
        ring.push(i / 30.0, _img(i))
    assert 38 <= len(ring) <= 42
    assert ring.size == (320, 180)
    win = ring.snapshot(1.0, 2.0)
    assert 9 <= len(win) <= 12 and all(1.0 <= t <= 2.0 for t, _ in win)
    assert ring.latest()[0] >= 3.9


def test_write_clip_and_snapshot(tmp_path):
    ring = RingBuffer(seconds=5.0, fps=10.0, max_width=640)
    for i in range(50):
        ring.push(i / 10.0, _img(i))
    frames = ring.snapshot(0.0, 2.95)
    path = write_clip(tmp_path / "clip", frames, fps=10.0)
    assert path is not None and path.exists() and path.suffix == ".avi"
    cap = cv2.VideoCapture(str(path))
    n = 0
    while True:
        ok, _ = cap.read()
        if not ok:
            break
        n += 1
    cap.release()
    assert n == len(frames) == 30
    snap = write_snapshot(tmp_path / "snap", ring.latest()[1])
    assert snap.exists() and snap.stat().st_size > 1000
    assert write_clip(tmp_path / "empty", [], 10.0) is None


def test_prune_dir(tmp_path):
    for i in range(5):
        (tmp_path / f"f{i}.bin").write_bytes(b"x" * 1000)
        import os
        import time

        os.utime(tmp_path / f"f{i}.bin", (time.time() + i, time.time() + i))
    removed = prune_dir(tmp_path, 2500)
    assert removed == 3 and sorted(p.name for p in tmp_path.iterdir()) == ["f3.bin", "f4.bin"]
