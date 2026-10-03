"""帧源实现：OpenCV（文件 / V4L2 / GStreamer / RTSP）与合成场景。"""

from __future__ import annotations

import logging
import time

import cv2
import numpy as np

from smartview.capture.base import FrameSource
from smartview.clock import Clock, MonotonicClock
from smartview.config import CameraConfig, SpeedConfig
from smartview.geometry.camera import PinholeCamera
from smartview.synth.scene import SyntheticScene, make_scene
from smartview.types import Frame

log = logging.getLogger(__name__)


class OpenCVSource(FrameSource):
    """``uri`` 形式：

    * 文件路径（回放，ts = 媒体时间）
    * ``v4l2:/dev/video0``
    * ``gst:<pipeline 字符串>``（Jetson GMSL2 推荐，见 configs/jetson_*.yaml）
    * ``rtsp://...``
    直播源每次 ``read()`` 取最新帧（丢弃积压）。
    """

    def __init__(self, cam_id: str, uri: str, fps: float = 15.0, loop: bool = False, clock: Clock | None = None) -> None:
        self.cam_id = cam_id
        self.uri = uri
        self.fps = fps
        self.loop = loop
        self.clock = clock or MonotonicClock()
        self.cap: cv2.VideoCapture | None = None
        self.seq = 0
        self._finished = False
        self.is_live = uri.startswith(("v4l2:", "gst:", "rtsp://", "rtmp://", "http://", "https://"))

    def open(self) -> None:
        if self.uri.startswith("gst:"):
            self.cap = cv2.VideoCapture(self.uri[4:], cv2.CAP_GSTREAMER)
        elif self.uri.startswith("v4l2:"):
            self.cap = cv2.VideoCapture(self.uri[5:], cv2.CAP_V4L2)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        else:
            self.cap = cv2.VideoCapture(self.uri)
        if not self.cap.isOpened():
            raise RuntimeError(f"无法打开视频源 {self.uri!r}")
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        src_fps = self.cap.get(cv2.CAP_PROP_FPS) or 0.0
        if not self.is_live and src_fps > 0:
            self.fps = float(src_fps)

    def read(self) -> Frame | None:
        assert self.cap is not None, "open() 未调用"
        if self._finished:
            return None
        if self.is_live:
            # 丢弃积压帧，只取最新
            for _ in range(2):
                self.cap.grab()
        ok, img = self.cap.read()
        if not ok or img is None:
            if self.is_live:
                return None
            if self.loop and self.seq > 0:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, img = self.cap.read()
                if not ok:
                    self._finished = True
                    return None
            else:
                self._finished = True
                return None
        ts = self.clock.now() if self.is_live else self.seq / self.fps
        fr = Frame(cam_id=self.cam_id, seq=self.seq, ts=ts, image=img, wall_ts=time.time())
        self.seq += 1
        return fr

    @property
    def finished(self) -> bool:
        return self._finished

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None


class SyntheticSource(FrameSource):
    """合成场景帧源（回放语义：ts = i/fps）。"""

    def __init__(
        self,
        cam_id: str,
        scene: SyntheticScene,
    ) -> None:
        self.cam_id = cam_id
        self.scene = scene
        self.fps = scene.cfg.fps
        self.width, self.height = scene.cfg.width, scene.cfg.height
        self.seq = 0
        self.is_live = False

    @classmethod
    def from_config(
        cls,
        cam: CameraConfig,
        speed_mps: float | None = None,
        seed: int | None = None,
        duration_s: float | None = None,
    ) -> SyntheticSource:
        scenario = cam.source.split(":", 1)[1] if ":" in cam.source else "empty"
        camera = PinholeCamera.from_mount(cam.width, cam.height, cam.mount)
        scene = make_scene(
            scenario,
            camera,
            fps=cam.fps,
            speed_mps=speed_mps,
            duration_s=duration_s,
            seed=seed,
            header_overlay=None if cam.role == "header" else False,
        )
        return cls(cam.id, scene)

    def open(self) -> None:
        self.seq = 0

    def read(self) -> Frame | None:
        if self.seq >= self.scene.n_frames:
            return None
        img = self.scene.render(self.seq)
        fr = Frame(cam_id=self.cam_id, seq=self.seq, ts=self.scene.ts_at(self.seq), image=img, wall_ts=time.time())
        self.seq += 1
        return fr

    @property
    def finished(self) -> bool:
        return self.seq >= self.scene.n_frames

    def close(self) -> None:
        return None


class ListSource(FrameSource):
    """由内存中的图像列表构成的帧源（测试用）。"""

    def __init__(self, cam_id: str, images: list[np.ndarray], fps: float = 15.0) -> None:
        self.cam_id, self.images, self.fps = cam_id, images, fps
        self.seq = 0
        if images:
            self.height, self.width = images[0].shape[:2]

    def open(self) -> None:
        self.seq = 0

    def read(self) -> Frame | None:
        if self.seq >= len(self.images):
            return None
        fr = Frame(self.cam_id, self.seq, self.seq / self.fps, self.images[self.seq], time.time())
        self.seq += 1
        return fr

    @property
    def finished(self) -> bool:
        return self.seq >= len(self.images)

    def close(self) -> None:
        return None


def build_source(
    cam: CameraConfig,
    speed: SpeedConfig | None = None,
    clock: Clock | None = None,
    loop: bool = False,
    seed: int | None = None,
    duration_s: float | None = None,
) -> FrameSource:
    if cam.source.startswith("synthetic:"):
        speed_mps = speed.manual_mps if (speed is not None and speed.source == "manual") else None
        return SyntheticSource.from_config(cam, speed_mps=speed_mps, seed=seed, duration_s=duration_s)
    return OpenCVSource(cam.id, cam.source, fps=cam.fps, loop=loop, clock=clock)
