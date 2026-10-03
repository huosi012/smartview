import numpy as np

from smartview.clock import ReplayClock
from smartview.config import MachineConfig, RiskConfig
from smartview.risk import RiskEngine, assess_track
from smartview.risk.engine import CameraInfo
from smartview.types import AlarmLevel, GroundPoint, Track

CAMS = {"fwd": CameraInfo("forward", (0, 3)), "hdr_l": CameraInfo("header", (0, 1)), "hdr_r": CameraInfo("header", (2, 3))}


def _track(cam="fwd", tid=1, cls="well_pipe", score=0.8, hits=3, x=10.0, y=0.0, ttc=None, speed=2.0, row=None):
    hp = 1.2 + 0.3
    g = GroundPoint(x_fwd=x, y_lat=y, row=row if row is not None else int(round(1.5 - y / 0.6)), in_path=abs(y) <= hp, foot_uv=(0, 0))
    t = Track(track_id=tid, cam_id=cam, cls_id=0, cls_name=cls, bbox=np.zeros(4), score=score, hits=hits, age=hits)
    t.ground, t.dist_m = g, x
    t.ttc_s = ttc if ttc is not None else x / speed
    t.confirmed = hits >= 3
    return t


def _engine(sens="medium"):
    clk = ReplayClock(0.0)
    cfg = RiskConfig(sensitivity=sens)
    eng = RiskEngine(cfg, MachineConfig(), CAMS, clock=clk)
    return eng, clk


def test_forward_levels_by_distance_and_path():
    cfg, m = RiskConfig(), MachineConfig()
    assert assess_track(_track(x=15.0), "forward", cfg, m).level == AlarmLevel.L1
    assert assess_track(_track(x=10.0), "forward", cfg, m).level == AlarmLevel.L2
    assert assess_track(_track(x=5.0), "forward", cfg, m).level == AlarmLevel.L3
    assert assess_track(_track(x=15.0, ttc=2.5), "forward", cfg, m).level == AlarmLevel.L3  # 高速：TTC 触发
    assert assess_track(_track(x=10.0, y=2.0), "forward", cfg, m).level == AlarmLevel.L1  # 邻近
    assert assess_track(_track(x=10.0, y=5.0), "forward", cfg, m).level == AlarmLevel.L0  # 路径外
    assert assess_track(_track(x=25.0), "forward", cfg, m).level == AlarmLevel.L0
    assert assess_track(_track(x=9.0, cls="person", score=0.5), "forward", cfg, m).level == AlarmLevel.L3
    assert assess_track(_track(x=5.0, hits=2), "forward", cfg, m).level == AlarmLevel.L1  # 未确认
    assert assess_track(_track(x=5.0, score=0.3), "forward", cfg, m).level == AlarmLevel.L0  # 置信度不足
    assert assess_track(_track(x=5.0, cls="unknown_obstacle", score=0.5), "forward", cfg, m).level == AlarmLevel.L1  # 加权不足


def test_header_levels():
    cfg, m = RiskConfig(), MachineConfig()
    assert assess_track(_track(cam="hdr_l", x=2.0, y=0.6), "header", cfg, m).level == AlarmLevel.L3
    assert assess_track(_track(cam="hdr_l", x=4.0, y=0.6), "header", cfg, m).level == AlarmLevel.L2
    assert assess_track(_track(cam="hdr_l", x=2.0, y=2.0), "header", cfg, m).level == AlarmLevel.L2
    assert assess_track(_track(cam="hdr_l", x=2.0, y=2.0, hits=2), "header", cfg, m).level == AlarmLevel.L1


def test_sensitivity_changes_confirmation():
    cfg_hi, cfg_lo, m = RiskConfig(sensitivity="high"), RiskConfig(sensitivity="low"), MachineConfig()
    assert assess_track(_track(x=5.0, hits=2, score=0.4), "forward", cfg_hi, m).level == AlarmLevel.L3
    assert assess_track(_track(x=5.0, hits=2, score=0.4), "forward", RiskConfig(), m).level == AlarmLevel.L1
    assert assess_track(_track(x=5.0, hits=3, score=0.4), "forward", cfg_lo, m).level == AlarmLevel.L0
    assert assess_track(_track(x=5.0, hits=4, score=0.5), "forward", cfg_lo, m).level == AlarmLevel.L3


