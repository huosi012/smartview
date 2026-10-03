import numpy as np

from smartview.detect.postprocess import box_iou, decode_yolo, letterbox, nms_numpy, unletterbox


def test_letterbox_and_unletterbox_round_trip():
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    lb, scale, pad = letterbox(img, 640)
    assert lb.shape == (640, 640, 3) and scale == 1.0 and pad == (0.0, 140.0)
    boxes = np.array([[100, 150, 200, 250]], dtype=np.float32)  # letterbox 坐标
    back = unletterbox(boxes, scale, pad)
    assert np.allclose(back, [[100, 10, 200, 110]])
    img2 = np.zeros((720, 1280, 3), dtype=np.uint8)
    lb2, scale2, pad2 = letterbox(img2, 640)
    assert lb2.shape[0] == 640 and abs(scale2 - 0.5) < 1e-9 and pad2 == (0.0, 140.0)


def test_nms_suppresses_overlaps_but_keeps_other_classes():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype=np.float32)
    scores = np.array([0.9, 0.8, 0.7], dtype=np.float32)
    keep = nms_numpy(boxes, scores, 0.5)
    assert keep.tolist() == [0, 2]
    keep_cls = nms_numpy(boxes, scores, 0.5, class_ids=np.array([0, 1, 0]))
    assert sorted(keep_cls.tolist()) == [0, 1, 2]
    assert box_iou(boxes[:1], boxes[1:2])[0, 0] > 0.6


def _planted(layout: str, nc: int = 80, n: int = 8400, v5: bool = False):
    attrs = nc + (5 if v5 else 4)
    arr = np.zeros((attrs, n), dtype=np.float32)
    arr[0, 7] = 320
    arr[1, 7] = 200
    arr[2, 7] = 50
    arr[3, 7] = 100
    if v5:
        arr[4, 7] = 0.9
        arr[5 + 2, 7] = 1.0
    else:
        arr[4 + 2, 7] = 0.9
    arr = arr[None]
    return arr if layout == "cn" else np.ascontiguousarray(arr.transpose(0, 2, 1))


def test_decode_both_layouts_and_v5():
    for layout in ("cn", "nc"):
        boxes, scores, cls = decode_yolo(_planted(layout), num_classes=80, conf_thr=0.5)
        assert len(boxes) == 1 and cls[0] == 2 and abs(scores[0] - 0.9) < 1e-6
        assert np.allclose(boxes[0], [295, 150, 345, 250])
    boxes, scores, cls = decode_yolo(_planted("nc", v5=True), num_classes=80, conf_thr=0.5)
    assert len(boxes) == 1 and cls[0] == 2 and abs(scores[0] - 0.9) < 1e-6
    # 未给类别数时按"属性轴较短"推断
    boxes, _, _ = decode_yolo(_planted("cn"), conf_thr=0.5)
    assert len(boxes) == 1
