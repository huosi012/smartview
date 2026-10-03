"""针孔相机模型、地面单应性与车体坐标定位。

坐标系约定
----------
* 车体系（地面系）：原点在割台前缘中心的地面投影，x 向前，y 向左，z 向上（右手系）。
* 相机光学系（OpenCV 约定）：X 向右，Y 向下，Z 沿光轴向前。
* 像素系：u 向右，v 向下，原点在左上角。

相机姿态由 :class:`smartview.config.MountConfig` 给出：位置 (x_fwd, y_lat, z)，俯角 pitch（向下为正）、
偏航 yaw（向左为正）、横滚 roll。旋转矩阵 ``R``（车体 → 相机）::

    R = Rz_c(roll) · Rx_c(pitch) · R0 · Rz_v(-yaw)
    R0 = [[0, -1, 0], [0, 0, -1], [1, 0, 0]]   # 车体 x→Z_c, -y→X_c, -z→Y_c

合成场景生成器与生产定位代码共用本模块，保证"渲染 ↔ 反投影"几何一致。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from smartview.config import CameraConfig, MachineConfig, MountConfig
from smartview.types import GroundPoint, Track

_R0 = np.array([[0.0, -1.0, 0.0], [0.0, 0.0, -1.0], [1.0, 0.0, 0.0]])


def _rx(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def _rz(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


@dataclass
class PinholeCamera:
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    position: np.ndarray  # (3,) 车体系中的相机位置
    R: np.ndarray  # (3,3) 车体 → 相机

    # ------------------------------------------------------------ constructors
    @classmethod
    def from_fov(
        cls,
        width: int,
        height: int,
        hfov_deg: float,
        x_fwd_m: float = 0.0,
        y_lat_m: float = 0.0,
        z_m: float = 1.0,
        pitch_deg: float = 0.0,
        yaw_deg: float = 0.0,
        roll_deg: float = 0.0,
    ) -> PinholeCamera:
        fx = (width / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)
        fy = fx  # 方形像素
        R = _rz(math.radians(roll_deg)) @ _rx(math.radians(pitch_deg)) @ _R0 @ _rz(-math.radians(yaw_deg))
        return cls(
            width=int(width),
            height=int(height),
            fx=fx,
            fy=fy,
            cx=width / 2.0,
            cy=height / 2.0,
            position=np.array([x_fwd_m, y_lat_m, z_m], dtype=float),
            R=R,
        )

    @classmethod
    def from_mount(cls, width: int, height: int, mount: MountConfig) -> PinholeCamera:
        return cls.from_fov(
            width,
            height,
            mount.hfov_deg,
            x_fwd_m=mount.x_fwd_m,
            y_lat_m=mount.y_lat_m,
            z_m=mount.z_m,
            pitch_deg=mount.pitch_deg,
            yaw_deg=mount.yaw_deg,
            roll_deg=mount.roll_deg,
        )

    def resized(self, width: int, height: int) -> PinholeCamera:
        """同一相机在另一分辨率下的模型（内参按比例缩放）。"""
        sx, sy = width / self.width, height / self.height
        return PinholeCamera(
            width=int(width),
            height=int(height),
            fx=self.fx * sx,
            fy=self.fy * sy,
            cx=self.cx * sx,
            cy=self.cy * sy,
            position=self.position.copy(),
            R=self.R.copy(),
        )

    # -------------------------------------------------------------- intrinsics
    @property
    def K(self) -> np.ndarray:
        return np.array([[self.fx, 0.0, self.cx], [0.0, self.fy, self.cy], [0.0, 0.0, 1.0]])

    @property
    def hfov_deg(self) -> float:
        return math.degrees(2.0 * math.atan((self.width / 2.0) / self.fx))

    @property
    def vfov_deg(self) -> float:
        return math.degrees(2.0 * math.atan((self.height / 2.0) / self.fy))

    # -------------------------------------------------------------- projection
    def project(self, pts_v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """车体系 3D 点 (N,3) → 像素 (N,2) 与深度 (N,)。深度 <= 0 的点在相机后方。"""
        pts_v = np.asarray(pts_v, dtype=float).reshape(-1, 3)
        pc = (self.R @ (pts_v - self.position).T).T  # (N,3)
        z = pc[:, 2]
        with np.errstate(divide="ignore", invalid="ignore"):
            u = self.fx * pc[:, 0] / z + self.cx
            v = self.fy * pc[:, 1] / z + self.cy
        return np.stack([u, v], axis=1), z

    def ground_to_image(self, x: float, y: float) -> tuple[float, float] | None:
        uv, z = self.project(np.array([[x, y, 0.0]]))
        if z[0] <= 1e-9:
            return None
        return float(uv[0, 0]), float(uv[0, 1])

    def ray(self, u: float, v: float) -> np.ndarray:
        """像素 → 车体系中的单位视线方向。"""
        d_c = np.array([(u - self.cx) / self.fx, (v - self.cy) / self.fy, 1.0])
        d_v = self.R.T @ d_c
        return d_v / np.linalg.norm(d_v)

    def image_to_ground(self, u: float, v: float) -> tuple[float, float] | None:
        """像素 → 地面点 (x_fwd, y_lat)；地平线以上或射线不与地面相交返回 None。"""
        d = self.ray(u, v)
        if d[2] >= -1e-9:
            return None
        t = -self.position[2] / d[2]
        p = self.position + t * d
        return float(p[0]), float(p[1])

    def ground_homography(self) -> np.ndarray:
        """3x3 单应性：像素齐次坐标 → 地面 (x, y, 1)。与 :meth:`image_to_ground` 等价（标定路径使用）。"""
        M = self.R @ np.array(
            [[1.0, 0.0, -self.position[0]], [0.0, 1.0, -self.position[1]], [0.0, 0.0, -self.position[2]]]
        )
        H_g2i = self.K @ M
        H_i2g = np.linalg.inv(H_g2i)
        # 归一化：使像底中心的 w 为正，便于用 w 的符号判断地平线以上
        w = (H_i2g @ np.array([self.cx, self.height - 1.0, 1.0]))[2]
        if w < 0:
            H_i2g = -H_i2g
        return H_i2g / abs(H_i2g[2, 2]) if abs(H_i2g[2, 2]) > 1e-12 else H_i2g

    def horizon_v(self, u: float | None = None) -> float:
        """地平线所在的像素行（前向无限远处）。"""
        far = self.position + np.array([1e6, 0.0, 0.0])
        if u is not None:
            d = self.ray(u, self.cy)
            far = self.position + 1e6 * np.array([d[0], d[1], 0.0]) / max(np.hypot(d[0], d[1]), 1e-9)
        uv, _ = self.project(far.reshape(1, 3))
        return float(uv[0, 1])

    def object_height_px(self, x_fwd: float, y_lat: float, h_m: float) -> float | None:
        """地面点 (x_fwd, y_lat) 处高 h_m 的竖直物体在图像中的像素高度。"""
        uv, z = self.project(np.array([[x_fwd, y_lat, 0.0], [x_fwd, y_lat, h_m]]))
        if np.any(z <= 1e-9):
            return None
        return float(abs(uv[0, 1] - uv[1, 1]))

    def ground_visible_range(self) -> tuple[float, float | None]:
        """中心列可见地面的最近距离与最远距离（None = 直到地平线）。"""
        near = self.image_to_ground(self.cx, self.height - 1.0)
        far = self.image_to_ground(self.cx, 0.0)
        near_x = near[0] if near else float("nan")
        return near_x, (far[0] if far else None)


# --------------------------------------------------------------------------- helpers
def time_to_contact(dist_m: float | None, speed_mps: float, min_speed_mps: float = 0.3) -> float | None:
    if dist_m is None:
        return None
    return max(dist_m, 0.0) / max(speed_mps, min_speed_mps)


def estimate_range_rate(samples: list[tuple[float, float]], window_s: float = 0.5) -> float | None:
    """由 (ts, dist) 序列最小二乘估计距离变化率（m/s，负=接近）。样本不足返回 None。"""
    if len(samples) < 3:
        return None
    t_end = samples[-1][0]
    pts = [(t, d) for t, d in samples if t_end - t <= window_s and d is not None]
    if len(pts) < 3:
        return None
    t = np.array([p[0] for p in pts])
    d = np.array([p[1] for p in pts])
    if np.ptp(t) < 1e-6:
        return None
    t = t - t.mean()
    slope = float((t * (d - d.mean())).sum() / (t * t).sum())
    return slope


class GroundProjector:
    """把图像中的目标脚点定位到车体地面坐标，并给出行号 / 是否在作业路径内。

    * 若相机配置了标定单应性 ``homography``（像素 → 地面），优先使用；
    * 否则由 ``mount`` 外参构造 :class:`PinholeCamera`。
    * 尺度门限（classical 检测器）始终使用由 mount 推导的针孔模型。
    """

    def __init__(
        self,
        cam: CameraConfig,
        machine: MachineConfig,
        image_size: tuple[int, int] | None = None,
    ) -> None:
        self.cam_cfg = cam
        self.machine = machine
        w, h = image_size if image_size else (cam.width, cam.height)
        self.width, self.height = int(w), int(h)
        self.camera = PinholeCamera.from_mount(cam.width, cam.height, cam.mount)
        if (self.width, self.height) != (cam.width, cam.height):
            self.camera = self.camera.resized(self.width, self.height)
        self._H: np.ndarray | None = None
        self._H_inv: np.ndarray | None = None
        if cam.homography is not None:
            H = np.array(cam.homography, dtype=float)
            # 单应性按配置分辨率标定；当前分辨率不同则缩放像素坐标
            S = np.diag([cam.width / self.width, cam.height / self.height, 1.0])
            H = H @ S
            w_sign = (H @ np.array([self.width / 2.0, self.height - 1.0, 1.0]))[2]
            if w_sign < 0:
                H = -H
            self._H = H
            self._H_inv = np.linalg.inv(H)

    # -------------------------------------------------------------- transforms
    def for_size(self, width: int, height: int) -> GroundProjector:
        if (width, height) == (self.width, self.height):
            return self
        return GroundProjector(self.cam_cfg, self.machine, image_size=(width, height))

    def image_to_ground(self, u: float, v: float) -> tuple[float, float] | None:
        if self._H is None:
            return self.camera.image_to_ground(u, v)
        x, y, w = self._H @ np.array([u, v, 1.0])
        if w <= 1e-9:
            return None
        x, y = x / w, y / w
        if not (math.isfinite(x) and math.isfinite(y)):
            return None
        return float(x), float(y)

    def ground_to_image(self, x: float, y: float) -> tuple[float, float] | None:
        if self._H_inv is None:
            return self.camera.ground_to_image(x, y)
        u, v, w = self._H_inv @ np.array([x, y, 1.0])
        if abs(w) <= 1e-12:
            return None
        return float(u / w), float(v / w)

    # ------------------------------------------------------------ vehicle logic
    def row_of(self, y_lat: float) -> int:
        """行号：从左到右 0..n_rows-1（可越界为负或 >= n_rows，表示机外）。"""
        n = self.machine.n_rows
        return int(round((n - 1) / 2.0 - y_lat / self.machine.row_spacing_m))

    def half_path(self) -> float:
        return self.machine.header_width_m / 2.0 + self.machine.path_margin_m

    def in_path(self, y_lat: float) -> bool:
        return abs(y_lat) <= self.half_path()

    def is_adjacent(self, y_lat: float, margin_m: float = 1.0) -> bool:
        return abs(y_lat) <= self.half_path() + margin_m

    def locate(self, u: float, v: float) -> GroundPoint | None:
        g = self.image_to_ground(u, v)
        if g is None:
            return None
        x, y = g
        return GroundPoint(x_fwd=x, y_lat=y, row=self.row_of(y), in_path=self.in_path(y), foot_uv=(float(u), float(v)))

    def annotate(self, track: Track) -> GroundPoint | None:
        u, v = track.foot_uv
        gp = self.locate(u, v)
        track.ground = gp
        return gp

    def expected_height_px(self, v: float, h_m: float, u: float | None = None) -> float | None:
        """图像行 v（脚点）处、高 h_m 物体的期望像素高度（用于尺度门限）。"""
        uu = self.camera.cx if u is None else u
        g = self.camera.image_to_ground(uu, v)
        if g is None:
            return None
        return self.camera.object_height_px(g[0], g[1], h_m)
