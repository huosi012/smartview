"""YOLO 系列通用前后处理：letterbox、输出解码（自动识别布局）、numpy NMS。"""

from __future__ import annotations

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore


def letterbox(img: np.ndarray, size: int, color: tuple[int, int, int] = (114, 114, 114)):
    """等比缩放并填充到 size×size。返回 (out, scale, (pad_x, pad_y))。"""
    h, w = img.shape[:2]
    scale = min(size / h, size / w)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    if (nw, nh) != (w, h):
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    else:
        resized = img
    pad_x, pad_y = (size - nw) / 2.0, (size - nh) / 2.0
    left, top = int(round(pad_x - 0.1)), int(round(pad_y - 0.1))
    out = np.full((size, size, 3), color, dtype=img.dtype)
    out[top : top + nh, left : left + nw] = resized
    return out, scale, (float(left), float(top))


def unletterbox(boxes_xyxy: np.ndarray, scale: float, pad: tuple[float, float]) -> np.ndarray:
    b = np.asarray(boxes_xyxy, dtype=np.float32).copy()
    if b.size == 0:
        return b.reshape(0, 4)
    b[:, [0, 2]] -= pad[0]
    b[:, [1, 3]] -= pad[1]
    b /= scale
    return b


def xywh2xyxy(x: np.ndarray) -> np.ndarray:
    y = np.empty_like(x)
    y[:, 0] = x[:, 0] - x[:, 2] / 2
    y[:, 1] = x[:, 1] - x[:, 3] / 2
    y[:, 2] = x[:, 0] + x[:, 2] / 2
    y[:, 3] = x[:, 1] + x[:, 3] / 2
    return y


def decode_yolo(out: np.ndarray, num_classes: int | None = None, conf_thr: float = 0.001):
    """解码 YOLOv5/v8/v11 风格的原始输出。

    支持布局：``(1, 4+nc, N)``（v8/v11 导出默认）、``(1, N, 4+nc)``、``(1, N, 5+nc)``（v5，含 objectness）。
    返回 ``(xyxy[N,4], scores[N], cls[N])``（输入图坐标系，未做 NMS）。
    """
    o = np.asarray(out)
    if o.ndim == 3:
        o = o[0]
    if o.ndim != 2:
        raise ValueError(f"无法解码形状 {out.shape}")
    a, b = o.shape
    # 判定属性轴
    if num_classes is not None:
        cands = {num_classes + 4, num_classes + 5}
        if a in cands and b not in cands:
            o = o.T
        elif b in cands:
            pass
        else:
            raise ValueError(f"输出 {out.shape} 与类别数 {num_classes} 不匹配")
    else:
        if a < b:  # 属性数通常远小于 anchor 数
            o = o.T
    n, attrs = o.shape
    nc = attrs - 4
    v5 = False
    if num_classes is not None:
        v5 = attrs == num_classes + 5
        nc = num_classes
    boxes = xywh2xyxy(o[:, :4].astype(np.float32))
    if v5:
        obj = o[:, 4:5]
        cls_scores = o[:, 5 : 5 + nc] * obj
    else:
        cls_scores = o[:, 4 : 4 + nc]
    if cls_scores.shape[1] == 0:
        return boxes[:0], np.zeros(0, np.float32), np.zeros(0, np.int64)
    cls = cls_scores.argmax(axis=1)
    scores = cls_scores[np.arange(n), cls].astype(np.float32)
    keep = scores >= conf_thr
    return boxes[keep], scores[keep], cls[keep].astype(np.int64)


def box_iou(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """IoU 矩阵 (len(a), len(b))。"""
    a = np.asarray(a, dtype=np.float32).reshape(-1, 4)
    b = np.asarray(b, dtype=np.float32).reshape(-1, 4)
    if a.size == 0 or b.size == 0:
        return np.zeros((len(a), len(b)), dtype=np.float32)
    tl = np.maximum(a[:, None, :2], b[None, :, :2])
    br = np.minimum(a[:, None, 2:], b[None, :, 2:])
    wh = np.clip(br - tl, 0, None)
    inter = wh[..., 0] * wh[..., 1]
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / np.maximum(area_a[:, None] + area_b[None, :] - inter, 1e-9)


def nms_numpy(boxes: np.ndarray, scores: np.ndarray, iou_thr: float = 0.5, class_ids: np.ndarray | None = None) -> np.ndarray:
    """返回保留的索引（按分数降序）。给定 class_ids 时按类别分别抑制。"""
    boxes = np.asarray(boxes, dtype=np.float32).reshape(-1, 4)
    scores = np.asarray(scores, dtype=np.float32)
    if len(boxes) == 0:
        return np.zeros(0, dtype=np.int64)
    if class_ids is not None:
        # 类别偏移技巧：不同类别的框平移到互不重叠的位置
        offs = np.asarray(class_ids, dtype=np.float32)[:, None] * (boxes.max() + 1.0)
        work = boxes + offs
    else:
        work = boxes
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        ious = box_iou(work[i : i + 1], work[order[1:]])[0]
        order = order[1:][ious <= iou_thr]
    return np.asarray(keep, dtype=np.int64)


def clip_boxes(boxes: np.ndarray, width: int, height: int) -> np.ndarray:
    b = np.asarray(boxes, dtype=np.float32).reshape(-1, 4).copy()
    b[:, [0, 2]] = b[:, [0, 2]].clip(0, width - 1)
    b[:, [1, 3]] = b[:, [1, 3]].clip(0, height - 1)
    return b
