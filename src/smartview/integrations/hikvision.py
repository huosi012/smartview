"""海康威视（Hikvision）网络相机接入。

* 取流：标准 RTSP（主码流 ``/Streaming/Channels/101``，子码流 ``102``），由 ``OpenCVSource`` 直接拉取；
* 控制：ISAPI（HTTP Digest 认证）
    - 设备信息 ``GET /ISAPI/System/deviceInfo``
    - 报警输出继电器 ``PUT /ISAPI/System/IO/outputs/{n}/trigger``（high / low）—— 接外置蜂鸣器 / 警灯，最通用
    - 抓图 ``GET /ISAPI/Streaming/channels/{n}01/picture``
    - 可配置扩展请求（声光警戒机型的语音 / 白光灯，端点因机型而异，需按相机 ISAPI 文档核对）
    - 双向音频：``/ISAPI/System/TwoWayAudio/channels/{n}/open|audioData|close``，把 WAV 转 G.711 µ-law 推给内置喇叭机型
* :class:`HikvisionAlarmSink`：把风险引擎等级映射为相机侧报警（继电器脉冲 + 可选语音），尊重确认 / 静音。

**真机验证提示**：ISAPI 行为随固件差异较大，上线前用 ``smartview hik-test`` 逐项验证。
"""

from __future__ import annotations

import logging
import queue
import threading
import wave
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

import numpy as np

from smartview.alarm.base import AlarmSink
from smartview.clock import Clock, MonotonicClock
from smartview.config import HikvisionConfig, HikvisionExtraRequest
from smartview.types import AlarmLevel, AlarmState

log = logging.getLogger(__name__)

IO_TRIGGER_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<IOPortData version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">'
    "<outputState>{state}</outputState></IOPortData>"
)


def rtsp_url(host: str, user: str, password: str, channel: int = 1, sub: bool = False, port: int = 554) -> str:
    """海康 RTSP 地址：主码流 x01，子码流 x02（用户名/密码做 URL 转义）。"""
    stream = f"{channel}0{2 if sub else 1}"
    return f"rtsp://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/Streaming/Channels/{stream}"


def _xml_text(root: ET.Element, tag: str) -> str | None:
    for el in root.iter():
        if el.tag.split("}")[-1] == tag:
            return el.text
    return None


def wav_to_g711_ulaw(path: str | Path) -> bytes:
    """WAV（任意采样率 / 声道 / 16 bit）→ 8 kHz 单声道 G.711 µ-law 字节流。"""
    with wave.open(str(path), "rb") as w:
        n_ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        pcm = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sw == 1:
        pcm = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError("仅支持 8/16 bit PCM WAV")
    if n_ch > 1:
        pcm = pcm.reshape(-1, n_ch).mean(axis=1)
    if sr != 8000:
        t_src = np.arange(len(pcm)) / sr
        t_dst = np.arange(0, t_src[-1] if len(t_src) else 0, 1 / 8000)
        pcm = np.interp(t_dst, t_src, pcm).astype(np.float32)
    # µ-law 编码（G.711）
    mu = 255.0
    x = np.clip(pcm, -1.0, 1.0)
    y = np.sign(x) * np.log1p(mu * np.abs(x)) / np.log1p(mu)
    q = np.round((y + 1.0) / 2.0 * 255.0).astype(np.int32).clip(0, 255)
    return (255 - q).astype(np.uint8).tobytes()  # 按 G.711 约定取反


