import numpy as np

from smartview.config import SmartViewConfig
from smartview.detect.mask import RegionMask
from smartview.geometry.camera import PinholeCamera
from smartview.synth import make_scene
from smartview.tools.selfmask import learn_static_mask, mask_to_polygons


def test_learn_header_mask_from_synthetic_drive(replay_config_path):
    cfg = SmartViewConfig.load(replay_config_path)
    cam = cfg.camera("hdr_l")
    scene = make_scene("header_selfview", PinholeCamera.from_mount(cam.width, cam.height, cam.mount), fps=cam.fps)
    frames = [scene.render(i) for i in range(0, 45)]
    mask, n = learn_static_mask(frames)
    assert n == 45
    import cv2

    full = cv2.resize(mask, (cam.width, cam.height), interpolation=cv2.INTER_NEAREST) > 127
    # 真值：场景渲染的割台多边形
    truth = RegionMask(cam.width, cam.height, None, [scene.default_header_polygon()]).excluded.astype(bool)
    inter = (full & truth).sum()
    assert inter / truth.sum() >= 0.85, "学到的遮罩应覆盖绝大部分割台区域"
    ground = ~truth
    ground[: int(cam.height * 0.5)] = False  # 只看割台上方的近处地面
    assert (full & ground).sum() / ground.sum() <= 0.05, "学到的遮罩不应覆盖流动的地面"
    polys = mask_to_polygons((full * 255).astype(np.uint8))
    assert polys and all(0 <= x <= 1 and 0 <= y <= 1 for poly in polys for x, y in poly)
