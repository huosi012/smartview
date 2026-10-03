import numpy as np
import pytest
import yaml

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from smartview.config import SmartViewConfig  # noqa: E402
from smartview.hmi.server import create_app  # noqa: E402
from smartview.pipeline import SmartViewApp  # noqa: E402
from smartview.types import GroundPoint, Track  # noqa: E402


@pytest.fixture
def hmi(replay_config_path, tmp_path):
    data = yaml.safe_load(replay_config_path.read_text(encoding="utf-8"))
    data["storage"]["db_path"] = str(tmp_path / "events.db")
    data["storage"]["clip_dir"] = str(tmp_path / "clips")
    data["alarm"]["sinks"] = ["hmi"]
    cfg = SmartViewConfig.from_dict(data, base_dir=tmp_path)
    app = SmartViewApp(cfg, live=False, hmi=False)
    for w in app.workers.values():  # 各处理一帧，填充画面快照与环形缓存
        w.source.open()
        fr = w.source.read()
        w.process(fr)
    g = GroundPoint(x_fwd=5.0, y_lat=0.0, row=1, in_path=True, foot_uv=(320, 300))
    t = Track(track_id=1, cam_id="fwd", cls_id=0, cls_name="well_pipe", bbox=np.array([300, 250, 340, 300.0]), score=0.9, hits=5, age=5)
    t.ground, t.dist_m, t.ttc_s, t.confirmed = g, 5.0, 2.5, True
    app.engine.update("fwd", [t])
    client = TestClient(create_app(app.bus, app.controls))
    yield app, client
    app.shutdown()


def test_index_and_state(hmi):
    app, client = hmi
    r = client.get("/")
    assert r.status_code == 200 and "smartview" in r.text and "确认" in r.text
    s = client.get("/api/state").json()
    assert s["alarm"]["level"] == 3 and "井口钢管" in s["alarm"]["message"]
    assert s["cameras"]["fwd"]["has_image"] and s["cameras"]["hdr_l"]["health"]["status_zh"] == "正常"
    assert s["speed"]["kmh"] == 7.2 and s["settings"]["sensitivity"] == "medium"
    assert {c["id"] for c in s["settings"]["cameras"]} == {"fwd", "hdr_l"}


def test_ack_mute_unmute(hmi):
    app, client = hmi
    a = client.post("/api/ack").json()
    assert a["acked"] is True and a["buzzer_on"] is False and a["lamp_on"] is True
    m = client.post("/api/mute", json={"seconds": 30}).json()
    assert m["muted_until"] > 0
    assert client.post("/api/mute", json={"seconds": 0}).status_code == 422
    u = client.post("/api/unmute").json()
    assert u["muted_until"] == 0


def test_settings_validation(hmi):
    app, client = hmi
    r = client.put("/api/settings", json={"speed_kmh": 10.8, "sensitivity": "high"})
    assert r.status_code == 200 and r.json()["speed_kmh"] == 10.8 and r.json()["sensitivity"] == "high"
    assert app.speed.speed_mps() == pytest.approx(3.0)
    assert client.put("/api/settings", json={"sensitivity": "bogus"}).status_code == 422
    assert client.put("/api/settings", json={"speed_kmh": -1}).status_code == 422
    assert client.get("/api/settings").json()["speed_source"] == "manual"


def test_events_and_media(hmi):
    app, client = hmi
    j = client.get("/api/events").json()
    assert j["stats"]["total"] >= 1 and j["events"][0]["cam_id"] == "fwd"
    eid = j["events"][0]["event_id"]
    assert client.get(f"/api/events/{eid}").status_code == 200
    assert client.get("/api/events/9999").status_code == 404
    snap = client.get(f"/api/events/{eid}/snapshot.jpg")
    assert snap.status_code == 200 and snap.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/events/{eid}/clip").status_code == 404  # 后滚未完成


def test_mjpeg_and_single_jpeg(hmi):
    app, client = hmi
    with client.stream("GET", "/stream/fwd.mjpg?frames=2&fps=30") as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("multipart/x-mixed-replace")
        body = b"".join(r.iter_bytes())
    assert body.count(b"--frame") == 2 and b"\xff\xd8" in body
    j = client.get("/api/cam/fwd.jpg")
    assert j.status_code == 200 and j.content[:2] == b"\xff\xd8"
    assert client.get("/api/cam/nope.jpg").status_code == 200  # 占位图


def test_websocket_first_message_and_misc(hmi):
    app, client = hmi
    with client.websocket_connect("/ws") as ws:
        msg = ws.receive_json()
        assert "alarm" in msg and msg["alarm"]["level"] == 3
    assert client.post("/api/test-alarm", json={"level": 2}).status_code == 200
    p = client.post("/api/purge", json={}).json()
    assert p["ok"] is False  # 回放配置未启用吹扫
    assert client.get("/api/purge").json()["enabled"] is False
    assert client.get("/api/health").json()["cameras"]["fwd"]["ok"] is True
