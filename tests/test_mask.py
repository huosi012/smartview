import numpy as np

from smartview.config import CameraConfig
from smartview.detect.mask import RegionMask
from smartview.types import Detection


def _det(x1, y1, x2, y2):
    return Detection(bbox=np.array([x1, y1, x2, y2], dtype=np.float32), score=0.9, cls_id=0, cls_name="stone")


def test_effective_region_is_roi_minus_exclusions():
    m = RegionMask(100, 100, roi_polygon=[(0, 1), (0.2, 0), (0.8, 0), (1, 1)], exclude_polygons=[[(0, 1), (0, 0.8), (1, 0.8), (1, 1)]])
    assert m.contains(50, 50)
    assert not m.contains(50, 95)  # 排除区（割台）
    assert not m.contains(2, 5)  # ROI 外
    assert m.has_exclusions


def test_filter_drops_header_detections():
    m = RegionMask(100, 100, exclude_polygons=[[(0, 1), (0, 0.8), (1, 0.8), (1, 1)]])
    keep = m.filter([_det(10, 10, 30, 40), _det(10, 70, 30, 95), _det(40, 82, 60, 99)])
    assert len(keep) == 1 and keep[0].bbox[1] == 10
    # 框大部分在排除区但脚点被夹到画面内：按重叠比例剔除
    assert m.excluded_overlap(np.array([40, 82, 60, 99])) > 0.9


def test_from_camera_and_png_mask(tmp_path):
    import cv2

    png = tmp_path / "excl.png"
    img = np.zeros((36, 64), dtype=np.uint8)
    img[30:, :] = 255
    cv2.imwrite(str(png), img)
    cam = CameraConfig(id="h", role="header", width=640, height=360, exclude_mask_png=str(png))
    m = RegionMask.from_camera(cam)
    assert m.excluded.shape == (360, 640)
    assert m.contains(320, 100) and not m.contains(320, 350)
    m2 = m.for_size(320, 180)
    assert m2.contains(160, 50) and not m2.contains(160, 175)
    over = m.overlay(np.zeros((360, 640, 3), dtype=np.uint8))
    assert over[350, 320, 2] > 0
