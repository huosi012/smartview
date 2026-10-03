"""SmartViewApp：按配置装配全部组件；``run_sync``（回放 / 测试）与 ``run_threaded``（真机）。"""

from __future__ import annotations

import logging
import os
import shutil
import signal
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from smartview.alarm import (
    AlarmDispatcher,
    ConsoleSink,
    GpioSink,
    HmiSink,
    LensPurgeController,
    SoundSink,
    make_gpio_driver,
)
from smartview.alarm.gpio import FakeGpioDriver
from smartview.bus import StateBus
from smartview.capture import build_source
from smartview.clock import MonotonicClock, ReplayClock
from smartview.config import SmartViewConfig
from smartview.detect import RegionMask, build_detector
from smartview.geometry import GroundProjector, ManualSpeed, NmeaSpeed, SharedSpeed
from smartview.health import HealthMonitor
from smartview.pipeline.camera_worker import CameraWorker, jsonl_writer
from smartview.pipeline.controls import Controls
from smartview.risk import RiskEngine
from smartview.risk.engine import CameraInfo
from smartview.storage import EventRecorder, EventStore, RingBuffer
from smartview.track import ByteTrackLite
from smartview.types import AlarmLevel, AlarmState

log = logging.getLogger(__name__)


@dataclass
class RunSummary:
    frames: dict[str, int] = field(default_factory=dict)
    max_level: AlarmLevel = AlarmLevel.L0
    first_level_ts: dict[int, float] = field(default_factory=dict)
    events: int = 0
    duration_s: float = 0.0
    wall_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "frames": self.frames,
            "max_level": int(self.max_level),
            "first_level_ts": {f"L{k}": round(v, 3) for k, v in self.first_level_ts.items()},
            "events": self.events,
            "duration_s": round(self.duration_s, 2),
            "wall_s": round(self.wall_s, 2),
        }


