"""单相机处理链：健康 → 环形缓存 → 检测（裁剪/遮罩）→ 跟踪 → 几何定位 → 风险引擎 → HMI 快照。"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from collections.abc import Callable
from typing import Any

import cv2
import numpy as np

from smartview.bus import CamSnapshot, StateBus
from smartview.capture.base import FrameSource
from smartview.clock import Clock
from smartview.config import CameraConfig, SmartViewConfig
from smartview.detect.base import Detector
from smartview.detect.mask import RegionMask
from smartview.geometry.camera import GroundProjector, estimate_range_rate, time_to_contact
from smartview.geometry.speed import SharedSpeed
from smartview.health.monitor import HealthMonitor
from smartview.risk.engine import RiskEngine
from smartview.storage.ring_buffer import RingBuffer
from smartview.track.iou_tracker import ByteTrackLite
from smartview.types import CLASS_ZH, LEVEL_COLOR, AlarmLevel, Detection, Frame, Track

log = logging.getLogger(__name__)


def _hex_to_bgr(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)


class CameraWorker:
    def __init__(
        self,
        cam: CameraConfig,
        cfg: SmartViewConfig,
        source: FrameSource,
        detector: Detector,
        region: RegionMask,
        projector: GroundProjector,
        tracker: ByteTrackLite,
        health: HealthMonitor,
        ring: RingBuffer,
        engine: RiskEngine,
        bus: StateBus,
        speed: SharedSpeed,
        clock: Clock,
        purge=None,
        det_log: Callable[[dict[str, Any]], None] | None = None,
        collect: bool = False,
    ) -> None:
        self.cam, self.cfg = cam, cfg
        self.source, self.detector, self.region, self.projector = source, detector, region, projector
        self.tracker, self.health, self.ring = tracker, health, ring
        self.engine, self.bus, self.speed, self.clock = engine, bus, speed, clock
        self.purge = purge
        self.det_log = det_log
        self.collect = collect
        self.records: list[dict[str, Any]] = []
        self.use_crop = cfg.detector.backend != "classical" and cam.detect_crop is not None
        self._dist_hist: dict[int, deque[tuple[float, float]]] = {}
        self._last_faults: list[str] | None = None
        self._last_overlay_ts = -1e9
        self._infer_ms = 0.0
        self.frames = 0
        self.level = AlarmLevel.L0
        self._region_cache: RegionMask | None = None
        self._proj_cache: GroundProjector | None = None
        self._size: tuple[int, int] | None = None

    # ------------------------------------------------------------- helpers
    def _for_size(self, w: int, h: int) -> tuple[RegionMask, GroundProjector]:
        if self._size != (w, h) or self._region_cache is None or self._proj_cache is None:
            self._size = (w, h)
            self._region_cache = self.region.for_size(w, h)
            self._proj_cache = self.projector.for_size(w, h)
        return self._region_cache, self._proj_cache

    def _detect(self, image: np.ndarray, region: RegionMask) -> list[Detection]:
        if self.use_crop:
            h, w = image.shape[:2]
            x0, y0, x1, y1 = self.cam.detect_crop  # type: ignore[misc]
            px0, py0, px1, py1 = int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)
            dets = self.detector.detect(image[py0:py1, px0:px1])
            for d in dets:
                d.bbox = d.bbox + np.array([px0, py0, px0, py0], dtype=np.float32)
        else:
            dets = self.detector.detect(image)
        return region.filter(dets)

    def _annotate(self, tracks: list[Track], projector: GroundProjector, ts: float) -> None:
        v = self.speed.speed_mps()
        alive = set()
        for t in tracks:
            alive.add(t.track_id)
            gp = projector.annotate(t)
            if gp is None:
                t.dist_m, t.ttc_s = None, None
                continue
            hist = self._dist_hist.setdefault(t.track_id, deque(maxlen=30))
            a = self.cfg.tracker.dist_ema
            t.dist_m = gp.x_fwd if t.dist_m is None else (1 - a) * t.dist_m + a * gp.x_fwd
            hist.append((ts, gp.x_fwd))
            t.range_rate = estimate_range_rate(list(hist))
            t.ttc_s = time_to_contact(t.dist_m, v, self.cfg.speed.min_speed_mps)
        for tid in list(self._dist_hist):
            if tid not in alive:
                self._dist_hist.pop(tid, None)

    # ------------------------------------------------------------- process
    def process(self, frame: Frame) -> CamSnapshot:
        t0 = time.perf_counter()
        ts = frame.ts
        h, w = frame.image.shape[:2]
        region, projector = self._for_size(w, h)
        health = self.health.observe(frame, self._infer_ms)
        faults = self.health.faults()
        if faults != self._last_faults:
            self.engine.set_sensor_fault(self.cam.id, faults or None)
            self._last_faults = faults
        if self.purge is not None and health.lens_dirty:
            self.purge.on_lens_dirty(self.cam.purge_channel, True, self.clock.now())
        jpeg = self.ring.push(ts, frame.image)

        suppressed = self.purge is not None and self.purge.is_suppressed(self.cam.purge_channel, self.clock.now())
        dets: list[Detection] = []
        tracks: list[Track] = []
        if not suppressed:
            td = time.perf_counter()
            dets = self._detect(frame.image, region)
            self._infer_ms = (time.perf_counter() - td) * 1000.0
            tracks = self.tracker.update(dets, ts)
            self._annotate(tracks, projector, ts)
            assessments = self.engine.update(self.cam.id, tracks, self.clock.now())
            lvl = max((a.level for a in assessments), default=AlarmLevel.L0)
        else:
            lvl = AlarmLevel.L0
        self.level = lvl
        self.frames += 1

        track_dicts = [
            {
                "id": t.track_id,
                "cls": t.cls_name,
                "cls_zh": CLASS_ZH.get(t.cls_name, t.cls_name),
                "score": round(t.score, 2),
                "bbox": [round(float(v), 1) for v in t.bbox],
                "dist_m": None if t.dist_m is None else round(t.dist_m, 2),
                "ttc_s": None if t.ttc_s is None else round(t.ttc_s, 2),
                "row": t.ground.row if t.ground else None,
                "in_path": bool(t.ground.in_path) if t.ground else False,
                "hits": t.hits,
            }
            for t in tracks
        ]
        if self.det_log is not None or self.collect:
            rec = {
                "cam": self.cam.id,
                "seq": frame.seq,
                "ts": round(ts, 4),
                "dets": [{"bbox": d.as_list(), "score": round(d.score, 3), "cls": d.cls_name} for d in dets],
                "tracks": track_dicts,
                "level": int(lvl),
                "suppressed": suppressed,
            }
            if self.det_log is not None:
                self.det_log(rec)
            if self.collect:
                self.records.append(rec)

        overlay_jpeg = None
        if self.bus is not None and (ts - self._last_overlay_ts) >= 1.0 / self.cfg.hmi.mjpeg_fps:
            self._last_overlay_ts = ts
            overlay_jpeg = self._overlay(frame.image, region, tracks, suppressed)
        snap = CamSnapshot(
            cam_id=self.cam.id,
            ts=ts,
            jpeg=overlay_jpeg if overlay_jpeg is not None else jpeg,
            tracks=track_dicts,
            health=health,
            level=int(lvl),
            purging=suppressed,
            infer_ms=(time.perf_counter() - t0) * 1000.0,
            seq=frame.seq,
        )
        if self.bus is not None and (overlay_jpeg is not None or jpeg is not None or frame.seq % 5 == 0):
            if overlay_jpeg is None:
                prev = self.bus.cam_jpeg(self.cam.id)
                snap.jpeg = prev if prev is not None else jpeg
            self.bus.set_cam(snap)
        return snap

    def _overlay(self, image: np.ndarray, region: RegionMask, tracks: list[Track], suppressed: bool) -> bytes:
        vis = region.overlay(image, alpha=0.25) if region.has_exclusions or region.roi_polygon else image.copy()
        for t in tracks:
            x1, y1, x2, y2 = (int(v) for v in t.bbox)
            color = _hex_to_bgr(LEVEL_COLOR[AlarmLevel.L2 if (t.ground and t.ground.in_path) else AlarmLevel.L1])
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
            label = CLASS_ZH.get(t.cls_name, t.cls_name)
            txt = f"#{t.track_id} {t.score:.2f}"
            if t.dist_m is not None:
                txt += f" {t.dist_m:.1f}m"
            cv2.putText(vis, txt, (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
            _ = label  # 中文标签由 HMI 侧渲染（OpenCV 默认字体不含中文）
        if suppressed:
            cv2.putText(vis, "PURGING", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2, cv2.LINE_AA)
        ok, buf = cv2.imencode(".jpg", vis, [int(cv2.IMWRITE_JPEG_QUALITY), self.cfg.hmi.jpeg_quality])
        return buf.tobytes() if ok else b""

    # -------------------------------------------------------- thread loop
    def run_loop(self, stop_event, on_frame: Callable[[Frame], None] | None = None) -> None:
        """真机模式：独立线程循环读取并处理。"""
        self.source.open()
        try:
            while not stop_event.is_set():
                fr = self.source.read()
                if fr is None:
                    if self.source.finished:
                        break
                    stop_event.wait(0.005)
                    continue
                self.process(fr)
                if on_frame is not None:
                    on_frame(fr)
        except Exception:  # noqa: BLE001
            log.exception("相机 %s 工作线程异常退出", self.cam.id)
            self.engine.set_sensor_fault(self.cam.id, ["处理线程异常"])
        finally:
            self.source.close()


def jsonl_writer(path: str):
    f = open(path, "a", encoding="utf-8")  # noqa: SIM115

    def _w(rec: dict[str, Any]) -> None:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    _w.close = f.close  # type: ignore[attr-defined]
    return _w
