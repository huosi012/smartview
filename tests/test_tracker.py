import numpy as np

from smartview.track import ByteTrackLite
from smartview.types import Detection


def _d(x, y, w=20, h=40, score=0.9, cls="stone"):
    return Detection(bbox=np.array([x, y, x + w, y + h], dtype=np.float32), score=score, cls_id=0, cls_name=cls)


def test_confirmation_and_stable_id():
    tr = ByteTrackLite(min_hits=3, max_age=5)
    out = []
    for i in range(6):
        out.append(tr.update([_d(100 + 2 * i, 100 + 3 * i)], ts=i / 15))
    assert out[0] == [] and out[1] == []
    assert len(out[2]) == 1 and out[2][0].confirmed
    ids = {t.track_id for frame in out[2:] for t in frame}
    assert ids == {out[2][0].track_id}
    assert out[-1][0].hits == 6


def test_gap_keeps_id_and_long_gap_drops():
    tr = ByteTrackLite(min_hits=2, max_age=3)
    tr.update([_d(100, 100)], 0.0)
    t1 = tr.update([_d(102, 103)], 0.1)
    tid = t1[0].track_id
    # 丢失 2 帧（<= max_age）后再出现：ID 保持
    assert tr.update([], 0.2) == []
    assert tr.update([], 0.3) == []
    t2 = tr.update([_d(110, 115)], 0.4)
    assert len(t2) == 1 and t2[0].track_id == tid
    # 丢失超过 max_age：轨迹删除，新目标获得新 ID
    for k in range(5):
        tr.update([], 0.5 + 0.1 * k)
    t3 = tr.update([_d(112, 118)], 1.1)
    assert t3 == []  # 新轨迹尚未确认
    t3 = tr.update([_d(113, 119)], 1.2)
    assert t3[0].track_id != tid


def test_low_score_second_stage_recovers():
    tr = ByteTrackLite(min_hits=1, max_age=3, conf_high=0.5, conf_low=0.1)
    tr.update([_d(100, 100, score=0.9)], 0.0)
    out = tr.update([_d(101, 101, score=0.2)], 0.1)  # 低分检测只用于维持已有轨迹
    assert len(out) == 1 and out[0].hits == 2
    out2 = tr.update([_d(300, 300, score=0.2)], 0.2)  # 低分检测不新建轨迹
    assert all(t.bbox[0] < 200 for t in tr.tracks)
    assert out2 == []


def test_two_objects_distinct_ids():
    tr = ByteTrackLite(min_hits=1)
    out = tr.update([_d(100, 100), _d(300, 100)], 0.0)
    assert len(out) == 2 and out[0].track_id != out[1].track_id
    out = tr.update([_d(302, 101), _d(101, 102)], 0.1)  # 顺序颠倒仍正确关联
    by_x = sorted(out, key=lambda t: t.bbox[0])
    assert by_x[0].hits == 2 and by_x[1].hits == 2


def test_small_jittering_box_keeps_id():
    """远处 4 px 小框每帧抖动 3 px（IoU≈0）仍应保持同一 ID。"""
    tr = ByteTrackLite(min_hits=2, max_age=3)
    ids = set()
    for i in range(10):
        dx, dy = (3, 0) if i % 2 else (0, 3)
        out = tr.update([_d(300 + dx, 150 + dy, w=4, h=5)], ts=i / 15)
        ids.update(t.track_id for t in out)
    assert len(ids) == 1
    # 大框不启用距离兜底：相距 30 px 的大框视为新目标
    tr2 = ByteTrackLite(min_hits=1)
    a = tr2.update([_d(100, 100, w=60, h=80)], 0.0)
    b = tr2.update([_d(190, 100, w=60, h=80)], 0.1)
    assert a[0].track_id != b[0].track_id
