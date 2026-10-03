"""时钟抽象。

所有与"持续时间"相关的逻辑（TTC、滞回、冷却、吹扫间隔）一律使用单调时间，
真机用 :class:`MonotonicClock`，回放与测试用 :class:`ReplayClock`，保证确定性。
墙上时间只用于事件记录。
"""

from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    def now(self) -> float:  # pragma: no cover - protocol
        ...


class MonotonicClock:
    """真机时钟：``time.monotonic``。"""

    def now(self) -> float:
        return time.monotonic()


class ReplayClock:
    """回放/测试时钟：由调用方显式推进。"""

    def __init__(self, start: float = 0.0) -> None:
        self._t = float(start)

    def now(self) -> float:
        return self._t

    def set(self, t: float) -> None:
        if t < self._t:
            raise ValueError(f"ReplayClock cannot go backwards: {t} < {self._t}")
        self._t = float(t)

    def advance(self, dt: float) -> float:
        if dt < 0:
            raise ValueError("dt must be >= 0")
        self._t += float(dt)
        return self._t


FakeClock = ReplayClock
