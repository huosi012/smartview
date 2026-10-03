"""镜头吹扫控制器（风刀 / 电磁阀）。

触发来源：定时（period_s）、镜头脏污检测（on_dirty）、HMI 手动。
保护：最小间隔 min_interval_s、滑动窗口占空比 max_duty（保护电磁阀与气源）。
吹扫期间及其后 suppress_extra_s 内，对应相机的检测结果不提交风险引擎（气流扬尘会造成误检）。
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from smartview.alarm.gpio import GpioDriver
from smartview.clock import Clock, MonotonicClock
from smartview.config import PurgeConfig

log = logging.getLogger(__name__)

DUTY_WINDOW_S = 600.0


@dataclass
class _Channel:
    name: str
    pin: int
    active_until: float | None = None
    last_start: float = -1e9
    count: int = 0
    last_reason: str = ""
    bursts: list[tuple[float, float]] = field(default_factory=list)


class LensPurgeController:
    def __init__(
        self,
        cfg: PurgeConfig,
        driver: GpioDriver,
        clock: Clock | None = None,
        on_change: Callable[[str, bool], None] | None = None,
        on_log: Callable[[float, str, str], None] | None = None,
    ) -> None:
        self.cfg = cfg
        self.driver = driver
        self.clock = clock or MonotonicClock()
        self.on_change = on_change
        self.on_log = on_log
        self._lock = threading.Lock()
        self._ch: dict[str, _Channel] = {}
        for name, pin in cfg.channels.items():
            self._ch[name] = _Channel(name=name, pin=pin)
            driver.setup_output(pin)
            driver.write(pin, False)
        self._next_periodic = self.clock.now() + cfg.period_s if cfg.period_s > 0 else None

    # ---------------------------------------------------------------- queries
    def channels(self) -> list[str]:
        return list(self._ch)

    def is_active(self, channel: str, now: float | None = None) -> bool:
        now = self.clock.now() if now is None else now
        ch = self._ch.get(channel)
        return bool(ch and ch.active_until is not None and now < ch.active_until)

    def is_suppressed(self, channel: str | None, now: float | None = None) -> bool:
        """吹扫窗口（含结束后 suppress_extra_s）内不提交检测。"""
        if channel is None or channel not in self._ch:
            return False
        now = self.clock.now() if now is None else now
        ch = self._ch[channel]
        end = ch.last_start + self.cfg.burst_s + self.cfg.suppress_extra_s
        return ch.last_start <= now < end

    def status(self, now: float | None = None) -> dict:
        now = self.clock.now() if now is None else now
        return {
            "enabled": self.cfg.enabled,
            "next_periodic_in_s": (round(self._next_periodic - now, 1) if self._next_periodic is not None else None),
            "channels": {
                n: {
                    "active": self.is_active(n, now),
                    "count": c.count,
                    "last_ago_s": (round(now - c.last_start, 1) if c.count else None),
                    "last_reason": c.last_reason,
                }
                for n, c in self._ch.items()
            },
        }

    # ---------------------------------------------------------------- control
    def _duty_ok(self, ch: _Channel, now: float) -> bool:
        ch.bursts = [(s, e) for s, e in ch.bursts if e >= now - DUTY_WINDOW_S]
        used = sum(min(e, now) - max(s, now - DUTY_WINDOW_S) for s, e in ch.bursts)
        return (used + self.cfg.burst_s) / DUTY_WINDOW_S <= self.cfg.max_duty

    def request(self, channel: str, reason: str = "manual", now: float | None = None) -> bool:
        """请求一次吹扫；受最小间隔与占空比限制。返回是否已启动。"""
        if not self.cfg.enabled:
            return False
        now = self.clock.now() if now is None else now
        with self._lock:
            ch = self._ch.get(channel)
            if ch is None:
                return False
            if self.is_active(channel, now):
                return False
            if now - ch.last_start < self.cfg.min_interval_s:
                return False
            if not self._duty_ok(ch, now):
                log.warning("吹扫通道 %s 达到占空比上限，跳过（%s）", channel, reason)
                return False
            ch.active_until = now + self.cfg.burst_s
            ch.last_start = now
            ch.count += 1
            ch.last_reason = reason
            ch.bursts.append((now, now + self.cfg.burst_s))
            self.driver.write(ch.pin, True)
        log.info("吹扫 %s 开始（%s）", channel, reason)
        if self.on_change:
            self.on_change(channel, True)
        if self.on_log:
            self.on_log(now, channel, reason)
        return True

    def request_all(self, reason: str = "manual", now: float | None = None) -> int:
        return sum(1 for n in list(self._ch) if self.request(n, reason, now))

    def on_lens_dirty(self, channel: str | None, dirty: bool, now: float | None = None) -> bool:
        if not dirty or not self.cfg.on_dirty or channel is None:
            return False
        return self.request(channel, "lens_dirty", now)

    def tick(self, now: float | None = None) -> None:
        """结束到期的吹扫；到达周期时启动定时吹扫。真机由线程周期调用，回放逐帧调用。"""
        now = self.clock.now() if now is None else now
        ended: list[str] = []
        with self._lock:
            for ch in self._ch.values():
                if ch.active_until is not None and now >= ch.active_until:
                    ch.active_until = None
                    self.driver.write(ch.pin, False)
                    ended.append(ch.name)
        for n in ended:
            log.info("吹扫 %s 结束", n)
            if self.on_change:
                self.on_change(n, False)
        if self.cfg.enabled and self._next_periodic is not None and now >= self._next_periodic:
            self._next_periodic = now + self.cfg.period_s
            self.request_all("periodic", now)

    def close(self) -> None:
        with self._lock:
            for ch in self._ch.values():
                ch.active_until = None
                try:
                    self.driver.write(ch.pin, False)
                except Exception:  # noqa: BLE001
                    pass
