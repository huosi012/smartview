from pathlib import Path

from smartview.alarm import AlarmDispatcher, ConsoleSink, FakeGpioDriver, GpioSink, MemorySink, SoundSink
from smartview.alarm.gpio import pattern
from smartview.clock import ReplayClock
from smartview.config import GpioConfig
from smartview.types import AlarmLevel, AlarmState, RiskAssessment


def _state(level, buzzer=None, acked=False, ts=0.0, tid=1):
    top = None
    if level > AlarmLevel.L0:
        top = RiskAssessment("fwd", tid, level, 0.8, 6.2, 3.1, ["x"], "well_pipe", 1, True)
    st = AlarmState(level=level, ts=ts, top=top, acked=acked)
    st.buzzer_on = (level >= AlarmLevel.L2 and not acked) if buzzer is None else buzzer
    st.lamp_on = level >= AlarmLevel.L2
    return st


def test_dispatcher_sync_and_console():
    mem, con = MemorySink(), ConsoleSink(printer=lambda s: None)
    d = AlarmDispatcher([mem, con], async_mode=False)
    d.publish(_state(AlarmLevel.L2))
    d.publish(_state(AlarmLevel.L2))
    d.publish(_state(AlarmLevel.L3))
    assert len(mem.states) == 3
    assert len(con.lines) == 2 and "井口钢管" in con.lines[1] and "[L3 危险]" in con.lines[1]
    d.refresh()
    assert len(mem.states) == 4


def test_gpio_patterns_and_active_low():
    drv = FakeGpioDriver()
    cfg = GpioConfig(buzzer_pin=12, lamp_pin=16, lamp_yellow_pin=18, active_high=False)
    clk = ReplayClock(0.0)
    sink = GpioSink(cfg, driver=drv, clock=clk)
    sink.on_state(_state(AlarmLevel.L3))
    assert drv.pins == {12: True, 16: True, 18: False}
    sink.on_state(_state(AlarmLevel.L2))
    assert sink.apply(0.1) == (True, True, False)
    assert sink.apply(0.6) == (False, True, False)  # 间歇
    sink.on_state(_state(AlarmLevel.L2, acked=True))
    assert sink.apply(0.1) == (False, True, False)  # 确认后蜂鸣停止、灯保持
    sink.on_state(_state(AlarmLevel.L1))
    assert drv.pins == {12: False, 16: False, 18: True}
    sink.close()
    assert drv.pins == {12: False, 16: False, 18: False}
    assert pattern(AlarmLevel.L0, False, 0.0) == (False, False, False)


def test_sound_sink_repeat_and_once(tmp_path):
    for n in (1, 2, 3):
        (tmp_path / f"L{n}.wav").write_bytes(b"RIFF")
    (tmp_path / "voice_L3.wav").write_bytes(b"RIFF")
    played: list[Path] = []
    clk = ReplayClock(0.0)
    s = SoundSink(tmp_path, repeat_interval_s=2.0, clock=clk, play_fn=played.append)
    s.on_state(_state(AlarmLevel.L1, ts=0.0))
    s.on_state(_state(AlarmLevel.L1, ts=0.5))
    assert [p.name for p in played] == ["L1.wav"]
    s.on_state(_state(AlarmLevel.L2, ts=1.0))
    s.on_state(_state(AlarmLevel.L2, ts=2.0))
    s.on_state(_state(AlarmLevel.L2, ts=3.1))
    assert [p.name for p in played] == ["L1.wav", "L2.wav", "L2.wav"]
    s.on_state(_state(AlarmLevel.L3, ts=3.2))
    assert played[-1].name == "voice_L3.wav"  # 语音优先
    s.on_state(_state(AlarmLevel.L3, ts=6.0, acked=True))
    assert len(played) == 4  # 确认后不再重复
