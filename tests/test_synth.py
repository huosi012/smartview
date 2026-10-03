import hashlib

import numpy as np

from smartview.capture import SyntheticSource, build_source
from smartview.config import SmartViewConfig
from smartview.geometry.camera import PinholeCamera
from smartview.synth import SCENARIOS, make_scene


def _fwd_cam():
    return PinholeCamera.from_fov(640, 360, 60, x_fwd_m=-2.5, z_m=3.2, pitch_deg=15)


def _hdr_cam():
    return PinholeCamera.from_fov(640, 360, 100, x_fwd_m=0.3, y_lat_m=0.6, z_m=0.5, pitch_deg=25)


def test_scene_is_deterministic():
    a = make_scene("pipe_forward", _fwd_cam(), seed=3)
    b = make_scene("pipe_forward", _fwd_cam(), seed=3)
    fa, fb = a.render(10), b.render(10)
    assert fa.shape == (360, 640, 3) and fa.dtype == np.uint8
    assert hashlib.md5(fa.tobytes()).hexdigest() == hashlib.md5(fb.tobytes()).hexdigest()
    c = make_scene("pipe_forward", _fwd_cam(), seed=4)
    assert hashlib.md5(c.render(10).tobytes()).hexdigest() != hashlib.md5(fa.tobytes()).hexdigest()


def test_ground_truth_moves_toward_camera_and_bbox_grows():
    sc = make_scene("pipe_forward", _fwd_cam())
    gts = [sc.ground_truth(i)[0] for i in range(sc.n_frames)]
    assert gts[0].x_fwd == 18.0
    assert gts[-1].x_fwd < gts[0].x_fwd
    vis = [g for g in gts if g.visible]
    assert len(vis) > sc.n_frames // 2
    h0 = vis[0].bbox[3] - vis[0].bbox[1]
    h1 = vis[-1].bbox[3] - vis[-1].bbox[1]
    assert h1 > h0 * 2
    # 真值框在图内，且底边与几何一致（脚点反投影回到真值距离附近）
    g = vis[len(vis) // 2]
    x1, y1, x2, y2 = g.bbox
    assert 0 <= x1 < x2 < 640 and 0 <= y1 < y2 < 360
    back = sc.camera.image_to_ground((x1 + x2) / 2, y2)
    assert back is not None and abs(back[0] - g.x_fwd) < 0.4


def test_header_scene_has_static_header_region():
    sc = make_scene("header_selfview", _hdr_cam())
    f0, f1 = sc.render(0), sc.render(20)
    # 底部割台区域静止：差异极小；上方地面区域随前进变化
    bottom = np.abs(f0[340:, 200:440].astype(int) - f1[340:, 200:440].astype(int)).mean()
    ground = np.abs(f0[200:260, 200:440].astype(int) - f1[200:260, 200:440].astype(int)).mean()
    assert bottom < 6.0
    assert ground > bottom * 2


def test_all_scenarios_render_first_frame():
    for name in SCENARIOS:
        cam = _hdr_cam() if SCENARIOS[name]["header_overlay"] else _fwd_cam()
        sc = make_scene(name, cam, duration_s=0.2)
        img = sc.render(0)
        assert img.shape == (360, 640, 3)


def test_synthetic_source_from_config(replay_config_path):
    cfg = SmartViewConfig.load(replay_config_path)
    src = build_source(cfg.camera("fwd"), cfg.speed)
    assert isinstance(src, SyntheticSource)
    with src:
        f0 = src.read()
        f1 = src.read()
    assert f0 is not None and f1 is not None
    assert f0.cam_id == "fwd" and f0.seq == 0 and f1.ts > f0.ts
    assert f0.image.shape == (360, 640, 3)
    # 车速取自配置（manual）
    assert src.scene.cfg.speed_mps == cfg.speed.manual_mps
