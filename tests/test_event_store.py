import threading

from smartview.storage import EventStore
from smartview.types import AlarmLevel, Event


def _ev(ts=1000.0, level=AlarmLevel.L2, cam="fwd", tid=1):
    return Event(event_id=None, ts_start=ts, ts_end=None, level_max=level, cam_id=cam, cls_name="well_pipe", track_id=tid, dist_min=9.5, ttc_min=4.7, speed_mps=2.0, extra={"reasons": ["x"]})


def test_crud_and_ack(tmp_path):
    store = EventStore(tmp_path / "ev.db")
    assert store.journal_mode().lower() == "wal"
    eid = store.insert(_ev())
    assert eid == 1
    store.update(eid, level_max=AlarmLevel.L3, dist_min=4.2, clip_path="/x.avi")
    ev = store.get(eid)
    assert ev.level_max == AlarmLevel.L3 and ev.dist_min == 4.2 and ev.clip_path == "/x.avi" and ev.extra == {"reasons": ["x"]}
    store.ack(eid, 1001.0)
    assert store.get(eid).acked and store.get(eid).ack_ts == 1001.0
    store.insert(_ev(ts=1100.0, level=AlarmLevel.L2, tid=2))
    assert [e.event_id for e in store.list()] == [2, 1]
    assert [e.event_id for e in store.list(min_level=3)] == [1]
    assert [e.event_id for e in store.list(since=1050.0)] == [2]
    assert store.stats() == {"total": 2, "by_level": {"L2": 1, "L3": 1}}
    store.log_purge(1.0, "header", "manual")
    assert store.purge_count() == 1
    store.close()


def test_concurrent_reader_writer(tmp_path):
    store = EventStore(tmp_path / "ev.db")
    errors = []

    def writer():
        try:
            for i in range(50):
                store.insert(_ev(ts=float(i)))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def reader():
        try:
            for _ in range(50):
                store.list(limit=10)
                store.stats()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    ts = [threading.Thread(target=writer), threading.Thread(target=reader), threading.Thread(target=writer)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert not errors
    assert store.stats()["total"] == 100


def test_update_rejects_unknown_field(tmp_path):
    store = EventStore(":memory:")
    eid = store.insert(_ev())
    try:
        store.update(eid, bogus=1)
    except ValueError:
        pass
    else:
        raise AssertionError("应拒绝未知字段")
