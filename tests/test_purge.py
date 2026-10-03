from smartview.alarm import FakeGpioDriver, LensPurgeController
from smartview.clock import ReplayClock
from smartview.config import PurgeConfig


def _ctl(period_s=60, **kw):
    cfg = PurgeConfig(enabled=True, channels={"header": 18, "forward": 22}, burst_s=1.5, period_s=period_s, min_interval_s=10, max_duty=0.1, suppress_extra_s=0.5, **kw)
    clk = ReplayClock(0.0)
    drv = FakeGpioDriver()
    changes = []
    logs = []
    ctl = LensPurgeController(cfg, drv, clock=clk, on_change=lambda c, a: changes.append((c, a)), on_log=lambda t, c, r: logs.append((c, r)))
    return cfg, clk, drv, ctl, changes, logs


def test_manual_request_min_interval_and_suppression():
    cfg, clk, drv, ctl, changes, logs = _ctl()
    assert ctl.request("header", "manual")
    assert drv.pins[18] is True and ctl.is_active("header") and ctl.is_suppressed("header")
    assert not ctl.request("header", "manual")  # 进行中
    clk.advance(1.6)
    ctl.tick()
    assert drv.pins[18] is False and not ctl.is_active("header")
    assert ctl.is_suppressed("header")  # 结束后 0.5 s 内仍抑制
    clk.advance(0.6)
    assert not ctl.is_suppressed("header")
    assert not ctl.request("header", "manual")  # 最小间隔 10 s
    clk.advance(10)
    assert ctl.request("header", "manual")
    assert changes[:2] == [("header", True), ("header", False)] and logs[0] == ("header", "manual")
    assert ctl.status()["channels"]["header"]["count"] == 2
    assert not ctl.is_suppressed(None) and not ctl.is_suppressed("nope")


def test_periodic_and_dirty_triggers():
    cfg, clk, drv, ctl, changes, logs = _ctl()
    clk.advance(59)
    ctl.tick()
    assert not ctl.is_active("header")
    clk.advance(1.5)
    ctl.tick()
    assert ctl.is_active("header") and ctl.is_active("forward")
    assert all(r == "periodic" for _, r in logs)
    clk.advance(20)
    ctl.tick()
    assert ctl.on_lens_dirty("forward", True)
    assert not ctl.on_lens_dirty("forward", False)
    assert logs[-1] == ("forward", "lens_dirty")


def test_duty_cycle_limit():
    cfg, clk, drv, ctl, changes, logs = _ctl(period_s=0)  # 关闭定时吹扫，只看手动请求
    # 600 s 窗口内最多 60 s：每 10 s 一次 1.5 s → 第 41 次应被拒绝
    ok = 0
    for _ in range(45):
        if ctl.request("header", "manual"):
            ok += 1
        clk.advance(10.0)
        ctl.tick()
    assert ok == 40


def test_disabled_controller_is_inert():
    cfg = PurgeConfig(enabled=False)
    ctl = LensPurgeController(cfg, FakeGpioDriver(), clock=ReplayClock())
    assert not ctl.request("header") and ctl.status()["channels"] == {}
