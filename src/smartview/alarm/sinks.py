from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from smartview.alarm.base import AlarmSink
from smartview.bus import StateBus
from smartview.clock import Clock, MonotonicClock
from smartview.types import AlarmLevel, AlarmState

log = logging.getLogger(__name__)


class MemorySink(AlarmSink):
    """测试用：记录收到的所有状态。"""

    def __init__(self) -> None:
        self.states: list[AlarmState] = []

    def on_state(self, state: AlarmState) -> None:
        self.states.append(state)


class ConsoleSink(AlarmSink):
    """控制台 / 日志输出：只在等级或目标变化时打印一行。"""

    def __init__(self, printer: Callable[[str], None] | None = None) -> None:
        self.printer = printer or (lambda s: print(s, flush=True))
        self._last_key = None
        self.lines: list[str] = []

    def on_state(self, state: AlarmState) -> None:
        key = (state.level, state.top.cam_id if state.top else None, state.top.track_id if state.top else None, state.acked, state.sensor_fault)
        if key == self._last_key:
            return
        self._last_key = key
        tag = f"[L{int(state.level)} {state.level_zh}]"
        where = f"（{state.top.cam_id} #{state.top.track_id}）" if state.top else ""
        extra = " 已确认" if state.acked else ""
        line = f"t={state.ts:7.2f}s {tag} {state.message_zh()}{where}{extra}"
        self.lines.append(line)
        self.printer(line)


class SoundSink(AlarmSink):
    """用外部播放器播放提示音（aplay / ffplay / paplay）。

    文件查找顺序：``voice_L{n}.wav``（中文语音，用户自备）→ ``L{n}.wav``（numpy 生成的提示音）。
    L2/L3 在 ``buzzer_on`` 期间按 ``repeat_interval_s`` 重复；L1 只提示一次。
    """

    def __init__(
        self,
        wav_dir: str | Path,
        player: str = "aplay",
        repeat_interval_s: float = 2.0,
        clock: Clock | None = None,
        play_fn: Callable[[Path], None] | None = None,
    ) -> None:
        self.wav_dir = Path(wav_dir)
        self.repeat_interval_s = repeat_interval_s
        self.clock = clock or MonotonicClock()
        self._last_play_ts = -1e9
        self._last_level = AlarmLevel.L0
        self._last_key = None
        self._proc: subprocess.Popen | None = None
        if play_fn is not None:
            self._play = play_fn
        else:
            exe = shutil.which(player)
            if exe is None:
                log.warning("未找到播放器 %s，声音提示停用（蜂鸣器为主报警）", player)
                self._play = None  # type: ignore[assignment]
            else:
                self._exe = exe
                self._play = self._play_subprocess

    def _file_for(self, level: AlarmLevel) -> Path | None:
        for name in (f"voice_L{int(level)}.wav", f"L{int(level)}.wav"):
            p = self.wav_dir / name
            if p.exists():
                return p
        return None

    def _play_subprocess(self, path: Path) -> None:  # pragma: no cover - 需要音频设备
        if self._proc is not None and self._proc.poll() is None:
            return
        args = [self._exe, "-q", str(path)] if "aplay" in self._exe else [self._exe, "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)]
        self._proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def on_state(self, state: AlarmState) -> None:
        if self._play is None:
            return
        now = state.ts if state.ts else self.clock.now()
        key = (state.level, state.top.track_id if state.top else None)
        changed = key != self._last_key
        self._last_key = key
        if state.level == AlarmLevel.L0:
            self._last_level = state.level
            return
        should = False
        if state.level >= AlarmLevel.L2 and state.buzzer_on:
            should = changed or (now - self._last_play_ts) >= self.repeat_interval_s
        elif state.level == AlarmLevel.L1:
            should = changed and self._last_level != AlarmLevel.L1
        self._last_level = state.level
        if should:
            f = self._file_for(state.level)
            if f is not None:
                self._play(f)
                self._last_play_ts = now


class HmiSink(AlarmSink):
    def __init__(self, bus: StateBus) -> None:
        self.bus = bus

    def on_state(self, state: AlarmState) -> None:
        self.bus.set_alarm(state)
