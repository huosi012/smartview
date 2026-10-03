from __future__ import annotations

import logging
import queue
import threading
from abc import ABC, abstractmethod

from smartview.clock import Clock, MonotonicClock
from smartview.types import AlarmState

log = logging.getLogger(__name__)


class AlarmSink(ABC):
    """报警输出端。``on_state`` 必须幂等：状态变化时与每 ``refresh_s`` 周期都会被调用。"""

    @abstractmethod
    def on_state(self, state: AlarmState) -> None: ...

    def close(self) -> None:
        return None


class AlarmDispatcher:
    """把风险引擎的状态分发给各 sink。

    * ``async_mode=True``：独立线程 + 队列，GPIO / 声音不会阻塞相机线程；并按 refresh_s 周期重发最近状态；
    * ``async_mode=False``：同步直达（回放 / 测试，确定性）。
    """

    def __init__(self, sinks: list[AlarmSink], refresh_s: float = 1.0, async_mode: bool = True, clock: Clock | None = None) -> None:
        self.sinks = list(sinks)
        self.refresh_s = refresh_s
        self.async_mode = async_mode
        self.clock = clock or MonotonicClock()
        self._q: queue.Queue[AlarmState | None] = queue.Queue()
        self._last: AlarmState | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def publish(self, state: AlarmState) -> None:
        self._last = state
        if self.async_mode:
            self._q.put(state)
        else:
            self._deliver(state)

    def _deliver(self, state: AlarmState) -> None:
        for s in self.sinks:
            try:
                s.on_state(state)
            except Exception:  # noqa: BLE001
                log.exception("报警输出 %s 异常", type(s).__name__)

    def refresh(self) -> None:
        if self._last is not None:
            self._deliver(self._last)

    def start(self) -> None:
        if not self.async_mode or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="alarm-dispatch", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                st = self._q.get(timeout=self.refresh_s)
            except queue.Empty:
                self.refresh()
                continue
            if st is None:
                break
            self._deliver(st)

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._q.put(None)
            self._thread.join(timeout)
            self._thread = None
        for s in self.sinks:
            try:
                s.close()
            except Exception:  # noqa: BLE001
                log.exception("关闭报警输出 %s 异常", type(s).__name__)