class HikvisionISAPI:
    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        port: int = 80,
        https: bool = False,
        timeout: float = 3.0,
        transport=None,
    ) -> None:
        import httpx

        self.base = f"{'https' if https else 'http'}://{host}:{port}"
        self.client = httpx.Client(
            base_url=self.base,
            auth=httpx.DigestAuth(user, password),
            timeout=timeout,
            transport=transport,
            verify=not https or False,
        )
        self.host = host

    # ---------------------------------------------------------------- basics
    def request(self, method: str, path: str, body: str | bytes | None = None, content_type: str = "application/xml"):
        headers = {"Content-Type": content_type} if body is not None else {}
        return self.client.request(method, path, content=body, headers=headers)

    def device_info(self) -> dict[str, str | None]:
        r = self.request("GET", "/ISAPI/System/deviceInfo")
        r.raise_for_status()
        root = ET.fromstring(r.text)
        return {k: _xml_text(root, k) for k in ("deviceName", "model", "serialNumber", "firmwareVersion", "deviceType")}

    def set_output(self, port: int, on: bool) -> bool:
        r = self.request("PUT", f"/ISAPI/System/IO/outputs/{port}/trigger", IO_TRIGGER_XML.format(state="high" if on else "low"))
        ok = r.status_code == 200
        if ok and r.text:
            try:
                code = _xml_text(ET.fromstring(r.text), "statusCode")
                ok = code in (None, "1")
            except ET.ParseError:
                pass
        if not ok:
            log.warning("海康报警输出 %s 设置失败: HTTP %s %s", port, r.status_code, r.text[:120])
        return ok

    def pulse_output(self, port: int, seconds: float) -> bool:
        ok = self.set_output(port, True)
        if ok:
            threading.Timer(seconds, lambda: self.set_output(port, False)).start()
        return ok

    def snapshot(self, channel: int = 1) -> bytes:
        r = self.request("GET", f"/ISAPI/Streaming/channels/{channel}01/picture")
        r.raise_for_status()
        return r.content

    def extra(self, req: HikvisionExtraRequest) -> bool:
        r = self.request(req.method, req.path, req.body, req.content_type)
        if r.status_code != 200:
            log.warning("海康扩展请求 %s %s 失败: HTTP %s", req.method, req.path, r.status_code)
        return r.status_code == 200

    # ------------------------------------------------------------ two-way audio
    def play_wav(self, wav_path: str | Path, channel: int = 1, chunk_ms: int = 40) -> bool:
        """通过双向音频通道向相机喇叭播放 WAV（G.711 µ-law，8 kHz）。固件差异大，需真机验证。"""
        data = wav_to_g711_ulaw(wav_path)
        base = f"/ISAPI/System/TwoWayAudio/channels/{channel}"
        r = self.request("PUT", f"{base}/open")
        if r.status_code != 200:
            log.warning("双向音频打开失败: HTTP %s %s", r.status_code, r.text[:120])
            return False
        try:
            step = 8 * chunk_ms  # 8 kHz × 1 byte
            for i in range(0, len(data), step):
                rr = self.request("PUT", f"{base}/audioData", data[i : i + step], "application/octet-stream")
                if rr.status_code not in (200, 204):
                    log.warning("双向音频发送失败: HTTP %s", rr.status_code)
                    return False
                threading.Event().wait(chunk_ms / 1000.0)
            return True
        finally:
            self.request("PUT", f"{base}/close")

    def close(self) -> None:
        self.client.close()


class HikvisionAlarmSink(AlarmSink):
    """等级 ≥ min_level 且蜂鸣有效（未确认 / 未静音）时触发相机报警输出；降级后关闭。ISAPI 调用在独立线程串行执行。"""

    def __init__(self, cfg: HikvisionConfig, isapi: HikvisionISAPI | None = None, clock: Clock | None = None, async_mode: bool = True) -> None:
        import os

        self.cfg = cfg
        self.clock = clock or MonotonicClock()
        password = os.environ.get(cfg.password_env, "") if cfg.password_env else cfg.password
        self.isapi = isapi or HikvisionISAPI(cfg.host, cfg.user, password, cfg.port, cfg.https, cfg.timeout_s)
        self._last_trigger = -1e9
        self._output_on = False
        self._q: queue.Queue = queue.Queue()
        self.async_mode = async_mode
        self.calls: list[str] = []  # 记录动作（测试 / 诊断）
        if async_mode:
            threading.Thread(target=self._worker, name="hik-alarm", daemon=True).start()

    def _run(self, fn, label: str) -> None:
        self.calls.append(label)
        if self.async_mode:
            self._q.put(fn)
        else:
            fn()

    def _worker(self) -> None:  # pragma: no cover - 线程
        while True:
            fn = self._q.get()
            if fn is None:
                break
            try:
                fn()
            except Exception:  # noqa: BLE001
                log.exception("海康报警调用异常")

    def on_state(self, state: AlarmState) -> None:
        now = self.clock.now()
        active = state.level >= AlarmLevel(self.cfg.min_level) and state.buzzer_on
        if active:
            if now - self._last_trigger >= self.cfg.min_interval_s:
                self._last_trigger = now
                self._output_on = True
                port, secs = self.cfg.output_port, self.cfg.pulse_s
                self._run(lambda: self.isapi.pulse_output(port, secs), f"pulse:{port}")
                if self.cfg.audio_alarm is not None:
                    req = self.cfg.audio_alarm
                    self._run(lambda: self.isapi.extra(req), f"extra:{req.path}")
                if self.cfg.audio_wav:
                    wav = self.cfg.audio_wav
                    self._run(lambda: self.isapi.play_wav(wav), "wav")
        elif self._output_on and state.level < AlarmLevel(self.cfg.min_level):
            self._output_on = False
            port = self.cfg.output_port
            self._run(lambda: self.isapi.set_output(port, False), f"off:{port}")

    def close(self) -> None:
        try:
            if self._output_on:
                self.isapi.set_output(self.cfg.output_port, False)
        finally:
            if self.async_mode:
                self._q.put(None)
            self.isapi.close()
