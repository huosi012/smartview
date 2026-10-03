import math

import numpy as np
import pytest

from smartview.clock import ReplayClock
from smartview.config import CameraConfig, MachineConfig
from smartview.geometry import (
    GroundProjector,
    ManualSpeed,
    NmeaSpeed,
    PinholeCamera,
    estimate_range_rate,
    time_to_contact,
)
from smartview.types import Track

FWD = dict(width=640, height=360, hfov_deg=60, x_fwd_m=-2.5, y_lat_m=0.0, z_m=3.2, pitch_deg=15)


def test_ground_round_trip_forward_camera():
    cam = PinholeCamera.from_fov(**FWD)
    for x in np.linspace(4.5, 25.0, 12):
        for y in np.linspace(-3.0, 3.0, 7):
            uv = cam.ground_to_image(x, y)
            assert uv is not None
            back = cam.image_to_ground(*uv)
            assert back is not None
            assert math.isclose(back[0], x, abs_tol=1e-6)
            assert math.isclose(back[1], y, abs_tol=1e-6)


def test_round_trip_with_yaw_and_roll():
    cam = PinholeCamera.from_fov(640, 360, 100, x_fwd_m=0.3, y_lat_m=0.6, z_m=0.5, pitch_deg=25, yaw_deg=8, roll_deg=-3)
    for x in (0.6, 1.0, 2.0, 3.5):
        for y in (-0.5, 0.0, 0.9):
            uv = cam.ground_to_image(x, y)
            assert uv is not None
            back = cam.image_to_ground(*uv)
            assert back is not None and np.allclose(back, (x, y), atol=1e-6)


def test_horizon_and_above_horizon_is_none():
    cam = PinholeCamera.from_fov(**FWD)
    hv = cam.horizon_v()
    expected = cam.cy - cam.fy * math.tan(math.radians(15))
    assert math.isclose(hv, expected, abs_tol=1e-6)
    assert cam.image_to_ground(cam.cx, hv - 5) is None
    assert cam.image_to_ground(cam.cx, hv + 5) is not None
    # 俯角 15°、离地 3.2 m 的前视相机：可见地面从约 2.4 m（距割台前缘）开始
    near, far = cam.ground_visible_range()
    assert 1.5 < near < 3.5 and far is None


def test_pixel_scale_matches_hardware_doc_numbers():
    # 1920 px / 60° 前视：15 m 处约 0.9 cm/px → Ø219 mm 钢管约 24 px 宽
    cam = PinholeCamera.from_fov(1920, 1080, 60, x_fwd_m=-2.5, z_m=3.2, pitch_deg=15)
    x = 15.0 - 2.5  # 距割台前缘 12.5 m = 距相机 15 m
    lp = cam.ground_to_image(x, -0.1095)
    rp = cam.ground_to_image(x, 0.1095)
    assert lp and rp
    assert 20 < abs(lp[0] - rp[0]) < 28
    h = cam.object_height_px(x, 0.0, 0.5)
    assert h is not None and 40 < h < 70


def test_analytic_homography_matches_dlt():
    cv2 = pytest.importorskip("cv2")
    cam = PinholeCamera.from_fov(**FWD)
    ground = np.array([[5.0, -2.0], [5.0, 2.0], [15.0, 2.5], [15.0, -2.5]], dtype=np.float32)
    px = np.array([cam.ground_to_image(x, y) for x, y in ground], dtype=np.float32)
    H_dlt = cv2.getPerspectiveTransform(px, ground)
    H_an = cam.ground_homography()
    H_dlt = H_dlt / H_dlt[2, 2]
    H_an = H_an / H_an[2, 2]
    assert np.allclose(H_dlt, H_an, atol=1e-3)


