"""GPIO 输出：蜂鸣器 / 红灯 / 黄灯 / 吹扫电磁阀。

Jetson.GPIO 延迟导入；不可用时使用 :class:`FakeGpioDriver`（记录引脚状态，供测试与回放）。
继电器模块多为低电平有效，用 ``active_high`` 统一处理。退出时强制全部关断。
"""

from __future__ import annotations

import atexit
import logging
import math
import threading
from typing import Protocol

from smartview.alarm.base import AlarmSink
from smartview.clock import Clock, MonotonicClock
from smartview.config import GpioConfig
from smartview.types import AlarmLevel, AlarmState

log = logging.getLogger(__name__)


class GpioDriver(Protocol):
    def setup_output(self, pin: int) -> None: ...

    def write(self, pin: int, on: bool) -> None: ...

    def cleanup(self) -> None: ...


class FakeGpioDriver:
    def __init__(self) -> None:
        self.pins: dict[int, bool] = {}
        self.history: list[tuple[int, bool]] = []
        self._lock = threading.Lock()

    def setup_output(self, pin: int) -> None:
        with self._lock:
            self.pins.setdefault(pin, False)

    def write(self, pin: int, on: bool) -> None:
        with self._lock:
            if self.pins.get(pin) != on:
                self.history.append((pin, on))
            self.pins[pin] = on

    def cleanup(self) -> None:
        with self._lock:
            for p in self.pins:
                self.pins[p] = False


class JetsonGpioDriver:  # pragma: no cover - 需真机
    def __init__(self, mode: str = "BOARD", active_high: bool = False) -> None:
        import Jetson.GPIO as GPIO  # type: ignore

        self.GPIO = GPIO
        self.active_high = active_high
        GPIO.setmode(GPIO.BOARD if mode == "BOARD" else GPIO.BCM)
        GPIO.setwarnings(False)
        self._pins: set[int] = set()

    def setup_output(self, pin: int) -> None:
        self.GPIO.setup(pin, self.GPIO.OUT, initial=self._level(False))
        self._pins.add(pin)

    def _level(self, on: bool):
        return self.GPIO.HIGH if (on == self.active_high) else self.GPIO.LOW

    def write(self, pin: int, on: bool) -> None:
        self.GPIO.output(pin, self._level(on))

    def cleanup(self) -> None:
        for p in self._pins:
            try:
                self.GPIO.output(p, self._level(False))
            except Exception:  # noqa: BLE001
                pass
        self.GPIO.cleanup()


def make_gpio_driver(mode: str = "BOARD", active_high: bool = False, prefer_real: bool = True) -> GpioDriver:
    if prefer_real:
        try:
            drv: GpioDriver = JetsonGpioDriver(mode, active_high)
            log.info("使用 Jetson.GPIO（%s，%s）", mode, "高有效" if active_high else "低有效")
            return drv
        except Exception as exc:  # noqa: BLE001
            log.warning("Jetson.GPIO 不可用（%s），使用 FakeGpioDriver（仅记录）", exc)
    return FakeGpioDriver()


def pattern(level: AlarmLevel, buzzer_on: bool, t: float) -> tuple[bool, bool, bool]:
    """返回 (蜂鸣器, 红灯, 黄灯) 在时刻 t 的通断：L3 连续，L2 0.5 s 通 / 0.5 s 断，L1 黄灯。"""
    if level >= AlarmLevel.L3:
        return buzzer_on, True, False
    if level == AlarmLevel.L2:
        phase_on = (math.floor(t * 2) % 2) == 0
        return buzzer_on and phase_on, True, False
    if level == AlarmLevel.L1:
        return False, False, True
    return False, False, False


class GpioSink(AlarmSink):
    def __init__(self, cfg: GpioConfig, driver: GpioDriver | None = None, clock: Clock | None = None, tick_hz: float = 10.0) -> None:
        self.cfg = cfg
        self.clock = clock or MonotonicClock()
        self.driver = driver or make_gpio_driver(cfg.mode, cfg.active_high)
        for pin in (cfg.buzzer_pin, cfg.lamp_pin, cfg.lamp_yellow_pin):
            if pin is not None:
                self.driver.setup_output(pin)
        self._state: AlarmState | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.tick_hz = tick_hz
        atexit.register(self.close)

    def on_state(self, state: AlarmState) -> None:
        with self._lock:
            self._state = state
        self.apply(self.clock.now())

    def apply(self, t: float) -> tuple[bool, bool, bool]:
        with self._lock:
            st = self._state
        if st is None:
            out = (False, False, False)
        else:
            out = pattern(st.level, st.buzzer_on, t)
        buzzer, red, yellow = out
        self.driver.write(self.cfg.buzzer_pin, buzzer)
        self.driver.write(self.cfg.lamp_pin, red)
        if self.cfg.lamp_yellow_pin is not None:
            self.driver.write(self.cfg.lamp_yellow_pin, yellow)
        return out

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="gpio-pattern", daemon=True)
        self._thread.start()

    def _run(self) -> None:  # pragma: no cover - 定时线程
        while not self._stop.wait(1.0 / self.tick_hz):
            self.apply(self.clock.now())

    def close(self) -> None:
        self._stop.set()
        try:
            for pin in (self.cfg.buzzer_pin, self.cfg.lamp_pin, self.cfg.lamp_yellow_pin):
                if pin is not None:
                    self.driver.write(pin, False)
        except Exception:  # noqa: BLE001
            pass
