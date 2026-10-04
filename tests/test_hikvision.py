import time

import httpx
import pytest
from pydantic import ValidationError

from smartview.clock import ReplayClock
from smartview.config import HikvisionConfig, HikvisionExtraRequest, SmartViewConfig
from smartview.integrations.hikvision import HikvisionAlarmSink, HikvisionISAPI, rtsp_url, wav_to_g711_ulaw
from smartview.types import AlarmLevel, AlarmState, RiskAssessment


class FakeCamera:
    """模拟海康 ISAPI：首次无 Authorization 返回 401 Digest 质询，其后记录请求。"""

    def __init__(self):
        self.requests: list[tuple[str, str, bytes]] = []
        self.output_state = "low"

    def handler(self, request: httpx.Request) -> httpx.Response:
        if "Authorization" not in request.headers:
            return httpx.Response(401, headers={"WWW-Authenticate": 'Digest realm="IP Camera", nonce="abc123", qop="auth"'})
        assert request.headers["Authorization"].startswith("Digest ")
        body = request.read()
        self.requests.append((request.method, request.url.path, body))
        p = request.url.path
        if p == "/ISAPI/System/deviceInfo":
            return httpx.Response(200, text='<?xml version="1.0"?><DeviceInfo xmlns="http://www.isapi.org/ver20/XMLSchema"><deviceName>Field Cam</deviceName><model>DS-2CD2T47G2-LSU/SL</model><serialNumber>SN1</serialNumber><firmwareVersion>V5.7.3</firmwareVersion></DeviceInfo>')
        if p.startswith("/ISAPI/System/IO/outputs/") and p.endswith("/trigger"):
            self.output_state = "high" if b"<outputState>high</outputState>" in body else "low"
            return httpx.Response(200, text='<ResponseStatus><statusCode>1</statusCode><statusString>OK</statusString></ResponseStatus>')
        if p.endswith("/picture"):
            return httpx.Response(200, content=b"\xff\xd8fakejpeg")
        if "/TwoWayAudio/" in p:
            return httpx.Response(200, text="<ResponseStatus><statusCode>1</statusCode></ResponseStatus>")
        return httpx.Response(404)


def _isapi(cam):
    return HikvisionISAPI("cam.local", "admin", "secret", transport=httpx.MockTransport(cam.handler))


def test_rtsp_url_and_ulaw(repo_root):
    assert rtsp_url("192.168.1.64", "admin", "p@ss/word") == "rtsp://admin:p%40ss%2Fword@192.168.1.64:554/Streaming/Channels/101"
    assert rtsp_url("10.0.0.5", "u", "p", channel=2, sub=True, port=5540).endswith(":5540/Streaming/Channels/202")
    data = wav_to_g711_ulaw(repo_root / "assets" / "sounds" / "L1.wav")
    assert abs(len(data) - 0.18 * 8000) < 80  # 0.18 s @ 8 kHz


def test_isapi_digest_and_outputs():
    cam = FakeCamera()
    api = _isapi(cam)
    info = api.device_info()
    assert info["model"].startswith("DS-2CD") and info["deviceName"] == "Field Cam"
    assert api.set_output(1, True) and cam.output_state == "high"
    assert api.set_output(1, False) and cam.output_state == "low"
    assert api.snapshot(1).startswith(b"\xff\xd8")
    assert api.pulse_output(2, 0.05)
    assert cam.output_state == "high"
    time.sleep(0.2)
    assert cam.output_state == "low"
    assert any(p == "/ISAPI/System/IO/outputs/2/trigger" for _, p, _ in cam.requests)
    api.close()


def test_two_way_audio_play(repo_root):
    cam = FakeCamera()
    api = _isapi(cam)
    assert api.play_wav(repo_root / "assets" / "sounds" / "L1.wav", chunk_ms=100)
    paths = [p for _, p, _ in cam.requests if "TwoWayAudio" in p]
    assert paths[0].endswith("/open") and paths[-1].endswith("/close") and any(p.endswith("/audioData") for p in paths)
    api.close()


def _state(level, buzzer=True, ts=0.0):
    top = RiskAssessment("fwd", 1, level, 0.9, 5.0, 2.5, ["x"], "well_pipe", 1, True) if level else None
    st = AlarmState(level=level, ts=ts, top=top)
    st.buzzer_on = buzzer and level >= AlarmLevel.L2
    st.lamp_on = level >= AlarmLevel.L2
    return st


def test_alarm_sink_levels_interval_and_ack():
    cam = FakeCamera()
    clk = ReplayClock(0.0)
    cfg = HikvisionConfig(host="cam.local", user="admin", password="secret", output_port=1, pulse_s=0.05, min_interval_s=5, min_level=2,
                          audio_alarm=HikvisionExtraRequest(method="PUT", path="/ISAPI/Custom/AudioAlarm", body="<x/>"))
    sink = HikvisionAlarmSink(cfg, isapi=_isapi(cam), clock=clk, async_mode=False)
    sink.on_state(_state(AlarmLevel.L1))
    assert sink.calls == []
    sink.on_state(_state(AlarmLevel.L2))
    assert sink.calls == ["pulse:1", "extra:/ISAPI/Custom/AudioAlarm"] and cam.output_state == "high"
    clk.advance(2)
    sink.on_state(_state(AlarmLevel.L3))  # 间隔内不重复触发
    assert len(sink.calls) == 2
    clk.advance(4)
    sink.on_state(_state(AlarmLevel.L3))
    assert sink.calls.count("pulse:1") == 2
    sink.on_state(_state(AlarmLevel.L3, buzzer=False))  # 已确认 / 静音：不再触发
    assert sink.calls.count("pulse:1") == 2
    sink.on_state(_state(AlarmLevel.L0))
    assert sink.calls[-1] == "off:1"
    time.sleep(0.1)
    assert cam.output_state == "low"
    sink.close()


def test_config_accepts_cloud_and_hikvision(monkeypatch):
    monkeypatch.setenv("HIK_PW", "env-secret")
    cfg = SmartViewConfig.from_dict({
        "alarm": {"sinks": ["console", "hikvision"], "hikvision": {"host": "10.0.0.8", "password_env": "HIK_PW"}},
        "cloud": {"enabled": True, "url": "https://cloud.example.com", "api_key": "k", "frame_fps": 0.5},
    })
    assert cfg.alarm.hikvision.host == "10.0.0.8" and cfg.cloud.frame_fps == 0.5
    with pytest.raises(ValidationError):
        SmartViewConfig.from_dict({"alarm": {"sinks": ["bogus"]}})
