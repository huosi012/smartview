"""报警状态机：多相机融合、滞回、确认 / 静音、传感器故障。

线程模型：各相机线程调用 :meth:`update`，HMI 线程调用 :meth:`ack` / :meth:`mute` 等；
所有入口持同一把锁，状态快照通过 :meth:`state` 复制返回。
"""

from __future__ import annotations

import copy
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from smartview.clock import Clock, MonotonicClock
from smartview.config import MachineConfig, RiskConfig
from smartview.risk.rules import assess_track
from smartview.types import AlarmLevel, AlarmState, RiskAssessment, Track

log = logging.getLogger(__name__)


@dataclass
class CameraInfo:
    role: str
    rows_covered: tuple[int, int] | None = None

    def covers_row(self, row: int | None) -> bool:
        if row is None or self.rows_covered is None:
            return True
        lo, hi = self.rows_covered
        return lo <= row <= hi


@dataclass
class _CamRecord:
    ts: float
    assessments: list[RiskAssessment]


class RiskEngine:
    def __init__(
        self,
        cfg: RiskConfig,
        machine: MachineConfig,
        cameras: dict[str, CameraInfo],
        clock: Clock | None = None,
    ) -> None:
        self.cfg = cfg
        self.machine = machine
        self.cameras = dict(cameras)
        self.clock = clock or MonotonicClock()
        self._lock = threading.RLock()
        self._state = AlarmState()
        self._records: dict[str, _CamRecord] = {}
        self._below_since: float | None = None
        self._ack_level = AlarmLevel.L0
        self._ack_key: tuple[str, int] | None = None
        self._faults: dict[str, list[str]] = {}
        self._subs: list[Callable[[AlarmState], None]] = []
        self._version = 0

    # --------------------------------------------------------------- controls
    def subscribe(self, cb: Callable[[AlarmState], None]) -> None:
        self._subs.append(cb)

    def set_sensitivity(self, name: str) -> None:
        with self._lock:
            self.cfg.sensitivity = name  # type: ignore[assignment]

    def ack(self) -> AlarmState:
        with self._lock:
            now = self.clock.now()
            st = self._state
            st.acked = True
            self._ack_level = st.level
            self._ack_key = (st.top.cam_id, st.top.track_id) if st.top else None
            self._recompute(now, force_notify=True)
            return self.state()

    def mute(self, seconds: float) -> AlarmState:
        with self._lock:
            now = self.clock.now()
            self._state.muted_until = now + max(0.0, min(seconds, self.cfg.mute_max_s))
            self._recompute(now, force_notify=True)
            return self.state()

    def unmute(self) -> AlarmState:
        with self._lock:
            self._state.muted_until = 0.0
            self._recompute(self.clock.now(), force_notify=True)
            return self.state()

    def set_sensor_fault(self, cam_id: str, reasons: list[str] | None) -> None:
        with self._lock:
            if reasons:
                self._faults[cam_id] = list(reasons)
            else:
                self._faults.pop(cam_id, None)
            self._recompute(self.clock.now())

    def set_purging(self, cam_id: str, active: bool) -> None:
        with self._lock:
            if active:
                self._state.purging[cam_id] = True
            else:
                self._state.purging.pop(cam_id, None)
            self._recompute(self.clock.now())

    def test_alarm(self, level: AlarmLevel, dist_m: float = 6.2) -> AlarmState:
        """HMI"测试报警"：注入一条虚拟评估（约 fusion_window 后自动消失，再经滞回降级）。"""
        with self._lock:
            now = self.clock.now()
            a = RiskAssessment(
                cam_id="__test__", track_id=0, level=AlarmLevel(level), score=1.0, dist_m=dist_m, ttc_s=None,
                reasons=["测试报警"], cls_name="well_pipe", row=None, in_path=True,
            )
            self._records["__test__"] = _CamRecord(ts=now, assessments=[a] if level > AlarmLevel.L0 else [])
            self._recompute(now, force_notify=True)
            return self.state()

    def set_event_id(self, event_id: int | None) -> None:
        with self._lock:
            self._state.event_id = event_id

    def state(self) -> AlarmState:
        with self._lock:
            return copy.deepcopy(self._state)

    @property
    def version(self) -> int:
        return self._version

    # ----------------------------------------------------------------- inputs
    def update(self, cam_id: str, tracks: list[Track], ts: float | None = None) -> list[RiskAssessment]:
        info = self.cameras.get(cam_id) or CameraInfo(role="forward")
        with self._lock:
            now = self.clock.now() if ts is None else ts
            assessments = [assess_track(t, info.role, self.cfg, self.machine) for t in tracks]
            assessments = [a for a in assessments if a.level > AlarmLevel.L0]
            self._records[cam_id] = _CamRecord(ts=now, assessments=assessments)
            self._recompute(now)
            return assessments

    def tick(self, ts: float | None = None) -> AlarmState:
        with self._lock:
            self._recompute(self.clock.now() if ts is None else ts)
            return self.state()

    # ------------------------------------------------------------------ logic
    def _fresh_records(self, now: float) -> dict[str, _CamRecord]:
        win = max(self.cfg.thresholds.fusion_window_s, 1.0)
        return {c: r for c, r in self._records.items() if now - r.ts <= win}

    def _raw_level(self, now: float) -> tuple[AlarmLevel, RiskAssessment | None, dict[str, AlarmLevel]]:
        fresh = self._fresh_records(now)
        per_cam: dict[str, AlarmLevel] = {}
        best: RiskAssessment | None = None
        for cam_id, rec in fresh.items():
            lvl = AlarmLevel.L0
            for a in rec.assessments:
                lvl = max(lvl, a.level)
                if best is None or (a.level, -(a.dist_m or 1e9)) > (best.level, -(best.dist_m or 1e9)):
                    best = a
            per_cam[cam_id] = lvl
        raw = max(per_cam.values(), default=AlarmLevel.L0)
        # 多相机升级
        if raw >= AlarmLevel.L2 and raw < AlarmLevel.L3:
            cams_l2 = [c for c, lvl in per_cam.items() if lvl >= AlarmLevel.L2]
            escalate = len(cams_l2) >= 2
            if not escalate and best is not None and self.cameras.get(best.cam_id, CameraInfo("forward")).role == "forward":
                for cam_id in fresh:
                    info = self.cameras.get(cam_id)
                    if info is None or info.role != "header" or cam_id == best.cam_id:
                        continue
                    if per_cam.get(cam_id, AlarmLevel.L0) >= AlarmLevel.L1 and info.covers_row(best.row):
                        escalate = True
                        break
            if escalate:
                raw = AlarmLevel(min(int(raw) + 1, int(AlarmLevel.L3)))
                if best is not None:
                    best = copy.copy(best)
                    best.level = raw
                    best.reasons = list(best.reasons) + ["多相机同时确认"]
        return raw, best, per_cam

    def _support_lost_ts(self, now: float) -> float:
        if not self._records:
            return now
        if self._fresh_records(now):
            return now
        win = max(self.cfg.thresholds.fusion_window_s, 1.0)
        return max(r.ts for r in self._records.values()) + win

    def _recompute(self, now: float, force_notify: bool = False) -> None:
        st = self._state
        prev = (st.level, st.top.track_id if st.top else None, st.top.cam_id if st.top else None, st.buzzer_on, st.lamp_on, st.acked, st.sensor_fault, tuple(sorted(st.purging)), st.muted_until)
        raw, best, per_cam = self._raw_level(now)
        fault = bool(self._faults)
        if fault and raw < AlarmLevel.L1:
            raw = AlarmLevel.L1

        if raw > st.level:
            st.level = raw
            st.since_ts = now
            self._below_since = None
        elif raw < st.level:
            if self._below_since is None:
                # 支撑消失的时刻：若所有记录都已过期，从最后一条记录过期时起算，避免相机线程停摆时无限保持
                self._below_since = min(now, self._support_lost_ts(now))
            hold = float(self.cfg.hold_s.get(f"L{int(st.level)}", 0.0))
            if now - self._below_since >= hold:
                st.level = raw
                st.since_ts = now
                self._below_since = None
        else:
            self._below_since = None

        # 顶级威胁：当前等级下保留最近的最佳评估（降级保持期内沿用旧的）
        if best is not None and (best.level >= st.level or st.top is None):
            st.top = best
        elif st.level == AlarmLevel.L0:
            st.top = None

        # 确认（ack）的重新武装：更高等级或新目标
        if st.acked:
            key = (st.top.cam_id, st.top.track_id) if st.top else None
            if st.level > self._ack_level or (key is not None and key != self._ack_key):
                st.acked = False
        if st.level == AlarmLevel.L0:
            st.acked = False
            self._ack_level = AlarmLevel.L0
            self._ack_key = None

        st.sensor_fault = fault
        st.fault_reasons = [f"{c}: {'；'.join(r)}" for c, r in self._faults.items()]
        st.per_cam = per_cam
        st.ts = now
        muted = now < st.muted_until
        st.buzzer_on = st.level >= AlarmLevel.L2 and not st.acked and not muted
        st.lamp_on = st.level >= AlarmLevel.L2
        if not muted and st.muted_until:
            st.muted_until = 0.0

        cur = (st.level, st.top.track_id if st.top else None, st.top.cam_id if st.top else None, st.buzzer_on, st.lamp_on, st.acked, st.sensor_fault, tuple(sorted(st.purging)), st.muted_until)
        if cur != prev or force_notify:
            self._version += 1
            snapshot = copy.deepcopy(st)
            for cb in list(self._subs):
                try:
                    cb(snapshot)
                except Exception:  # noqa: BLE001
                    log.exception("风险引擎订阅者异常")
