"""核心数据类型。所有模块之间只通过这些类型交换数据。"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any

import numpy as np


class AlarmLevel(IntEnum):
    """四级状态。等级只升不降的滞回逻辑在 :mod:`smartview.risk.engine` 中实现。"""

    L0 = 0  # 正常
    L1 = 1  # 注意
    L2 = 2  # 警告
    L3 = 3  # 危险 / 立即停车


LEVEL_ZH: dict[AlarmLevel, str] = {
    AlarmLevel.L0: "正常",
    AlarmLevel.L1: "注意",
    AlarmLevel.L2: "警告",
    AlarmLevel.L3: "危险",
}

LEVEL_COLOR: dict[AlarmLevel, str] = {
    AlarmLevel.L0: "#6b7280",
    AlarmLevel.L1: "#eab308",
    AlarmLevel.L2: "#f97316",
    AlarmLevel.L3: "#dc2626",
}


class CameraRole(str, Enum):
    FORWARD = "forward"  # 驾驶室顶前视
    HEADER = "header"  # 割台分禾器低位近场


# 类别中文名；类别 id 由 detector 的 classes 列表决定，类名是跨模块的稳定键
CLASS_ZH: dict[str, str] = {
    "stone": "石块",
    "well_pipe": "井口钢管",
    "stake": "桩体",
    "concrete_pile": "水泥桩",
    "person": "行人",
    "animal": "动物",
    "pipe_like": "疑似钢管",
    "unknown_obstacle": "疑似异物",
}


@dataclass(slots=True)
class Frame:
    cam_id: str
    seq: int
    ts: float  # 单调时间（秒）
    image: np.ndarray  # BGR, HxWx3, uint8
    wall_ts: float = 0.0  # 墙上时间，仅用于事件记录


@dataclass(slots=True)
class Detection:
    bbox: np.ndarray  # xyxy, 像素坐标（原图坐标系）, float32 (4,)
    score: float
    cls_id: int
    cls_name: str

    def as_list(self) -> list[float]:
        return [float(v) for v in self.bbox]


@dataclass(slots=True)
class GroundPoint:
    """目标脚点在车体坐标系中的位置。

    x_fwd: 距割台前缘的前向距离（m，正=前方）
    y_lat: 横向偏移（m，左正右负），以车辆中心线为 0
    row:   所在行号（以中心线为 0，向左为正），None 表示无法判定
    in_path: 是否位于割台作业路径（含安全裕量）内
    foot_uv: 用于反投影的像素脚点
    """

    x_fwd: float
    y_lat: float
    row: int | None
    in_path: bool
    foot_uv: tuple[float, float]


@dataclass
class Track:
    track_id: int
    cam_id: str
    cls_id: int
    cls_name: str
    bbox: np.ndarray
    score: float
    hits: int = 0
    age: int = 0
    misses: int = 0
    history: deque = field(default_factory=lambda: deque(maxlen=30))  # (ts, bbox)
    ground: GroundPoint | None = None
    dist_m: float | None = None  # EMA 平滑后的前向距离
    range_rate: float | None = None  # 距离变化率（m/s，负=接近）
    ttc_s: float | None = None
    confirmed: bool = False
    last_ts: float = 0.0

    @property
    def foot_uv(self) -> tuple[float, float]:
        x1, _y1, x2, y2 = (float(v) for v in self.bbox)
        return ((x1 + x2) / 2.0, y2)


@dataclass(slots=True)
class RiskAssessment:
    cam_id: str
    track_id: int
    level: AlarmLevel
    score: float
    dist_m: float | None
    ttc_s: float | None
    reasons: list[str]
    cls_name: str = ""
    row: int | None = None
    in_path: bool = False

    def message_zh(self) -> str:
        name = CLASS_ZH.get(self.cls_name, self.cls_name or "异物")
        where = f"前方 {self.dist_m:.1f} m " if self.dist_m is not None else "前方 "
        if self.level >= AlarmLevel.L3:
            return f"{where}{name}，请立即停车"
        if self.level == AlarmLevel.L2:
            return f"{where}{name}，请减速准备停车"
        if self.level == AlarmLevel.L1:
            return f"{where}发现{name}，请注意"
        return ""


@dataclass
class AlarmState:
    level: AlarmLevel = AlarmLevel.L0
    since_ts: float = 0.0
    ts: float = 0.0
    top: RiskAssessment | None = None
    per_cam: dict[str, AlarmLevel] = field(default_factory=dict)
    buzzer_on: bool = False
    lamp_on: bool = False
    acked: bool = False
    muted_until: float = 0.0
    sensor_fault: bool = False
    fault_reasons: list[str] = field(default_factory=list)
    event_id: int | None = None
    purging: dict[str, bool] = field(default_factory=dict)

    @property
    def level_zh(self) -> str:
        return LEVEL_ZH[self.level]

    def message_zh(self) -> str:
        if self.top is not None and self.top.level > AlarmLevel.L0:
            return self.top.message_zh()
        if self.sensor_fault:
            return "传感器故障：" + "；".join(self.fault_reasons)
        return "系统正常"

    def to_dict(self) -> dict[str, Any]:
        top = None
        if self.top is not None:
            top = {
                "cam_id": self.top.cam_id,
                "track_id": self.top.track_id,
                "level": int(self.top.level),
                "cls_name": self.top.cls_name,
                "cls_zh": CLASS_ZH.get(self.top.cls_name, self.top.cls_name),
                "dist_m": self.top.dist_m,
                "ttc_s": self.top.ttc_s,
                "row": self.top.row,
                "in_path": self.top.in_path,
                "reasons": list(self.top.reasons),
            }
        return {
            "level": int(self.level),
            "level_zh": self.level_zh,
            "color": LEVEL_COLOR[self.level],
            "message": self.message_zh(),
            "since_ts": self.since_ts,
            "ts": self.ts,
            "top": top,
            "per_cam": {k: int(v) for k, v in self.per_cam.items()},
            "buzzer_on": self.buzzer_on,
            "lamp_on": self.lamp_on,
            "acked": self.acked,
            "muted_until": self.muted_until,
            "sensor_fault": self.sensor_fault,
            "fault_reasons": list(self.fault_reasons),
            "event_id": self.event_id,
            "purging": dict(self.purging),
        }


@dataclass
class Event:
    event_id: int | None
    ts_start: float  # 墙上时间
    ts_end: float | None
    level_max: AlarmLevel
    cam_id: str
    cls_name: str
    track_id: int
    dist_min: float | None = None
    ttc_min: float | None = None
    speed_mps: float | None = None
    acked: bool = False
    ack_ts: float | None = None
    clip_path: str | None = None
    snapshot_path: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "ts_start": self.ts_start,
            "ts_end": self.ts_end,
            "level_max": int(self.level_max),
            "level_zh": LEVEL_ZH[self.level_max],
            "cam_id": self.cam_id,
            "cls_name": self.cls_name,
            "cls_zh": CLASS_ZH.get(self.cls_name, self.cls_name),
            "track_id": self.track_id,
            "dist_min": self.dist_min,
            "ttc_min": self.ttc_min,
            "speed_mps": self.speed_mps,
            "acked": self.acked,
            "ack_ts": self.ack_ts,
            "clip_path": self.clip_path,
            "snapshot_path": self.snapshot_path,
            "extra": dict(self.extra),
        }


@dataclass(slots=True)
class CamHealth:
    cam_id: str
    fps: float = 0.0
    latency_ms: float = 0.0
    frozen: bool = False
    black: bool = False
    lens_dirty: bool = False
    offline: bool = False
    sharpness_ratio: float = 1.0
    static_ratio: float = 0.0
    last_frame_age_s: float = 0.0

    @property
    def ok(self) -> bool:
        return not (self.frozen or self.black or self.lens_dirty or self.offline)

    @property
    def status_zh(self) -> str:
        if self.offline:
            return "离线"
        if self.frozen:
            return "画面冻结"
        if self.black:
            return "黑屏"
        if self.lens_dirty:
            return "镜头脏污"
        return "正常"

    def to_dict(self) -> dict[str, Any]:
        return {
            "cam_id": self.cam_id,
            "fps": round(self.fps, 1),
            "latency_ms": round(self.latency_ms, 1),
            "frozen": self.frozen,
            "black": self.black,
            "lens_dirty": self.lens_dirty,
            "offline": self.offline,
            "sharpness_ratio": round(self.sharpness_ratio, 3),
            "static_ratio": round(self.static_ratio, 3),
            "last_frame_age_s": round(self.last_frame_age_s, 2),
            "ok": self.ok,
            "status_zh": self.status_zh,
        }