def test_immediate_upgrade_and_held_downgrade():
    eng, clk = _engine()
    eng.update("fwd", [_track(x=10.0)])
    assert eng.state().level == AlarmLevel.L2
    eng.update("fwd", [_track(x=5.0)])
    assert eng.state().level == AlarmLevel.L3 and eng.state().buzzer_on and eng.state().lamp_on
    # 目标消失：L3 保持 hold_s(3 s) 后才降级
    for _ in range(5):
        clk.advance(0.5)
        eng.update("fwd", [])
    assert eng.state().level == AlarmLevel.L3
    clk.advance(0.9)  # t=3.4：距支撑消失（t=0.5）2.9 s，仍保持
    eng.update("fwd", [])
    assert eng.state().level == AlarmLevel.L3
    clk.advance(0.2)  # t=3.6：超过 hold_s=3 s → 降级
    eng.update("fwd", [])
    assert eng.state().level == AlarmLevel.L0 and not eng.state().buzzer_on


def test_two_camera_escalation():
    eng, clk = _engine()
    eng.update("fwd", [_track(x=10.0, row=1)])
    assert eng.state().level == AlarmLevel.L2
    eng.update("hdr_r", [_track(cam="hdr_r", x=2.5, y=2.0, hits=2)])  # 其它行、仅 L1 → 不升级
    assert eng.state().level == AlarmLevel.L2
    eng.update("hdr_l", [_track(cam="hdr_l", tid=7, x=2.5, y=2.0, hits=2)])  # 同覆盖行 L1 → 升级
    assert eng.state().level == AlarmLevel.L3
    assert "多相机同时确认" in eng.state().top.reasons


def test_two_cameras_both_l2_escalate():
    eng, clk = _engine()
    eng.update("fwd", [_track(x=10.0, y=2.0)])  # 邻近 → L1
    eng.update("hdr_l", [_track(cam="hdr_l", x=4.0, y=0.6)])  # 路径内 4 m → L2
    assert eng.state().level == AlarmLevel.L2
    eng.update("fwd", [_track(x=10.0)])  # 前视 L2 + 割台 L2 → L3
    assert eng.state().level == AlarmLevel.L3


def test_stale_camera_decays():
    eng, clk = _engine()
    eng.update("fwd", [_track(x=5.0)])
    assert eng.state().level == AlarmLevel.L3
    clk.advance(10.0)
    eng.tick()
    assert eng.state().level == AlarmLevel.L0


def test_ack_and_rearm():
    eng, clk = _engine()
    eng.update("fwd", [_track(x=10.0)])
    st = eng.ack()
    assert st.acked and not st.buzzer_on and st.lamp_on
    eng.update("fwd", [_track(x=10.0)])
    assert not eng.state().buzzer_on
    eng.update("fwd", [_track(x=5.0)])  # 更高等级 → 重新武装
    assert eng.state().buzzer_on and not eng.state().acked
    eng.ack()
    eng.update("fwd", [_track(tid=2, x=5.0)])  # 新目标 → 重新武装
    assert eng.state().buzzer_on


def test_mute_is_capped_and_expires():
    eng, clk = _engine()
    eng.update("fwd", [_track(x=5.0)])
    st = eng.mute(600)
    assert st.muted_until == clk.now() + 60.0 and not st.buzzer_on and st.lamp_on
    clk.advance(30)
    eng.update("fwd", [_track(x=5.0)])
    assert not eng.state().buzzer_on
    clk.advance(31)
    eng.update("fwd", [_track(x=5.0)])
    assert eng.state().buzzer_on


def test_sensor_fault_forces_visual_l1():
    eng, clk = _engine()
    eng.set_sensor_fault("hdr_l", ["画面冻结"])
    st = eng.state()
    assert st.level == AlarmLevel.L1 and st.sensor_fault and not st.buzzer_on
    assert "hdr_l" in st.fault_reasons[0]
    eng.set_sensor_fault("hdr_l", None)
    clk.advance(1.1)
    eng.tick()
    assert eng.state().level == AlarmLevel.L0 and not eng.state().sensor_fault


def test_subscribers_notified_on_change_only():
    eng, clk = _engine()
    seen = []
    eng.subscribe(lambda s: seen.append(s.level))
    eng.update("fwd", [_track(x=10.0)])
    eng.update("fwd", [_track(x=10.0)])
    eng.update("fwd", [_track(x=10.0)])
    assert seen == [AlarmLevel.L2]
    eng.update("fwd", [_track(x=5.0)])
    assert seen == [AlarmLevel.L2, AlarmLevel.L3]
    assert eng.state().message_zh().startswith("前方 5.0 m 井口钢管")
