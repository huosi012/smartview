"""事件记录器：订阅报警状态，负责事件开启 / 更新 / 关闭、冷却合并、快照与前后滚片段。"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from smartview.clock import Clock, MonotonicClock
from smartview.config import StorageConfig
from smartview.risk.engine import RiskEngine
from smartview.storage.event_store import EventStore
from smartview.storage.ring_buffer import RingBuffer, prune_dir, write_clip, write_snapshot
from smartview.types import AlarmLevel, AlarmState, Event

log = logging.getLogger(__name__)


@dataclass
class _Open:
    event: Event
    mono_start: float
    cam_id: str
    track_id: int
    last_xy: tuple[float, float] | None


@dataclass
class _PendingClip:
    event_id: int
    cam_id: str
    t_trigger: float
    t_due: float


class EventRecorder:
    def __init__(
        self,
        store: EventStore,
        cfg: StorageConfig,
        engine: RiskEngine | None = None,
        clock: Clock | None = None,
        wall_fn: Callable[[], float] | None = None,
        cooldown_s: float = 5.0,
        clip_dir: str | Path | None = None,
        async_clips: bool = False,
    ) -> None:
        self.store = store
        self.cfg = cfg
        self.engine = engine
        self.clock = clock or MonotonicClock()
        self.wall_fn = wall_fn or time.time
        self.cooldown_s = cooldown_s
        self.clip_dir = Path(clip_dir or cfg.clip_dir)
        self.async_clips = async_clips
        self._rings: dict[str, RingBuffer] = {}
        self._open: _Open | None = None
        self._last_closed: tuple[_Open, float] | None = None
        self._pending: list[_PendingClip] = []
        self._lock = threading.RLock()
        self._speed_fn: Callable[[], float] | None = None
        if engine is not None:
            engine.subscribe(self.on_state)

    # ---------------------------------------------------------------- wiring
    def register_ring(self, cam_id: str, ring: RingBuffer) -> None:
        self._rings[cam_id] = ring

    def set_speed_fn(self, fn: Callable[[], float]) -> None:
        self._speed_fn = fn

    @property
    def open_event_id(self) -> int | None:
        with self._lock:
            return self._open.event.event_id if self._open else None

    # --------------------------------------------------------------- handlers
    def on_state(self, st: AlarmState) -> None:
        with self._lock:
            now = self.clock.now()
            if st.level >= AlarmLevel.L2 and st.top is not None:
                if self._open is None:
                    self._start(st, now)
                else:
                    self._update(st)
            elif self._open is not None and st.level < AlarmLevel.L2:
                self._close(now)
            if st.acked and self._open is not None and not self._open.event.acked:
                self._open.event.acked = True
                self._open.event.ack_ts = self.wall_fn()
                self.store.update(self._open.event.event_id, acked=True, ack_ts=self._open.event.ack_ts)  # type: ignore[arg-type]

    def _start(self, st: AlarmState, now: float) -> None:
        top = st.top
        assert top is not None
        xy = None
        reopen = None
        if self._last_closed is not None:
            prev, t_closed = self._last_closed
            same_track = prev.cam_id == top.cam_id and prev.track_id == top.track_id
            near = False
            if prev.last_xy is not None and top.dist_m is not None:
                near = abs(prev.last_xy[0] - top.dist_m) <= 1.0
            if now - t_closed <= self.cooldown_s and (same_track or near):
                reopen = prev
        if reopen is not None:
            ev = reopen.event
            ev.ts_end = None
            ev.level_max = max(ev.level_max, st.level)
            self.store.update(ev.event_id, ts_end=None, level_max=ev.level_max)  # type: ignore[arg-type]
            self._open = _Open(ev, now, top.cam_id, top.track_id, (top.dist_m or 0.0, 0.0))
            self._last_closed = None
            log.info("事件 %s 在冷却期内延续", ev.event_id)
        else:
            speed = self._speed_fn() if self._speed_fn else None
            ev = Event(
                event_id=None,
                ts_start=self.wall_fn(),
                ts_end=None,
                level_max=st.level,
                cam_id=top.cam_id,
                cls_name=top.cls_name,
                track_id=top.track_id,
                dist_min=top.dist_m,
                ttc_min=top.ttc_s,
                speed_mps=speed,
                extra={"reasons": list(top.reasons), "row": top.row},
            )
            self.store.insert(ev)
            if top.dist_m is not None:
                xy = (top.dist_m, 0.0)
            self._open = _Open(ev, now, top.cam_id, top.track_id, xy)
            self._save_snapshot(ev, top.cam_id)
            self._pending.append(_PendingClip(ev.event_id, top.cam_id, now, now + self.cfg.post_roll_s))  # type: ignore[arg-type]
            log.info("事件 %s 开始：%s", ev.event_id, st.message_zh())
        if self.engine is not None:
            self.engine.set_event_id(self._open.event.event_id)

    def _update(self, st: AlarmState) -> None:
        assert self._open is not None and st.top is not None
        ev, top = self._open.event, st.top
        changed = {}
        if st.level > ev.level_max:
            ev.level_max = st.level
            changed["level_max"] = int(st.level)
        if top.dist_m is not None and (ev.dist_min is None or top.dist_m < ev.dist_min):
            ev.dist_min = top.dist_m
            changed["dist_min"] = top.dist_m
            self._open.last_xy = (top.dist_m, 0.0)
        if top.ttc_s is not None and (ev.ttc_min is None or top.ttc_s < ev.ttc_min):
            ev.ttc_min = top.ttc_s
            changed["ttc_min"] = top.ttc_s
        if (top.cam_id, top.track_id) != (self._open.cam_id, self._open.track_id):
            self._open.cam_id, self._open.track_id = top.cam_id, top.track_id
        if changed:
            self.store.update(ev.event_id, **changed)  # type: ignore[arg-type]

    def _close(self, now: float) -> None:
        assert self._open is not None
        ev = self._open.event
        ev.ts_end = self.wall_fn()
        self.store.update(ev.event_id, ts_end=ev.ts_end)  # type: ignore[arg-type]
        self._last_closed = (self._open, now)
        self._open = None
        if self.engine is not None:
            self.engine.set_event_id(None)
        log.info("事件 %s 结束", ev.event_id)

    # ------------------------------------------------------------- snapshots
    def _event_base(self, ev: Event, cam_id: str) -> Path:
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(ev.ts_start))
        return self.clip_dir / f"ev{ev.event_id:06d}_{stamp}_{cam_id}"

    def _save_snapshot(self, ev: Event, cam_id: str) -> None:
        ring = self._rings.get(cam_id)
        latest = ring.latest() if ring else None
        if latest is None:
            return
        try:
            p = write_snapshot(self._event_base(ev, cam_id), latest[1])
            ev.snapshot_path = str(p)
            self.store.update(ev.event_id, snapshot_path=str(p))  # type: ignore[arg-type]
        except OSError:
            log.exception("保存快照失败")

    def tick(self, now: float | None = None) -> int:
        """处理到期的片段写出（回放模式由运行器逐帧调用；真机由线程周期调用）。返回写出的片段数。"""
        now = self.clock.now() if now is None else now
        written = 0
        with self._lock:
            due = [p for p in self._pending if now >= p.t_due]
            self._pending = [p for p in self._pending if now < p.t_due]
        for p in due:
            ring = self._rings.get(p.cam_id)
            ev = self.store.get(p.event_id)
            if ring is None or ev is None:
                continue
            frames = ring.snapshot(p.t_trigger - self.cfg.pre_roll_s, p.t_trigger + self.cfg.post_roll_s)
            if self.async_clips:
                threading.Thread(target=self._write, args=(ev, p.cam_id, frames, ring.fps), daemon=True).start()
            else:
                self._write(ev, p.cam_id, frames, ring.fps)
            written += 1
        return written

    def _write(self, ev: Event, cam_id: str, frames, fps: float) -> None:
        try:
            path = write_clip(self._event_base(ev, cam_id), frames, fps)
            if path is not None:
                self.store.update(ev.event_id, clip_path=str(path))  # type: ignore[arg-type]
                prune_dir(self.clip_dir, self.cfg.max_disk_gb * (1024**3))
        except Exception:  # noqa: BLE001
            log.exception("写片段失败")

    def flush(self) -> None:
        """强制写出所有待处理片段（关闭时调用）。"""
        with self._lock:
            for p in self._pending:
                p.t_due = -1e18
        self.tick(self.clock.now())

    def pending_clips(self) -> int:
        with self._lock:
            return len(self._pending)
