"""车速来源：手动设定 / NMEA（GNSS 串口）。"""

from __future__ import annotations

import logging
import threading
from typing import Protocol

from smartview.clock import Clock, MonotonicClock

log = logging.getLogger(__name__)

KNOT_MPS = 0.514444


class SpeedSource(Protocol):
    def speed_mps(self) -> float:  # pragma: no cover - protocol
        ...

    @property
    def quality(self) -> str:  # pragma: no cover - protocol
        """``manual`` / ``ok`` / ``stale``"""
        ...


class ManualSpeed:
    def __init__(self, mps: float = 1.5) -> None:
        self._v = float(max(mps, 0.0))
        self._lock = threading.Lock()

    def speed_mps(self) -> float:
        with self._lock:
            return self._v

    def set(self, mps: float) -> None:
        with self._lock:
            self._v = float(max(mps, 0.0))

    @property
    def quality(self) -> str:
        return "manual"


def parse_rmc(line: str) -> float | None:
    """解析 ``$GPRMC/$GNRMC`` 句子，返回地速 (m/s)；无效 / 非 RMC 返回 None。"""
    line = line.strip()
    if not line.startswith("$") or "RMC," not in line[:7]:
        return None
    body = line[1:].split("*")[0]
    fields = body.split(",")
    if len(fields) < 8:
        return None
    if fields[2] != "A":  # V = 无效定位
        return None
    try:
        knots = float(fields[7]) if fields[7] else 0.0
    except ValueError:
        return None
    return knots * KNOT_MPS


class NmeaSpeed:
    """从串口读取 NMEA 的车速源；``stale_s`` 内无有效定位则回退到手动值。

    串口读取线程只有在调用 :meth:`start` 后才启动；测试通过 :meth:`feed` 注入句子。
    """

    def __init__(
        self,
        port: str,
        baud: int,
        fallback: ManualSpeed,
        stale_s: float = 3.0,
        clock: Clock | None = None,
    ) -> None:
        self.port, self.baud = port, baud
        self.fallback = fallback
        self.stale_s = stale_s
        self.clock = clock or MonotonicClock()
        self._v: float | None = None
        self._t_fix: float = -1e9
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def feed(self, line: str) -> None:
        v = parse_rmc(line)
        if v is None:
            return
        with self._lock:
            self._v = v
            self._t_fix = self.clock.now()

    def speed_mps(self) -> float:
        with self._lock:
            fresh = self._v is not None and (self.clock.now() - self._t_fix) <= self.stale_s
            if fresh:
                return float(self._v)  # type: ignore[arg-type]
        return self.fallback.speed_mps()

    @property
    def quality(self) -> str:
        with self._lock:
            if self._v is None:
                return "stale"
            return "ok" if (self.clock.now() - self._t_fix) <= self.stale_s else "stale"

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="nmea-speed", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:  # pragma: no cover - 需要真实串口
        try:
            import serial  # type: ignore
        except ImportError:
            log.error("pyserial 未安装，NMEA 车速不可用，使用手动车速")
            return
        while not self._stop.is_set():
            try:
                with serial.Serial(self.port, self.baud, timeout=1.0) as ser:
                    while not self._stop.is_set():
                        raw = ser.readline()
                        if raw:
                            self.feed(raw.decode("ascii", errors="ignore"))
            except Exception as exc:  # noqa: BLE001
                log.warning("NMEA 串口错误 %s，3 s 后重试", exc)
                self._stop.wait(3.0)


class SharedSpeed:
    """供各线程共享的车速门面：可随时切换手动 / NMEA，并给 HMI 暴露设置接口。"""

    def __init__(self, manual: ManualSpeed, nmea: NmeaSpeed | None = None, use_nmea: bool = False) -> None:
        self.manual = manual
        self.nmea = nmea
        self._use_nmea = bool(use_nmea and nmea is not None)
        self._lock = threading.Lock()

    def speed_mps(self) -> float:
        with self._lock:
            src = self.nmea if self._use_nmea and self.nmea is not None else self.manual
        return src.speed_mps()

    @property
    def quality(self) -> str:
        with self._lock:
            src = self.nmea if self._use_nmea and self.nmea is not None else self.manual
        return src.quality

    @property
    def source(self) -> str:
        with self._lock:
            return "nmea" if self._use_nmea else "manual"

    def set_manual(self, mps: float) -> None:
        self.manual.set(mps)

    def use(self, source: str) -> None:
        with self._lock:
            self._use_nmea = source == "nmea" and self.nmea is not None
