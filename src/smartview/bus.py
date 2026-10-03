"""StateBus：各线程向 HMI / 报警分发共享状态的版本化容器。"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from smartview.types import AlarmState, CamHealth


@dataclass
class CamSnapshot:
    cam_id: str
    ts: float
    jpeg: bytes | None = None
    tracks: list[dict[str, Any]] = field(default_factory=list)
    health: CamHealth | None = None
    level: int = 0
    purging: bool = False
    infer_ms: float = 0.0
    seq: int = 0


class StateBus:
    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._version = 0
        self._alarm = AlarmState()
        self._cams: dict[str, CamSnapshot] = {}
        self._speed: dict[str, Any] = {"mps": 0.0, "source": "manual", "quality": "manual"}
        self._purge: dict[str, Any] = {}
        self._system: dict[str, Any] = {}
        self._started = time.time()

    # --------------------------------------------------------------- writers
    def _bump(self) -> None:
        self._version += 1
        self._cv.notify_all()

    def set_alarm(self, state: AlarmState) -> None:
        with self._cv:
            self._alarm = state
            self._bump()

    def set_cam(self, snap: CamSnapshot) -> None:
        with self._cv:
            self._cams[snap.cam_id] = snap
            self._bump()

    def set_speed(self, mps: float, source: str, quality: str) -> None:
        with self._cv:
            self._speed = {"mps": round(float(mps), 2), "kmh": round(float(mps) * 3.6, 1), "source": source, "quality": quality}
            self._bump()

    def set_purge(self, status: dict[str, Any]) -> None:
        with self._cv:
            self._purge = status
            self._bump()

    def set_system(self, info: dict[str, Any]) -> None:
        with self._cv:
            self._system = info
            self._bump()

    # --------------------------------------------------------------- readers
    @property
    def version(self) -> int:
        with self._cv:
            return self._version

    def wait_for_change(self, since: int, timeout: float = 1.0) -> int:
        with self._cv:
            if self._version == since:
                self._cv.wait(timeout)
            return self._version

    def alarm(self) -> AlarmState:
        with self._cv:
            return self._alarm

    def cam_jpeg(self, cam_id: str) -> bytes | None:
        with self._cv:
            snap = self._cams.get(cam_id)
            return snap.jpeg if snap else None

    def cam_ids(self) -> list[str]:
        with self._cv:
            return list(self._cams)

    def snapshot(self) -> dict[str, Any]:
        with self._cv:
            cams = {}
            for cid, s in self._cams.items():
                cams[cid] = {
                    "cam_id": cid,
                    "ts": s.ts,
                    "seq": s.seq,
                    "level": int(s.level),
                    "tracks": s.tracks,
                    "health": s.health.to_dict() if s.health else None,
                    "purging": s.purging,
                    "infer_ms": round(s.infer_ms, 1),
                    "has_image": s.jpeg is not None,
                }
            return {
                "version": self._version,
                "alarm": self._alarm.to_dict(),
                "cameras": cams,
                "speed": dict(self._speed),
                "purge": dict(self._purge),
                "system": dict(self._system),
                "uptime_s": round(time.time() - self._started, 1),
            }
