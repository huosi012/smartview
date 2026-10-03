"""ByteTrackLite：两段贪心 IoU 关联 + 常速预测的轻量多目标跟踪（纯 numpy）。

* 第一段：高分检测（score ≥ conf_high）与所有轨迹按 IoU 匹配（阈值 iou_high）；
* 第二段：剩余轨迹与低分检测（conf_low ≤ score < conf_high）匹配（阈值 iou_low），
  用于遮挡 / 粉尘导致分数下降时保持 ID；
* 未匹配的高分检测新建轨迹；连续 ``min_hits`` 次命中后确认；连续 ``max_age`` 次丢失后删除。
* 远处小目标（边长 ≤ ``small_px``）的框只有几个像素，IoU 对抖动极其敏感，因此对小框额外使用
  中心距离亲和度 ``1 - dist / small_dist_px`` 兜底，避免轨迹反复断裂、确认时间被拖长。
``update()`` 只返回已确认的轨迹。
"""

from __future__ import annotations

from collections import deque

import numpy as np

from smartview.detect.postprocess import box_iou
from smartview.types import Detection, Track


class _State:
    __slots__ = ("track", "vel", "last_bbox")

    def __init__(self, track: Track) -> None:
        self.track = track
        self.vel = np.zeros(4, dtype=np.float32)  # 每帧 xyxy 变化
        self.last_bbox = track.bbox.astype(np.float32).copy()


class ByteTrackLite:
    def __init__(
        self,
        cam_id: str = "",
        conf_high: float = 0.5,
        conf_low: float = 0.1,
        iou_high: float = 0.3,
        iou_low: float = 0.4,
        min_hits: int = 3,
        max_age: int = 10,
        vel_alpha: float = 0.5,
        history_len: int = 30,
        small_px: float = 24.0,
        small_dist_px: float = 12.0,
    ) -> None:
        self.cam_id = cam_id
        self.conf_high, self.conf_low = conf_high, conf_low
        self.iou_high, self.iou_low = iou_high, iou_low
        self.min_hits, self.max_age = min_hits, max_age
        self.vel_alpha = vel_alpha
        self.history_len = history_len
        self.small_px = small_px
        self.small_dist_px = small_dist_px
        self._states: list[_State] = []
        self._next_id = 1

    # ---------------------------------------------------------------- helpers
    @property
    def tracks(self) -> list[Track]:
        return [s.track for s in self._states]

    def _predict(self) -> np.ndarray:
        if not self._states:
            return np.zeros((0, 4), dtype=np.float32)
        return np.stack([s.last_bbox + s.vel for s in self._states]).astype(np.float32)

    def _affinity(self, pred: np.ndarray, det_boxes: np.ndarray) -> np.ndarray:
        """IoU 为主；双方都是小框时用中心距离亲和度兜底。"""
        aff = box_iou(pred, det_boxes)
        if aff.size == 0:
            return aff
        side_p = np.maximum(pred[:, 2] - pred[:, 0], pred[:, 3] - pred[:, 1])
        side_d = np.maximum(det_boxes[:, 2] - det_boxes[:, 0], det_boxes[:, 3] - det_boxes[:, 1])
        small = (side_p[:, None] <= self.small_px) & (side_d[None, :] <= self.small_px)
        if small.any():
            cp = np.stack([(pred[:, 0] + pred[:, 2]) / 2, (pred[:, 1] + pred[:, 3]) / 2], axis=1)
            cd = np.stack([(det_boxes[:, 0] + det_boxes[:, 2]) / 2, (det_boxes[:, 1] + det_boxes[:, 3]) / 2], axis=1)
            dist = np.linalg.norm(cp[:, None, :] - cd[None, :, :], axis=2)
            da = np.clip(1.0 - dist / self.small_dist_px, 0.0, 1.0)
            aff = np.where(small, np.maximum(aff, da), aff)
        return aff

    @staticmethod
    def _greedy(iou: np.ndarray, thr: float) -> list[tuple[int, int]]:
        pairs: list[tuple[int, int]] = []
        if iou.size == 0:
            return pairs
        iou = iou.copy()
        while True:
            i, j = np.unravel_index(int(iou.argmax()), iou.shape)
            if iou[i, j] < thr:
                break
            pairs.append((int(i), int(j)))
            iou[i, :] = -1
            iou[:, j] = -1
        return pairs

    def _apply(self, st: _State, det: Detection, ts: float) -> None:
        tr = st.track
        new = det.bbox.astype(np.float32)
        st.vel = (1 - self.vel_alpha) * st.vel + self.vel_alpha * (new - st.last_bbox)
        st.last_bbox = new.copy()
        tr.bbox = new
        tr.score = float(det.score)
        tr.cls_id, tr.cls_name = det.cls_id, det.cls_name
        tr.hits += 1
        tr.misses = 0
        tr.last_ts = ts
        tr.history.append((ts, new.copy()))
        if tr.hits >= self.min_hits:
            tr.confirmed = True

    def _new(self, det: Detection, ts: float) -> None:
        tr = Track(
            track_id=self._next_id,
            cam_id=self.cam_id,
            cls_id=det.cls_id,
            cls_name=det.cls_name,
            bbox=det.bbox.astype(np.float32).copy(),
            score=float(det.score),
            hits=1,
            age=1,
            misses=0,
            history=deque(maxlen=self.history_len),
            last_ts=ts,
            confirmed=self.min_hits <= 1,
        )
        tr.history.append((ts, tr.bbox.copy()))
        self._next_id += 1
        self._states.append(_State(tr))

    # ----------------------------------------------------------------- update
    def update(self, dets: list[Detection], ts: float) -> list[Track]:
        for s in self._states:
            s.track.age += 1
        pred = self._predict()
        high = [d for d in dets if d.score >= self.conf_high]
        low = [d for d in dets if self.conf_low <= d.score < self.conf_high]
        unmatched_states = list(range(len(self._states)))

        if high and self._states:
            iou = self._affinity(pred, np.stack([d.bbox for d in high]))
            pairs = self._greedy(iou, self.iou_high)
        else:
            pairs = []
        matched_det = set()
        for si, di in pairs:
            self._apply(self._states[si], high[di], ts)
            matched_det.add(di)
        unmatched_states = [i for i in unmatched_states if i not in {si for si, _ in pairs}]

        if low and unmatched_states:
            iou = self._affinity(pred[unmatched_states], np.stack([d.bbox for d in low]))
            pairs2 = self._greedy(iou, self.iou_low)
            for k, dj in pairs2:
                self._apply(self._states[unmatched_states[k]], low[dj], ts)
            matched2 = {unmatched_states[k] for k, _ in pairs2}
            unmatched_states = [i for i in unmatched_states if i not in matched2]

        for si in unmatched_states:
            st = self._states[si]
            st.track.misses += 1
            # 丢失时按预测推进位置，便于重新关联
            st.last_bbox = st.last_bbox + st.vel
            st.track.bbox = st.last_bbox.copy()

        for di, d in enumerate(high):
            if di not in matched_det:
                self._new(d, ts)

        self._states = [s for s in self._states if s.track.misses <= self.max_age]
        return [s.track for s in self._states if s.track.confirmed and s.track.misses == 0]

    def reset(self) -> None:
        self._states.clear()
