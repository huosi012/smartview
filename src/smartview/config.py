"""配置模型（pydantic v2）与 YAML 加载。

所有阈值均可在 YAML 中覆盖；未知字段一律报错（``extra="forbid"``），避免拼写错误静默失效。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Point = tuple[float, float]
Polygon = list[Point]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MachineConfig(_Strict):
    n_rows: int = Field(4, ge=1, le=16)
    row_spacing_m: float = Field(0.6, gt=0)
    header_width_m: float = Field(2.4, gt=0)
    path_margin_m: float = Field(0.3, ge=0)


class SpeedConfig(_Strict):
    source: Literal["manual", "nmea"] = "manual"
    manual_mps: float = Field(1.5, ge=0)
    nmea_port: str = "/dev/ttyTHS1"
    baud: int = 9600
    stale_s: float = Field(3.0, gt=0)
    min_speed_mps: float = Field(0.3, gt=0)  # TTC 计算的速度下限，避免停车时 TTC 为无穷


class MountConfig(_Strict):
    """相机外参（相对车体）。

    x_fwd_m: 相机相对割台前缘的前向位置（负 = 在割台后方，例如驾驶室顶）
    y_lat_m: 相机横向位置（左正）
    z_m:     离地高度
    pitch_deg: 俯角（向下为正）
    """

    x_fwd_m: float = 0.0
    y_lat_m: float = 0.0
    z_m: float = Field(1.0, gt=0)
    pitch_deg: float = Field(15.0, ge=0, lt=90)
    yaw_deg: float = 0.0
    roll_deg: float = 0.0
    hfov_deg: float = Field(60.0, gt=10, lt=170)


def _check_polygon(poly: list[Any], name: str) -> Polygon:
    if len(poly) < 3:
        raise ValueError(f"{name} 至少需要 3 个点")
    out: Polygon = []
    for pt in poly:
        if len(pt) != 2:
            raise ValueError(f"{name} 的点必须是 [x, y]")
        x, y = float(pt[0]), float(pt[1])
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ValueError(f"{name} 使用归一化坐标，必须在 [0,1] 内，得到 {pt}")
        out.append((x, y))
    return out


class CameraConfig(_Strict):
    id: str
    role: Literal["forward", "header"]
    source: str = "synthetic:empty"  # 文件路径 / "synthetic:<scenario>" / "gst:<pipeline>" / "v4l2:/dev/video0" / rtsp://
    width: int = Field(640, ge=64)
    height: int = Field(360, ge=64)
    fps: float = Field(15.0, gt=0)
    # 前视相机的中心裁剪（归一化 x0,y0,x1,y1）：避免整帧下采样丢失远处小目标
    detect_crop: tuple[float, float, float, float] | None = None
    # 识别区域（归一化多边形），None = 整幅
    roi_polygon: Polygon | None = None
    # 需剔除的自身区域（割台分禾器、机身等），有效区 = ROI − 排除区
    exclude_polygons: list[Polygon] = Field(default_factory=list)
    exclude_mask_png: str | None = None  # 像素级遮罩（白=排除），由 calib-mask 工具生成
    mount: MountConfig = Field(default_factory=MountConfig)
    homography: list[list[float]] | None = None  # 3x3，像素 → 车体地面 (x_fwd, y_lat)，优先于 mount
    rows_covered: tuple[int, int] | None = None  # 该相机覆盖的行号范围 [lo, hi]
    purge_channel: str | None = None  # 吹扫通道名（对应 alarm.purge.channels 的键）

    @field_validator("detect_crop")
    @classmethod
    def _crop_ok(cls, v):
        if v is None:
            return v
        x0, y0, x1, y1 = v
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError("detect_crop 必须满足 0<=x0<x1<=1, 0<=y0<y1<=1（归一化）")
        return v

    @field_validator("roi_polygon", mode="before")
    @classmethod
    def _roi_ok(cls, v):
        return None if v is None else _check_polygon(v, "roi_polygon")

    @field_validator("exclude_polygons", mode="before")
    @classmethod
    def _excl_ok(cls, v):
        return [_check_polygon(p, "exclude_polygons") for p in (v or [])]

    @field_validator("homography")
    @classmethod
    def _h_ok(cls, v):
        if v is None:
            return v
        if len(v) != 3 or any(len(r) != 3 for r in v):
            raise ValueError("homography 必须是 3x3")
        return [[float(x) for x in r] for r in v]


class DetectorConfig(_Strict):
    backend: Literal["classical", "onnx", "tensorrt"] = "classical"
    model_path: str | None = None
    classes: list[str] | None = None  # None → 使用 model.json 或 training/classes.yaml 的默认类别
    input_size: int = Field(640, ge=64)
    conf_thr: float = Field(0.35, ge=0, le=1)
    iou_thr: float = Field(0.5, ge=0, le=1)
    num_threads: int = Field(2, ge=1)
    # classical 基线参数
    min_object_m: float = Field(0.10, gt=0)
    max_object_m: float = Field(0.70, gt=0)


class TrackerConfig(_Strict):
    min_hits: int = Field(3, ge=1)
    max_age: int = Field(10, ge=1)
    conf_high: float = Field(0.5, ge=0, le=1)
    conf_low: float = Field(0.1, ge=0, le=1)
    iou_high: float = Field(0.3, ge=0, le=1)
    iou_low: float = Field(0.4, ge=0, le=1)
    dist_ema: float = Field(0.5, ge=0, le=1)  # 距离 EMA 系数（新值权重）


class RiskThresholds(_Strict):
    fwd_l1_max_dist_m: float = 20.0
    fwd_l2_dist_m: float = 12.0
    fwd_l2_ttc_s: float = 6.0
    fwd_l3_dist_m: float = 6.0
    fwd_l3_ttc_s: float = 3.0
    person_l3_dist_m: float = 10.0
    header_l2_dist_m: float = 3.0  # 割台相机：邻近路径且 ≤ 此距离 → L2（更远 → L1）
    header_l3_dist_m: float = 3.0  # 割台相机：在路且 ≤ 此距离 → L3（更远 → L2）
    adjacent_margin_m: float = 1.0  # "邻近路径"：路径边界外的额外范围
    fusion_window_s: float = 1.5
    min_weighted_score: float = 0.4


class RiskConfig(_Strict):
    sensitivity: Literal["low", "medium", "high"] = "medium"
    hold_s: dict[str, float] = Field(default_factory=lambda: {"L1": 1.0, "L2": 2.0, "L3": 3.0})
    cooldown_s: float = Field(5.0, ge=0)
    mute_max_s: float = Field(60.0, gt=0)
    class_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "stone": 1.0,
            "well_pipe": 1.2,
            "stake": 1.0,
            "concrete_pile": 1.0,
            "person": 1.5,
            "animal": 0.8,
            "pipe_like": 1.0,
            "unknown_obstacle": 0.6,
        }
    )
    thresholds: RiskThresholds = Field(default_factory=RiskThresholds)

    @field_validator("hold_s")
    @classmethod
    def _hold_ok(cls, v):
        for k in ("L1", "L2", "L3"):
            if k not in v:
                raise ValueError(f"hold_s 缺少 {k}")
            if v[k] < 0:
                raise ValueError("hold_s 必须 >= 0")
        return v


class GpioConfig(_Strict):
    buzzer_pin: int = 12
    lamp_pin: int = 16  # 红灯：L2/L3
    lamp_yellow_pin: int | None = None  # 可选黄灯：L1
    active_high: bool = False  # 常见继电器模块低电平有效
    mode: Literal["BOARD", "BCM"] = "BOARD"


class SoundConfig(_Strict):
    player: str = "aplay"
    wav_dir: str = "assets/sounds"
    repeat_interval_s: float = Field(2.0, gt=0)


class PurgeConfig(_Strict):
    """镜头吹扫（风刀 / 电磁阀）。"""

    enabled: bool = False
    channels: dict[str, int] = Field(default_factory=dict)  # 通道名 → GPIO 引脚
    burst_s: float = Field(1.5, gt=0)
    period_s: float = Field(60.0, ge=0)  # 定时吹扫周期（秒）；0 表示关闭定时吹扫
    on_dirty: bool = True  # 镜头脏污检测触发
    min_interval_s: float = Field(10.0, ge=0)
    max_duty: float = Field(0.10, gt=0, le=1)  # 最大占空比（保护电磁阀与气源）
    suppress_extra_s: float = Field(0.5, ge=0)  # 吹扫结束后继续抑制检测的时间

    @model_validator(mode="after")
    def _channels_ok(self):
        if self.enabled and not self.channels:
            raise ValueError("purge.enabled=true 时必须配置 channels")
        return self


class HikvisionExtraRequest(_Strict):
    """可配置的 ISAPI 扩展请求（声光报警 / 白光灯等，端点因机型而异，须按相机 ISAPI 文档核对）。"""

    method: Literal["PUT", "POST", "GET"] = "PUT"
    path: str = "/ISAPI/System/IO/outputs/1/trigger"
    body: str | None = None
    content_type: str = "application/xml"


class HikvisionConfig(_Strict):
    """海康威视相机 ISAPI 报警回传（sinks 中加入 "hikvision" 启用）。"""

    host: str = "192.168.1.64"
    port: int = Field(80, ge=1, le=65535)
    https: bool = False
    user: str = "admin"
    password: str = ""
    password_env: str | None = None  # 优先从环境变量读取密码
    output_port: int = Field(1, ge=1)  # 报警输出继电器编号
    pulse_s: float = Field(2.0, gt=0)  # 每次触发保持时间
    min_interval_s: float = Field(5.0, ge=0)  # 重复触发最小间隔
    min_level: int = Field(2, ge=1, le=3)  # 达到该等级才触发
    audio_alarm: HikvisionExtraRequest | None = None  # 声光警戒机型：自定义触发请求
    audio_wav: str | None = None  # 经双向音频通道播放的 WAV（内置喇叭机型）
    timeout_s: float = Field(3.0, gt=0)


class AlarmConfig(_Strict):
    sinks: list[Literal["console", "sound", "gpio", "hmi", "hikvision"]] = Field(default_factory=lambda: ["console", "hmi"])
    gpio: GpioConfig = Field(default_factory=GpioConfig)
    sound: SoundConfig = Field(default_factory=SoundConfig)
    purge: PurgeConfig = Field(default_factory=PurgeConfig)
    hikvision: HikvisionConfig = Field(default_factory=HikvisionConfig)
    refresh_s: float = Field(1.0, gt=0)  # 状态无变化时也按此周期刷新 sinks


class StorageConfig(_Strict):
    db_path: str = "data/events.db"
    clip_dir: str = "data/clips"
    pre_roll_s: float = Field(5.0, ge=0)
    post_roll_s: float = Field(3.0, ge=0)
    max_disk_gb: float = Field(20.0, gt=0)
    ring_fps: float = Field(10.0, gt=0)
    ring_max_width: int = Field(960, ge=160)
    jpeg_quality: int = Field(70, ge=10, le=100)
    enabled: bool = True


class HmiConfig(_Strict):
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = Field(8080, ge=1, le=65535)
    mjpeg_fps: float = Field(8.0, gt=0)
    jpeg_quality: int = Field(70, ge=10, le=100)


class CloudConfig(_Strict):
    """边缘 → 云端上传代理（抽帧 / 事件片段 / 命令轮询 / 模型同步）。"""

    enabled: bool = False
    url: str = "http://127.0.0.1:8090"
    api_key: str = ""
    api_key_env: str | None = None
    device_id: str = "harvester-01"
    frame_fps: float = Field(1.0, ge=0, le=30)  # 训练素材抽帧频率；0 = 不传帧
    frame_max_width: int = Field(1280, ge=160)
    jpeg_quality: int = Field(85, ge=10, le=100)
    upload_events: bool = True  # 事件快照 + 片段
    spool_dir: str = "data/cloud_spool"  # 断网时的磁盘排队目录
    max_spool_mb: float = Field(2048, gt=0)
    poll_commands_s: float = Field(5.0, ge=0)  # 云端命令轮询周期；0 = 关闭
    model_sync: bool = False  # 自动下载云端最新模型（OTA）
    model_dir: str = "models"
    model_sync_interval_s: float = Field(600, gt=0)
    timeout_s: float = Field(10.0, gt=0)


class SmartViewConfig(_Strict):
    machine: MachineConfig = Field(default_factory=MachineConfig)
    speed: SpeedConfig = Field(default_factory=SpeedConfig)
    cameras: list[CameraConfig] = Field(default_factory=list)
    detector: DetectorConfig = Field(default_factory=DetectorConfig)
    tracker: TrackerConfig = Field(default_factory=TrackerConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    alarm: AlarmConfig = Field(default_factory=AlarmConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    hmi: HmiConfig = Field(default_factory=HmiConfig)
    cloud: CloudConfig = Field(default_factory=CloudConfig)
    base_dir: str | None = Field(None, exclude=True)  # 相对路径的解析基准（配置文件所在目录）

    @model_validator(mode="after")
    def _cameras_ok(self):
        ids = [c.id for c in self.cameras]
        if len(ids) != len(set(ids)):
            raise ValueError(f"相机 id 重复: {ids}")
        if self.cameras and not any(c.role == "forward" or c.role == "header" for c in self.cameras):
            raise ValueError("至少需要一个相机")
        purge_channels = set(self.alarm.purge.channels)
        for c in self.cameras:
            if c.purge_channel and self.alarm.purge.enabled and c.purge_channel not in purge_channels:
                raise ValueError(f"相机 {c.id} 的 purge_channel={c.purge_channel} 未在 alarm.purge.channels 中定义")
        return self

    # ---------------------------------------------------------------- loading
    @classmethod
    def from_dict(cls, data: dict[str, Any], base_dir: str | Path | None = None) -> SmartViewConfig:
        cfg = cls.model_validate(data or {})
        cfg.base_dir = str(base_dir) if base_dir is not None else None
        return cfg

    @classmethod
    def load(cls, path: str | Path) -> SmartViewConfig:
        p = Path(path)
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls.from_dict(data, base_dir=p.parent)

    def resolve(self, rel: str | None) -> str | None:
        """把配置中的相对路径解析为相对配置文件目录的绝对路径。"""
        if rel is None:
            return None
        p = Path(rel)
        if p.is_absolute() or self.base_dir is None:
            return str(p)
        return str((Path(self.base_dir) / p).resolve())

    def camera(self, cam_id: str) -> CameraConfig:
        for c in self.cameras:
            if c.id == cam_id:
                return c
        raise KeyError(cam_id)

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.model_dump(mode="json", exclude_none=False), allow_unicode=True, sort_keys=False)
