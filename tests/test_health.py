import cv2
import numpy as np

from smartview.clock import ReplayClock
from smartview.health import HealthMonitor
from smartview.types import Frame


def _moving(i, rng):
    img = np.zeros((180, 320, 3), dtype=np.uint8)
    img[:] = (60, 85, 115)
    # 流动的条纹 + 噪声，模拟地面前进
    xs = (np.arange(320) + i * 7) % 40
    img[:, xs < 20] = (78, 108, 142)
    img = (img.astype(np.int16) + rng.integers(-8, 8, img.shape)).clip(0, 255).astype(np.uint8)
    return img


def test_fps_frozen_black_offline():
    clk = ReplayClock(0.0)
    hm = HealthMonitor("c", clock=clk, frozen_s=1.0, offline_s=1.0)
    rng = np.random.default_rng(0)
    for i in range(30):
        hm.observe(Frame("c", i, i / 15.0, _moving(i, rng)), infer_ms=5.0)
    h = hm.health
    assert 13 < h.fps < 17 and not h.frozen and not h.black and h.ok and h.status_zh == "正常"
    frozen = _moving(99, rng)
    for i in range(30, 50):
        hm.observe(Frame("c", i, i / 15.0, frozen))
    assert hm.health.frozen and "画面冻结" in hm.faults()
    hm.observe(Frame("c", 50, 50 / 15.0, np.zeros((180, 320, 3), np.uint8)))
    assert hm.health.black
    assert hm.check_offline(now=50 / 15.0 + 0.5).offline is False
    assert hm.check_offline(now=50 / 15.0 + 2.0).offline is True and "相机离线" in hm.faults()


def test_lens_dirty_detection():
    clk = ReplayClock(0.0)
    hm = HealthMonitor("c", clock=clk, baseline_s=60.0, baseline_step_s=0.2)
    rng = np.random.default_rng(1)
    for i in range(60):
        hm.observe(Frame("c", i, i / 15.0, _moving(i, rng)))
    assert not hm.health.lens_dirty
    # 镜头上附着大片静止泥污：画面大面积模糊且不随地面移动
    for i in range(60, 120):
        img = _moving(i, rng)
        blur = cv2.GaussianBlur(img, (0, 0), 6)
        img[40:150, 60:260] = blur[40:150, 60:260]
        img[40:150, 60:260] = (img[40:150, 60:260] * 0.2 + np.array([90, 95, 100]) * 0.8).astype(np.uint8)
        hm.observe(Frame("c", i, i / 15.0, img))
    h = hm.health
    assert h.sharpness_ratio < 0.8 and h.static_ratio > 0.15 and h.lens_dirty
    assert hm.dirty_blocks is not None and hm.dirty_blocks.mean() >= 0.15
    assert "镜头脏污，请清洁" in hm.faults() and h.status_zh == "镜头脏污"
