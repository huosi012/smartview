"""HMI / CLI 对运行中系统的控制入口（不依赖 fastapi）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from smartview.types import AlarmLevel

if TYPE_CHECKING:  # pragma: no cover
    from smartview.pipeline.app import SmartViewApp


class Controls:
    def __init__(self, app: SmartViewApp) -> None:
        self.app = app

    # ------------------------------------------------------------- alarms
    def ack(self) -> dict[str, Any]:
        return self.app.engine.ack().to_dict()

    def mute(self, seconds: float) -> dict[str, Any]:
        return self.app.engine.mute(seconds).to_dict()

    def unmute(self) -> dict[str, Any]:
        return self.app.engine.unmute().to_dict()

    def test_alarm(self, level: int) -> dict[str, Any]:
        return self.app.engine.test_alarm(AlarmLevel(int(level))).to_dict()

    # ----------------------------------------------------------- settings
    def settings(self) -> dict[str, Any]:
        sp = self.app.speed
        return {
            "speed_kmh": round(sp.manual.speed_mps() * 3.6, 1),
            "speed_source": sp.source,
            "speed_quality": sp.quality,
            "current_speed_kmh": round(sp.speed_mps() * 3.6, 1),
            "sensitivity": self.app.cfg.risk.sensitivity,
            "purge_enabled": bool(self.app.purge and self.app.cfg.alarm.purge.enabled),
            "purge_channels": self.app.purge.channels() if self.app.purge else [],
            "cameras": [
                {"id": c.id, "role": c.role, "role_zh": "前视" if c.role == "forward" else "割台", "purge_channel": c.purge_channel}
                for c in self.app.cfg.cameras
            ],
        }

    def update_settings(self, speed_kmh: float | None = None, speed_source: str | None = None, sensitivity: str | None = None) -> dict[str, Any]:
        if speed_kmh is not None:
            self.app.speed.set_manual(float(speed_kmh) / 3.6)
        if speed_source is not None:
            self.app.speed.use(speed_source)
        if sensitivity is not None:
            self.app.engine.set_sensitivity(sensitivity)
        self.app.publish_speed()
        return self.settings()

    # -------------------------------------------------------------- purge
    def purge(self, channel: str | None = None) -> dict[str, Any]:
        p = self.app.purge
        if p is None:
            return {"ok": False, "reason": "吹扫未启用", "started": 0}
        if channel:
            started = int(p.request(channel, "manual"))
        else:
            started = p.request_all("manual")
        self.app.publish_purge()
        return {"ok": started > 0, "started": started, "status": p.status()}

    def purge_status(self) -> dict[str, Any]:
        return self.app.purge.status() if self.app.purge else {"enabled": False, "channels": {}}

    # ------------------------------------------------------------- events
    def events(self, limit: int = 50, since: float | None = None, min_level: int = 0) -> list[dict[str, Any]]:
        if self.app.store is None:
            return []
        return [e.to_dict() for e in self.app.store.list(limit=limit, since=since, min_level=min_level)]

    def event(self, event_id: int) -> dict[str, Any] | None:
        if self.app.store is None:
            return None
        e = self.app.store.get(event_id)
        return e.to_dict() if e else None

    def stats(self) -> dict[str, Any]:
        return self.app.store.stats() if self.app.store else {"total": 0, "by_level": {}}
