import numpy as np

from smartview.clock import ReplayClock
from smartview.config import MachineConfig, RiskConfig, StorageConfig
from smartview.risk import RiskEngine
from smartview.risk.engine import CameraInfo
from smartview.storage import EventRecorder, EventStore, RingBuffer
from smartview.types import AlarmLevel, GroundPoint, Track


def _track(tid=1, x=10.0, cls="well_pipe", hits=3):
    g = GroundPoint(x_fwd=x, y_lat=0.0, row=1, in_path=True, foot_uv=(0, 0))
    t = Track(track_id=tid, cam_id="fwd", cls_id=0, cls_name=cls, bbox=np.zeros(4), score=0.8, hits=hits, age=hits)
    t.ground, t.dist_m, t.ttc_s, t.confirmed = g, x, x / 2.0, True
    return t


def _setup(tmp_path):
    clk = ReplayClock(0.0)
    engine = RiskEngine(RiskConfig(), MachineConfig(), {"fwd": CameraInfo("forward", (0, 3))}, clock=clk)
    store = EventStore(tmp_path / "ev.db")
    cfg = StorageConfig(pre_roll_s=1.0, post_roll_s=1.0, clip_dir=str(tmp_path / "clips"))
    rec = EventRecorder(store, cfg, engine=engine, clock=clk, wall_fn=lambda: 1_700_000_000.0 + clk.now(), cooldown_s=5.0)
    ring = RingBuffer(seconds=4.0, fps=10.0, max_width=320)
    rec.register_ring("fwd", ring)
    rec.set_speed_fn(lambda: 2.0)
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    return clk, engine, store, rec, ring, img


def test_event_lifecycle_snapshot_and_clip(tmp_path):
    clk, engine, store, rec, ring, img = _setup(tmp_path)
    for i in range(20):  # 2 s 前滚素材
        ring.push(i / 10.0, img)
        clk.set(i / 10.0)
    engine.update("fwd", [_track(x=10.0)])  # L2 → 事件开启
    eid = rec.open_event_id
    assert eid == 1 and engine.state().event_id == 1
    ev = store.get(eid)
    assert ev.level_max == AlarmLevel.L2 and ev.snapshot_path and ev.snapshot_path.endswith(".jpg") and ev.speed_mps == 2.0
    assert rec.tick() == 0  # 后滚未到期
    engine.update("fwd", [_track(x=5.0)])  # L3 → 更新 level_max / dist_min
    assert store.get(eid).level_max == AlarmLevel.L3 and store.get(eid).dist_min == 5.0
    for i in range(20, 32):
        clk.set(i / 10.0)
        ring.push(i / 10.0, img)
        engine.update("fwd", [_track(x=5.0)])
        rec.tick()
    ev = store.get(eid)
    assert ev.clip_path and ev.clip_path.endswith(".avi")
    # 目标消失 → L3 保持 3 s 后降级 → 事件关闭
    for i in range(32, 70):
        clk.set(i / 10.0)
        engine.update("fwd", [])
    assert rec.open_event_id is None and store.get(eid).ts_end is not None


def test_cooldown_extends_same_event(tmp_path):
    clk, engine, store, rec, ring, img = _setup(tmp_path)
    ring.push(0.0, img)
    engine.update("fwd", [_track(tid=1, x=10.0)])
    assert rec.open_event_id == 1
    t = 0.0
    while engine.state().level != AlarmLevel.L0:  # 让其降级关闭
        t += 0.5
        clk.set(t)
        engine.update("fwd", [])
    assert rec.open_event_id is None
    clk.set(t + 2.0)  # 冷却期内同一轨迹再次出现 → 延续事件 1
    engine.update("fwd", [_track(tid=1, x=9.0)])
    assert rec.open_event_id == 1 and store.stats()["total"] == 1
    # 关闭后超过冷却期的新目标 → 新事件
    t2 = t + 2.0
    while engine.state().level != AlarmLevel.L0:
        t2 += 0.5
        clk.set(t2)
        engine.update("fwd", [])
    clk.set(t2 + 10.0)
    engine.update("fwd", [_track(tid=9, x=8.0)])
    assert rec.open_event_id == 2 and store.stats()["total"] == 2


def test_ack_marks_event(tmp_path):
    clk, engine, store, rec, ring, img = _setup(tmp_path)
    engine.update("fwd", [_track(x=10.0)])
    engine.ack()
    assert store.get(1).acked and store.get(1).ack_ts is not None
