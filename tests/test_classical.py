import numpy as np

from smartview.config import SmartViewConfig
from smartview.detect.classical import ClassicalDetector
from smartview.detect.mask import RegionMask
from smartview.detect.postprocess import box_iou
from smartview.geometry.camera import GroundProjector, PinholeCamera
from smartview.synth import make_scene


def _setup(cfg, cam_id):
    cam = cfg.camera(cam_id)
    proj = GroundProjector(cam, cfg.machine)
    region = RegionMask.from_camera(cam)
    det = ClassicalDetector(projector=proj, region=region, conf_thr=cfg.detector.conf_thr)
    return cam, proj, region, det


def _hit(dets, gt_bbox, min_iou=0.15):
    if gt_bbox is None:
        return False
    gt = np.array(gt_bbox, dtype=np.float32)
    for d in dets:
        if box_iou(d.bbox[None], gt[None])[0, 0] >= min_iou:
            return True
        cx, cy = (d.bbox[0] + d.bbox[2]) / 2, (d.bbox[1] + d.bbox[3]) / 2
        if gt[0] - 3 <= cx <= gt[2] + 3 and gt[1] - 3 <= cy <= gt[3] + 3:
            return True
    return False


def test_detects_pipe_in_forward_scene(replay_config_path):
    cfg = SmartViewConfig.load(replay_config_path)
    cam, proj, region, det = _setup(cfg, "fwd")
    scene = make_scene("pipe_forward", PinholeCamera.from_mount(cam.width, cam.height, cam.mount), fps=cam.fps)
    hits = 0
    checked = 0
    for i in range(30, 110, 5):  # 钢管距离 14 m → 3.3 m
        gt = scene.ground_truth(i)[0]
        dets = det.detect(scene.render(i))
        checked += 1
        hits += _hit(dets, gt.bbox)
        assert len(dets) <= 4, f"frame {i}: 误检过多 {len(dets)}"
    assert hits >= checked * 0.8, f"命中 {hits}/{checked}"


def test_detects_stone_in_forward_scene(replay_config_path):
    cfg = SmartViewConfig.load(replay_config_path)
    cam, proj, region, det = _setup(cfg, "fwd")
    scene = make_scene("stone_forward", PinholeCamera.from_mount(cam.width, cam.height, cam.mount), fps=cam.fps)
    hits = sum(_hit(det.detect(scene.render(i)), scene.ground_truth(i)[0].bbox) for i in range(50, 110, 5))
    assert hits >= 9


def test_empty_scene_is_quiet(replay_config_path):
    cfg = SmartViewConfig.load(replay_config_path)
    cam, proj, region, det = _setup(cfg, "fwd")
    scene = make_scene("empty", PinholeCamera.from_mount(cam.width, cam.height, cam.mount), fps=cam.fps)
    total = sum(len(det.detect(scene.render(i))) for i in range(0, 60, 4))
    assert total <= 3


def test_header_mask_removes_self_detections(replay_config_path):
    cfg = SmartViewConfig.load(replay_config_path)
    cam = cfg.camera("hdr_l")
    proj = GroundProjector(cam, cfg.machine)
    scene = make_scene("header_selfview", PinholeCamera.from_mount(cam.width, cam.height, cam.mount), fps=cam.fps)
    img = scene.render(10)
    excl = RegionMask.from_camera(cam)
    no_mask = ClassicalDetector(projector=proj, region=RegionMask(cam.width, cam.height, cam.roi_polygon, []), conf_thr=0.35)
    with_mask = ClassicalDetector(projector=proj, region=excl, conf_thr=0.35)
    dets_raw = no_mask.detect(img)
    assert any(excl.excluded_overlap(d.bbox) > 0.3 for d in dets_raw), "不剔除割台时应在割台区域产生误检"
    dets_masked = with_mask.detect(img)
    assert all(excl.excluded_overlap(d.bbox) <= 0.5 for d in dets_masked)
    assert len(dets_masked) <= 1


def test_header_detects_pipe(replay_config_path):
    cfg = SmartViewConfig.load(replay_config_path)
    cam, proj, region, det = _setup(cfg, "hdr_l")
    scene = make_scene("pipe_header", PinholeCamera.from_mount(cam.width, cam.height, cam.mount), fps=cam.fps)
    hits = sum(_hit(det.detect(scene.render(i)), scene.ground_truth(i)[0].bbox) for i in range(0, 36, 3))
    assert hits >= 9