def test_projector_homography_path_equals_mount_path():
    machine = MachineConfig()
    cam_cfg = CameraConfig(id="fwd", role="forward", width=640, height=360, mount={**{k: v for k, v in FWD.items() if k not in ("width", "height")}})
    p_mount = GroundProjector(cam_cfg, machine)
    H = p_mount.camera.ground_homography().tolist()
    cam_cfg_h = cam_cfg.model_copy(update={"homography": H})
    p_h = GroundProjector(cam_cfg_h, machine)
    for u, v in [(320, 300), (100, 350), (500, 250), (320, 200)]:
        a, b = p_mount.image_to_ground(u, v), p_h.image_to_ground(u, v)
        assert a is not None and b is not None
        assert np.allclose(a, b, atol=1e-4)
    assert p_h.image_to_ground(320, 10) is None  # 地平线以上


def test_projector_for_other_resolution():
    machine = MachineConfig()
    cam_cfg = CameraConfig(id="fwd", role="forward", width=640, height=360, mount={**{k: v for k, v in FWD.items() if k not in ("width", "height")}})
    p = GroundProjector(cam_cfg, machine)
    p2 = p.for_size(1280, 720)
    a = p.image_to_ground(320, 300)
    b = p2.image_to_ground(640, 600)
    assert a is not None and b is not None and np.allclose(a, b, atol=1e-6)


def test_rows_and_path():
    machine = MachineConfig(n_rows=4, row_spacing_m=0.6, header_width_m=2.4, path_margin_m=0.3)
    cam_cfg = CameraConfig(id="fwd", role="forward")
    p = GroundProjector(cam_cfg, machine)
    assert p.row_of(0.9) == 0 and p.row_of(0.3) == 1 and p.row_of(-0.3) == 2 and p.row_of(-0.9) == 3
    assert p.row_of(1.5) == -1 and p.row_of(-1.5) == 4
    assert p.in_path(1.4) and not p.in_path(1.6)
    assert p.is_adjacent(2.0) and not p.is_adjacent(2.6)


def test_annotate_track():
    machine = MachineConfig()
    cam_cfg = CameraConfig(id="fwd", role="forward", width=640, height=360, mount={**{k: v for k, v in FWD.items() if k not in ("width", "height")}})
    p = GroundProjector(cam_cfg, machine)
    uv = p.ground_to_image(10.0, 0.5)
    assert uv is not None
    u, v = uv
    tr = Track(track_id=1, cam_id="fwd", cls_id=0, cls_name="stone", bbox=np.array([u - 10, v - 20, u + 10, v]), score=0.9)
    gp = p.annotate(tr)
    assert gp is not None and math.isclose(gp.x_fwd, 10.0, abs_tol=1e-6) and gp.in_path and gp.row == 1
    assert p.expected_height_px(v, 0.5) is not None


def test_ttc_and_range_rate():
    assert time_to_contact(10.0, 2.0) == 5.0
    assert time_to_contact(10.0, 0.0, 0.3) == pytest.approx(10.0 / 0.3)
    assert time_to_contact(None, 2.0) is None
    samples = [(t, 20.0 - 2.0 * t) for t in np.linspace(0, 1.0, 16)]
    assert estimate_range_rate(samples, window_s=0.5) == pytest.approx(-2.0, abs=1e-6)
    assert estimate_range_rate(samples[:2]) is None


def test_nmea_speed_parse_and_stale():
    clk = ReplayClock(100.0)
    manual = ManualSpeed(1.0)
    n = NmeaSpeed("/dev/null", 9600, fallback=manual, stale_s=3.0, clock=clk)
    assert n.quality == "stale" and n.speed_mps() == 1.0
    n.feed("$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A")
    assert n.quality == "ok" and n.speed_mps() == pytest.approx(22.4 * 0.514444)
    n.feed("$GNRMC,123520,V,,,,,000.0,,230394,,,N*53")  # 无效定位被忽略
    assert n.speed_mps() == pytest.approx(22.4 * 0.514444)
    clk.advance(3.5)
    assert n.quality == "stale" and n.speed_mps() == 1.0