class SmartViewApp:
    def __init__(
        self,
        cfg: SmartViewConfig,
        live: bool = False,
        hmi: bool | None = None,
        realtime: bool = False,
        log_detections: str | None = None,
        collect: bool = False,
        seed: int | None = None,
        duration_s: float | None = None,
        console_printer=None,
        prefer_real_gpio: bool | None = None,
    ) -> None:
        self.cfg = cfg
        self.live = live
        self.realtime = realtime
        self.hmi_enabled = cfg.hmi.enabled if hmi is None else hmi
        self.collect = collect
        self.seed = seed
        self.duration_s = duration_s
        self.console_printer = console_printer
        self.prefer_real_gpio = live if prefer_real_gpio is None else prefer_real_gpio
        self.clock = MonotonicClock() if live else ReplayClock(0.0)
        self._epoch = time.time()
        self.bus = StateBus()
        self.stop_event = threading.Event()
        self.timeline: list[tuple[float, AlarmState]] = []
        self._det_log = jsonl_writer(log_detections) if log_detections else None
        self.workers: dict[str, CameraWorker] = {}
        self.store: EventStore | None = None
        self.recorder: EventRecorder | None = None
        self.purge: LensPurgeController | None = None
        self.gpio_driver = None
        self._events_at_start = 0
        self._hmi_server = None
        self._hmi_thread: threading.Thread | None = None
        self._threads: list[threading.Thread] = []
        self._build()

    # ------------------------------------------------------------------ build
    def wall_now(self) -> float:
        return time.time() if self.live else self._epoch + self.clock.now()

    def _build(self) -> None:
        cfg = self.cfg
        manual = ManualSpeed(cfg.speed.manual_mps)
        nmea = None
        if cfg.speed.source == "nmea":
            nmea = NmeaSpeed(cfg.speed.nmea_port, cfg.speed.baud, manual, cfg.speed.stale_s, clock=self.clock)
        self.speed = SharedSpeed(manual, nmea, use_nmea=cfg.speed.source == "nmea")

        cams = {c.id: CameraInfo(c.role, c.rows_covered) for c in cfg.cameras}
        self.engine = RiskEngine(cfg.risk, cfg.machine, cams, clock=self.clock)
        self.engine.subscribe(self._on_state)

        need_gpio = "gpio" in cfg.alarm.sinks or cfg.alarm.purge.enabled
        if need_gpio:
            self.gpio_driver = make_gpio_driver(cfg.alarm.gpio.mode, cfg.alarm.gpio.active_high, prefer_real=self.prefer_real_gpio)
        sinks = []
        for name in cfg.alarm.sinks:
            if name == "console":
                sinks.append(ConsoleSink(printer=self.console_printer))
            elif name == "sound":
                sinks.append(SoundSink(cfg.resolve(cfg.alarm.sound.wav_dir) or cfg.alarm.sound.wav_dir, cfg.alarm.sound.player, cfg.alarm.sound.repeat_interval_s, clock=self.clock))
            elif name == "gpio":
                gs = GpioSink(cfg.alarm.gpio, driver=self.gpio_driver, clock=self.clock)
                if self.live:
                    gs.start()
                sinks.append(gs)
            elif name == "hmi":
                sinks.append(HmiSink(self.bus))
        self.dispatcher = AlarmDispatcher(sinks, cfg.alarm.refresh_s, async_mode=self.live, clock=self.clock)
        self.engine.subscribe(self.dispatcher.publish)

        if cfg.storage.enabled:
            self.store = EventStore(cfg.resolve(cfg.storage.db_path) or cfg.storage.db_path)
            self.recorder = EventRecorder(
                self.store,
                cfg.storage,
                engine=self.engine,
                clock=self.clock,
                wall_fn=self.wall_now,
                cooldown_s=cfg.risk.cooldown_s,
                clip_dir=cfg.resolve(cfg.storage.clip_dir),
                async_clips=self.live,
            )
            self.recorder.set_speed_fn(self.speed.speed_mps)
            self._events_at_start = self.store.stats()["total"]

        if cfg.alarm.purge.enabled:
            self.purge = LensPurgeController(
                cfg.alarm.purge,
                self.gpio_driver or FakeGpioDriver(),
                clock=self.clock,
                on_change=self._on_purge_change,
                on_log=(lambda t, c, r: self.store.log_purge(self.wall_now(), c, r)) if self.store else None,
            )

        ring_seconds = cfg.storage.pre_roll_s + cfg.storage.post_roll_s + 2.0
        for cam in cfg.cameras:
            source = build_source(cam, cfg.speed, clock=self.clock, seed=self.seed, duration_s=self.duration_s)
            projector = GroundProjector(cam, cfg.machine)
            region = RegionMask.from_camera(cam, base_dir=cfg.base_dir)
            detector = build_detector(cfg.detector, projector=projector, region=region, base_dir=cfg.base_dir)
            tracker = ByteTrackLite(
                cam.id,
                conf_high=cfg.tracker.conf_high,
                conf_low=cfg.tracker.conf_low,
                iou_high=cfg.tracker.iou_high,
                iou_low=cfg.tracker.iou_low,
                min_hits=cfg.tracker.min_hits,
                max_age=cfg.tracker.max_age,
            )
            health = HealthMonitor(cam.id, clock=self.clock)
            ring = RingBuffer(ring_seconds, cfg.storage.ring_fps, cfg.storage.ring_max_width, cfg.storage.jpeg_quality)
            if self.recorder is not None:
                self.recorder.register_ring(cam.id, ring)
            self.workers[cam.id] = CameraWorker(
                cam, cfg, source, detector, region, projector, tracker, health, ring, self.engine, self.bus, self.speed, self.clock,
                purge=self.purge, det_log=self._det_log, collect=self.collect,
            )
        self.controls = Controls(self)
        self.publish_speed()
        self.publish_purge()

    # ---------------------------------------------------------------- hooks
    def _on_state(self, st: AlarmState) -> None:
        self.timeline.append((st.ts, st))

    def _on_purge_change(self, channel: str, active: bool) -> None:
        for cam in self.cfg.cameras:
            if cam.purge_channel == channel:
                self.engine.set_purging(cam.id, active)
        self.publish_purge()

    def publish_speed(self) -> None:
        self.bus.set_speed(self.speed.speed_mps(), self.speed.source, self.speed.quality)

    def publish_purge(self) -> None:
        if self.purge is not None:
            self.bus.set_purge(self.purge.status(self.clock.now()))

    def _publish_system(self) -> None:
        info: dict[str, Any] = {"mode": "live" if self.live else "replay", "sensitivity": self.cfg.risk.sensitivity}
        try:
            du = shutil.disk_usage(self.cfg.resolve(self.cfg.storage.clip_dir) if Path(self.cfg.resolve(self.cfg.storage.clip_dir) or ".").exists() else ".")
            info["disk_free_gb"] = round(du.free / 1024**3, 1)
        except OSError:
            pass
        try:
            info["load1"] = round(os.getloadavg()[0], 2)
        except (OSError, AttributeError):
            pass
        if self.store is not None:
            info["events"] = self.store.stats()
        self.bus.set_system(info)

    def _housekeeping(self) -> None:
        now = self.clock.now()
        self.engine.tick(now)
        if self.recorder is not None:
            self.recorder.tick(now)
        if self.purge is not None:
            self.purge.tick(now)
        for w in self.workers.values():
            if self.live:
                h = w.health.check_offline(now)
                if h.offline:
                    w.engine.set_sensor_fault(w.cam.id, w.health.faults())
        self.publish_speed()

    # ------------------------------------------------------------------ HMI
    def start_hmi(self) -> None:
        if not self.hmi_enabled or self._hmi_thread is not None:
            return
        try:
            import uvicorn

            from smartview.hmi.server import create_app
        except ImportError as exc:
            log.error("HMI 需要 fastapi/uvicorn：pip install 'smartview[hmi]'（%s）", exc)
            return
        app = create_app(self.bus, self.controls)
        config = uvicorn.Config(app, host=self.cfg.hmi.host, port=self.cfg.hmi.port, log_level="warning", access_log=False)
        self._hmi_server = uvicorn.Server(config)
        self._hmi_server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
        self._hmi_thread = threading.Thread(target=self._hmi_server.run, name="hmi", daemon=True)
        self._hmi_thread.start()
        log.info("HMI: http://%s:%d/", self.cfg.hmi.host, self.cfg.hmi.port)

    def stop_hmi(self) -> None:
        if self._hmi_server is not None:
            self._hmi_server.should_exit = True
        if self._hmi_thread is not None:
            self._hmi_thread.join(5.0)
            self._hmi_thread = None

    # ------------------------------------------------------------- run modes
    def run_sync(self, max_frames: int | None = None) -> RunSummary:
        """回放：在调用线程中 lockstep 推进所有相机（确定性）。"""
        assert isinstance(self.clock, ReplayClock)
        t_wall0 = time.perf_counter()
        summary = RunSummary()
        for w in self.workers.values():
            w.source.open()
        active = dict(self.workers)
        n = 0
        last_house = -1.0
        t_first: float | None = None
        try:
            while active and not self.stop_event.is_set():
                for cam_id, w in list(active.items()):
                    fr = w.source.read()
                    if fr is None:
                        active.pop(cam_id)
                        continue
                    if fr.ts > self.clock.now():
                        self.clock.set(fr.ts)
                    if self.realtime:
                        if t_first is None:
                            t_first = time.perf_counter() - fr.ts
                        delay = (t_first + fr.ts) - time.perf_counter()
                        if delay > 0:
                            time.sleep(min(delay, 0.5))
                    w.process(fr)
                    summary.frames[cam_id] = summary.frames.get(cam_id, 0) + 1
                    n += 1
                    if max_frames is not None and n >= max_frames:
                        active = {}
                        break
                now = self.clock.now()
                if now - last_house >= 0.1:
                    last_house = now
                    self._housekeeping()
                    if n % 50 == 0:
                        self._publish_system()
        finally:
            for w in self.workers.values():
                w.source.close()
            if self.recorder is not None:
                # 推进时钟以完成后滚并写出片段
                self.clock.advance(self.cfg.storage.post_roll_s + 0.1)
                self.engine.tick(self.clock.now())
                self.recorder.flush()
            self.dispatcher.refresh()
            if self._det_log is not None and hasattr(self._det_log, "close"):
                self._det_log.close()
        for ts, st in self.timeline:
            if st.level > summary.max_level:
                summary.max_level = st.level
            if st.level > AlarmLevel.L0 and int(st.level) not in summary.first_level_ts:
                summary.first_level_ts[int(st.level)] = ts
        summary.events = (self.store.stats()["total"] - self._events_at_start) if self.store else 0
        summary.duration_s = self.clock.now()
        summary.wall_s = time.perf_counter() - t_wall0
        self._publish_system()
        return summary

    def run_threaded(self, install_signals: bool = True) -> None:
        """真机：每相机一个线程 + 分发线程 + 看门狗线程 + HMI。阻塞直到停止。"""
        if install_signals:
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    signal.signal(sig, lambda *_: self.stop_event.set())
                except ValueError:  # pragma: no cover - 非主线程
                    pass
        if self.speed.nmea is not None:
            self.speed.nmea.start()
        self.dispatcher.start()
        self.start_hmi()
        for cam_id, w in self.workers.items():
            t = threading.Thread(target=w.run_loop, args=(self.stop_event,), name=f"cam-{cam_id}", daemon=True)
            t.start()
            self._threads.append(t)
        hk = threading.Thread(target=self._housekeeping_loop, name="housekeeping", daemon=True)
        hk.start()
        self._threads.append(hk)
        try:
            while not self.stop_event.is_set():
                if all(w.source.finished for w in self.workers.values()):
                    log.info("所有视频源结束")
                    break
                self.stop_event.wait(0.2)
        finally:
            self.shutdown()

    def _housekeeping_loop(self) -> None:
        k = 0
        while not self.stop_event.wait(0.2):
            try:
                self._housekeeping()
                k += 1
                if k % 10 == 0:
                    self._publish_system()
            except Exception:  # noqa: BLE001
                log.exception("看门狗异常")

    def shutdown(self) -> None:
        self.stop_event.set()
        for t in self._threads:
            t.join(5.0)
        self._threads.clear()
        if self.speed.nmea is not None:
            self.speed.nmea.stop()
        self.dispatcher.stop()
        if self.recorder is not None:
            self.recorder.flush()
        if self.purge is not None:
            self.purge.close()
        if self.gpio_driver is not None:
            try:
                self.gpio_driver.cleanup()
            except Exception:  # noqa: BLE001
                pass
        for w in self.workers.values():
            try:
                w.detector.close()
            except Exception:  # noqa: BLE001
                pass
        if self._det_log is not None and hasattr(self._det_log, "close"):
            self._det_log.close()
        self.stop_hmi()
        if self.store is not None:
            self.store.close()
