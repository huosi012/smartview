"""合成玉米垄场景生成器。

用途：在没有真实田间数据时，离线、确定性地驱动整条链路（检测 → 跟踪 → 测距 → 报警），
并提供逐帧真值（物体地面坐标 / 像素框）供测试断言。渲染复用生产代码中的
:class:`smartview.geometry.PinholeCamera`，保证"渲染 ↔ 反投影"几何一致。

**这是一个简化模型**（秸秆为竖直四边形、叶片稀疏且仅在 0.5 m 以上），只用于验证软件逻辑，
不能替代真实数据训练与测试。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from smartview.geometry.camera import PinholeCamera

# ------------------------------------------------------------------ 颜色（BGR）
C_SKY_TOP = np.array([225, 205, 180], dtype=np.float32)
C_SKY_HOR = np.array([200, 195, 185], dtype=np.float32)
C_SOIL = np.array([60, 85, 115], dtype=np.float32)
C_RIDGE = np.array([78, 108, 142], dtype=np.float32)
C_FOG = np.array([170, 185, 200], dtype=np.float32)
C_STALK = np.array([70, 150, 190], dtype=np.float32)
C_LEAF = np.array([85, 175, 205], dtype=np.float32)
C_CANOPY = np.array([95, 165, 195], dtype=np.float32)
C_STONE = np.array([118, 122, 128], dtype=np.float32)
C_PIPE = np.array([62, 66, 74], dtype=np.float32)
C_PIPE_RUST = np.array([48, 70, 105], dtype=np.float32)
C_PIPE_TOP = np.array([18, 18, 22], dtype=np.float32)
C_PAD = np.array([150, 155, 160], dtype=np.float32)
C_STAKE = np.array([92, 100, 110], dtype=np.float32)
C_HEADER = np.array([112, 116, 122], dtype=np.float32)
C_HEADER_DARK = np.array([70, 72, 78], dtype=np.float32)

PIPE_RADIUS_8IN = 0.219 / 2.0  # 8 寸井管外径 219 mm


@dataclass
class SynthObject:
    kind: str  # "pipe" | "stone" | "stake"
    x0_fwd: float  # 第 0 帧时距割台前缘的前向距离 (m)
    y_lat: float  # 横向位置 (m, 左正)
    size_m: float = 0.3  # 直径 / 宽度
    height_m: float = 0.2
    pad: bool = False  # 钢管周围是否有混凝土井台


@dataclass
class GTObject:
    kind: str
    x_fwd: float
    y_lat: float
    bbox: tuple[float, float, float, float] | None
    visible: bool


@dataclass
class SynthConfig:
    width: int = 640
    height: int = 360
    fps: float = 15.0
    duration_s: float = 8.0
    speed_mps: float = 2.0
    camera: PinholeCamera | None = None
    row_spacing_m: float = 0.6
    n_rows_scene: int = 16  # 场景中渲染的行数（以中心线对称）
    plant_spacing_m: float = 0.25
    stalk_height_m: float = 2.2
    far_stalk_m: float = 20.0  # 超过此距离用冠层色带代替单株
    leaf_max_dist_m: float = 12.0
    objects: list[SynthObject] = field(default_factory=list)
    dust: float = 0.4  # 0..1 粉尘/雾化强度
    jitter_px: float = 2.0
    flicker: float = 0.04
    seed: int = 0
    header_overlay: bool = False  # 画面底部渲染割台/分禾器轮廓（割台相机）
    header_polygon: list[tuple[float, float]] | None = None  # 归一化坐标

    @property
    def n_frames(self) -> int:
        return max(1, int(round(self.duration_s * self.fps)))


def _hash01(*ints: int) -> float:
    """确定性伪随机 [0,1)，用于秸秆位置抖动（与帧无关）。"""
    h = 2166136261
    for v in ints:
        h ^= (v + 0x9E3779B9) & 0xFFFFFFFF
        h = (h * 16777619) & 0xFFFFFFFF
    return ((h >> 8) & 0xFFFFFF) / float(1 << 24)


def _value_noise(shape: tuple[int, int], rng: np.random.Generator, cells: int = 8) -> np.ndarray:
    """低频随机场 [0,1]，用于粉尘与土壤斑驳。"""
    h, w = shape
    small = rng.random((cells, max(1, int(cells * w / h))), dtype=np.float32)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC).clip(0, 1)


class SyntheticScene:
    def __init__(self, cfg: SynthConfig) -> None:
        self.cfg = cfg
        self.camera = cfg.camera or PinholeCamera.from_fov(cfg.width, cfg.height, 60, x_fwd_m=-2.5, z_m=3.2, pitch_deg=15)
        if (self.camera.width, self.camera.height) != (cfg.width, cfg.height):
            self.camera = self.camera.resized(cfg.width, cfg.height)
        self.rng = np.random.default_rng(cfg.seed)
        self.n_frames = cfg.n_frames
        self._horizon_v = self.camera.horizon_v()
        # 像素网格 → 地面坐标（车体系），一次性计算
        us, vs = np.meshgrid(np.arange(cfg.width, dtype=np.float32), np.arange(cfg.height, dtype=np.float32))
        H = self.camera.ground_homography().astype(np.float32)
        pts = np.stack([us.ravel(), vs.ravel(), np.ones(us.size, dtype=np.float32)], axis=0)
        g = H @ pts
        w = g[2]
        valid = w > 1e-6
        with np.errstate(divide="ignore", invalid="ignore"):
            gx = np.where(valid, g[0] / w, np.nan).reshape(cfg.height, cfg.width)
            gy = np.where(valid, g[1] / w, np.nan).reshape(cfg.height, cfg.width)
        self._gx, self._gy = gx, gy
        self._ground_mask = np.isfinite(gx) & (gx > self.camera.position[0] + 0.05)
        self._soil_noise = _value_noise((cfg.height, cfg.width), np.random.default_rng(cfg.seed + 11), cells=24)
        self._texture_seed = cfg.seed + 101

    # ------------------------------------------------------------------ helpers
    def shift_at(self, i: int) -> float:
        return self.cfg.speed_mps * (i / self.cfg.fps)

    def ts_at(self, i: int) -> float:
        return i / self.cfg.fps

    def _frame_rng(self, i: int) -> np.random.Generator:
        return np.random.default_rng(self.cfg.seed * 7919 + i)

    # ----------------------------------------------------------------- rendering
    def render(self, i: int) -> np.ndarray:
        cfg = self.cfg
        shift = self.shift_at(i)
        rng = self._frame_rng(i)
        img = self._render_background(shift)
        self._render_far_canopy(img)
        self._render_drawables(img, shift)
        img = self._post_effects(img, rng)
        if cfg.header_overlay:
            self._render_header(img)
        return img

    def _render_background(self, shift: float) -> np.ndarray:
        cfg = self.cfg
        h, w = cfg.height, cfg.width
        img = np.empty((h, w, 3), dtype=np.float32)
        # 天空渐变
        v = np.arange(h, dtype=np.float32)[:, None]
        t = np.clip(v / max(self._horizon_v, 1.0), 0, 1)
        sky = C_SKY_TOP[None, None, :] * (1 - t[..., None]) + C_SKY_HOR[None, None, :] * t[..., None]
        img[:] = sky
        # 地面：按世界坐标取纹理（随车辆前进而流动）
        gm = self._ground_mask
        gx_w = self._gx + shift
        gy = self._gy
        # 垄/沟：横向周期
        phase = (gy / cfg.row_spacing_m + 0.5) % 1.0  # 0 处为行中心（垄）
        ridge = 0.5 + 0.5 * np.cos(2 * np.pi * phase)  # 1=垄顶 0=沟底
        # 沿行方向的细纹理
        fine = 0.5 + 0.5 * np.sin(gx_w * 9.0 + gy * 3.0) * np.sin(gx_w * 2.3)
        tex = 0.65 * ridge + 0.20 * fine + 0.30 * (self._soil_noise - 0.5)
        tex = np.clip(tex, 0, 1)[..., None]
        ground = C_SOIL[None, None, :] * (1 - tex) + C_RIDGE[None, None, :] * tex
        # 远处土壤由于透视变密，略微提亮
        img[gm] = ground[gm]
        return img

    def _render_far_canopy(self, img: np.ndarray) -> None:
        """far_stalk_m 以外用冠层色带代替单株（与地平线之间）。"""
        cfg = self.cfg
        cam = self.camera
        top_far = cam.ground_to_image(cam.position[0] + cfg.far_stalk_m, 0.0)
        if top_far is None:
            return
        base_row = int(round(top_far[1]))
        # 冠层顶（stalk_height 高）在远处的像素行
        uv, z = cam.project(np.array([[cam.position[0] + cfg.far_stalk_m, 0.0, cfg.stalk_height_m]]))
        if z[0] <= 0:
            return
        top_row = int(round(uv[0, 1]))
        y0, y1 = max(0, min(top_row, base_row)), min(cfg.height, max(top_row, base_row) + 1)
        if y1 <= y0:
            return
        band = img[y0:y1]
        noise = self._soil_noise[y0:y1][..., None]
        band[:] = C_CANOPY[None, None, :] * (0.85 + 0.3 * noise)

    def _stalk_positions(self, shift: float) -> list[tuple[float, float, float, int, int]]:
        """返回可见范围内的秸秆 (x_v, y_v, height_scale, row_k, idx)。"""
        cfg = self.cfg
        cam = self.camera
        x_cam = cam.position[0]
        out = []
        n = cfg.n_rows_scene
        x_min = x_cam + 0.2
        x_max = x_cam + cfg.far_stalk_m
        k0 = int(math.floor((x_min + shift) / cfg.plant_spacing_m))
        k1 = int(math.ceil((x_max + shift) / cfg.plant_spacing_m))
        for r in range(n):
            y_row = (r - (n - 1) / 2.0) * cfg.row_spacing_m
            for k in range(k0, k1 + 1):
                jx = (_hash01(r, k, 1) - 0.5) * 0.08
                jy = (_hash01(r, k, 2) - 0.5) * 0.10
                hs = 0.85 + 0.3 * _hash01(r, k, 3)
                x_w = k * cfg.plant_spacing_m + jx
                x_v = x_w - shift
                if x_v < x_min or x_v > x_max:
                    continue
                out.append((x_v, y_row + jy, hs, r, k))
        return out

    def _render_drawables(self, img: np.ndarray, shift: float) -> None:
        cfg = self.cfg
        cam = self.camera
        draw: list[tuple[float, int, object]] = []  # (depth, order, payload)
        for x_v, y_v, hs, r, k in self._stalk_positions(shift):
            draw.append((x_v, 0, ("stalk", x_v, y_v, hs, r, k)))
        for obj in cfg.objects:
            x_v = obj.x0_fwd - shift
            if x_v < cam.position[0] + 0.1:
                continue
            draw.append((x_v, 1, ("obj", obj, x_v)))
        draw.sort(key=lambda d: (-d[0], d[1]))
        for _depth, _o, payload in draw:
            if payload[0] == "stalk":
                self._draw_stalk(img, *payload[1:])
            else:
                self._draw_object(img, payload[1], payload[2])

    def _fill(self, img: np.ndarray, pts: np.ndarray, color: np.ndarray) -> None:
        if pts is None or len(pts) < 3:
            return
        p = np.round(pts).astype(np.int32).reshape(-1, 1, 2)
        cv2.fillPoly(img, [p], color.tolist(), lineType=cv2.LINE_AA)

    def _project_hull(self, pts3: np.ndarray) -> np.ndarray | None:
        uv, z = self.camera.project(pts3)
        if np.any(z <= 1e-6):
            return None
        hull = cv2.convexHull(uv.astype(np.float32))
        return hull.reshape(-1, 2)

    def _draw_stalk(self, img: np.ndarray, x_v: float, y_v: float, hs: float, r: int, k: int) -> None:
        cfg = self.cfg
        hgt = cfg.stalk_height_m * hs
        half_w = 0.015 + 0.01 * _hash01(r, k, 4)
        pts3 = np.array(
            [
                [x_v, y_v - half_w, 0.0],
                [x_v, y_v + half_w, 0.0],
                [x_v, y_v + half_w * 0.6, hgt],
                [x_v, y_v - half_w * 0.6, hgt],
            ]
        )
        uv, z = self.camera.project(pts3)
        if np.any(z <= 1e-6):
            return
        shade = 0.8 + 0.4 * _hash01(r, k, 5)
        self._fill(img, uv, C_STALK * shade)
        # 稀疏干叶：仅 0.5 m 以上，长度短，保持垄底可见
        dist = x_v - self.camera.position[0]
        if dist <= cfg.leaf_max_dist_m:
            n_leaf = 1 + int(_hash01(r, k, 6) * 2)
            for j in range(n_leaf):
                z0 = 0.6 + 1.1 * _hash01(r, k, 7 + j)
                side = 1.0 if _hash01(r, k, 20 + j) > 0.5 else -1.0
                ln = 0.22 + 0.15 * _hash01(r, k, 30 + j)
                leaf = np.array(
                    [
                        [x_v, y_v, z0],
                        [x_v + 0.03, y_v, z0 + 0.04],
                        [x_v + 0.05, y_v + side * ln, z0 - 0.12],
                        [x_v - 0.02, y_v + side * ln * 0.9, z0 - 0.16],
                    ]
                )
                luv, lz = self.camera.project(leaf)
                if np.all(lz > 1e-6):
                    self._fill(img, luv, C_LEAF * (0.85 + 0.3 * _hash01(r, k, 40 + j)))

    def _object_points(self, obj: SynthObject, x_v: float) -> dict[str, np.ndarray]:
        a = obj.size_m / 2.0
        ang = np.linspace(0, 2 * np.pi, 24, endpoint=False)
        ring = np.stack([np.cos(ang), np.sin(ang)], axis=1)
        pts: dict[str, np.ndarray] = {}
        if obj.kind == "pipe":
            r = a
            base = np.column_stack([x_v + r * ring[:, 0], obj.y_lat + r * ring[:, 1], np.zeros(len(ring))])
            top = base.copy()
            top[:, 2] = obj.height_m
            pts["base"], pts["top"] = base, top
            if obj.pad:
                rp = max(0.4, 2.2 * r)
                pts["pad"] = np.column_stack([x_v + rp * ring[:, 0], obj.y_lat + rp * ring[:, 1], np.zeros(len(ring))])
        elif obj.kind == "stone":
            # 椭球：赤道环 + 顶点 + 底面环（半径略小）
            eq = np.column_stack([x_v + a * ring[:, 0], obj.y_lat + a * ring[:, 1], np.full(len(ring), obj.height_m * 0.45)])
            bot = np.column_stack([x_v + 0.8 * a * ring[:, 0], obj.y_lat + 0.8 * a * ring[:, 1], np.zeros(len(ring))])
            top = np.array([[x_v, obj.y_lat, obj.height_m]])
            pts["body"] = np.vstack([eq, bot, top])
            pts["base"] = bot
        else:  # stake: 细长盒
            w = a
            base = np.array(
                [[x_v - w, obj.y_lat - w, 0], [x_v + w, obj.y_lat - w, 0], [x_v + w, obj.y_lat + w, 0], [x_v - w, obj.y_lat + w, 0]],
                dtype=float,
            )
            top = base.copy()
            top[:, 2] = obj.height_m
            pts["base"], pts["top"] = base, top
        return pts

    def _draw_object(self, img: np.ndarray, obj: SynthObject, x_v: float) -> None:
        pts = self._object_points(obj, x_v)
        if obj.kind == "pipe":
            if "pad" in pts:
                self._fill(img, self._project_hull(pts["pad"]), C_PAD)
            lateral = self._project_hull(np.vstack([pts["base"], pts["top"]]))
            if lateral is None:
                return
            self._fill(img, lateral, C_PIPE)
            # 简单竖向明暗：左半偏锈色
            left = lateral.copy()
            cx = lateral[:, 0].mean()
            left[:, 0] = np.minimum(left[:, 0], cx)
            self._fill(img, cv2.convexHull(left.astype(np.float32)).reshape(-1, 2), C_PIPE_RUST * 0.9 + C_PIPE * 0.1)
            self._fill(img, self._project_hull(pts["top"]), C_PIPE_TOP)
        elif obj.kind == "stone":
            hull = self._project_hull(pts["body"])
            if hull is None:
                return
            self._fill(img, hull, C_STONE)
            # 下半部分加深
            low = hull.copy()
            cy = hull[:, 1].mean()
            low[:, 1] = np.maximum(low[:, 1], cy)
            self._fill(img, cv2.convexHull(low.astype(np.float32)).reshape(-1, 2), C_STONE * 0.8)
        else:
            lateral = self._project_hull(np.vstack([pts["base"], pts["top"]]))
            self._fill(img, lateral, C_STAKE)

    def _post_effects(self, img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        cfg = self.cfg
        h, w = cfg.height, cfg.width
        out = img
        if cfg.dust > 0:
            # 深度雾化：地面像素按距离，天空按最大
            dist = np.where(self._ground_mask, self._gx - self.camera.position[0], 60.0)
            dist = np.nan_to_num(dist, nan=60.0).clip(0, 60)
            k = 0.012 + 0.05 * cfg.dust
            alpha = (1 - np.exp(-k * dist))[..., None].astype(np.float32)
            out = out * (1 - alpha) + C_FOG[None, None, :] * alpha
            # 低频粉尘团（乘性亮度）
            dust_field = _value_noise((h, w), rng, cells=6)
            out = out * (1 + cfg.dust * 0.25 * (dust_field[..., None] - 0.5))
        # 亮度闪烁 + 传感器噪声
        gain = 1.0 + cfg.flicker * (rng.random() - 0.5) * 2
        out = out * gain + rng.normal(0, 2.0, size=(h, w, 1)).astype(np.float32)
        out = np.clip(out, 0, 255).astype(np.uint8)
        if cfg.jitter_px > 0:
            dx, dy = rng.normal(0, cfg.jitter_px / 2.0, size=2)
            dx, dy = float(np.clip(dx, -cfg.jitter_px, cfg.jitter_px)), float(np.clip(dy, -cfg.jitter_px, cfg.jitter_px))
            M = np.array([[1, 0, dx], [0, 1, dy]], dtype=np.float32)
            out = cv2.warpAffine(out, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
        return out

    def default_header_polygon(self) -> list[tuple[float, float]]:
        return [(0.0, 1.0), (0.0, 0.86), (0.33, 0.86), (0.40, 0.72), (0.60, 0.72), (0.67, 0.86), (1.0, 0.86), (1.0, 1.0)]

    def _render_header(self, img: np.ndarray) -> None:
        """割台 / 分禾器轮廓：相对相机静止，不随地面运动、不受抖动影响。"""
        cfg = self.cfg
        poly = cfg.header_polygon or self.default_header_polygon()
        pts = np.array([(x * (cfg.width - 1), y * (cfg.height - 1)) for x, y in poly], dtype=np.float32)
        p = np.round(pts).astype(np.int32).reshape(-1, 1, 2)
        cv2.fillPoly(img, [p], C_HEADER.tolist(), lineType=cv2.LINE_AA)
        cv2.polylines(img, [p], True, C_HEADER_DARK.tolist(), thickness=3, lineType=cv2.LINE_AA)
        # 螺栓 / 划痕纹理，确保不剔除时会被当作"非植被灰色物体"
        rs = np.random.default_rng(self._texture_seed)
        mask = np.zeros(img.shape[:2], dtype=np.uint8)
        cv2.fillPoly(mask, [p], 255)
        ys, xs = np.nonzero(mask)
        if len(xs):
            for _ in range(12):
                j = rs.integers(0, len(xs))
                cv2.circle(img, (int(xs[j]), int(ys[j])), int(rs.integers(2, 5)), C_HEADER_DARK.tolist(), -1, lineType=cv2.LINE_AA)

    # -------------------------------------------------------------- ground truth
    def ground_truth(self, i: int) -> list[GTObject]:
        cfg = self.cfg
        shift = self.shift_at(i)
        out: list[GTObject] = []
        for obj in cfg.objects:
            x_v = obj.x0_fwd - shift
            bbox = None
            visible = False
            if x_v > self.camera.position[0] + 0.1:
                pts = self._object_points(obj, x_v)
                allp = np.vstack([v for k, v in pts.items() if k != "pad"])
                uv, z = self.camera.project(allp)
                if np.all(z > 1e-6):
                    x1, y1 = uv.min(axis=0)
                    x2, y2 = uv.max(axis=0)
                    cx1, cy1 = max(0.0, float(x1)), max(0.0, float(y1))
                    cx2, cy2 = min(cfg.width - 1.0, float(x2)), min(cfg.height - 1.0, float(y2))
                    if cx2 - cx1 >= 2 and cy2 - cy1 >= 2:
                        bbox = (cx1, cy1, cx2, cy2)
                        area_full = max((x2 - x1) * (y2 - y1), 1e-6)
                        visible = bool(((cx2 - cx1) * (cy2 - cy1)) / area_full > 0.5)
            out.append(GTObject(kind=obj.kind, x_fwd=float(x_v), y_lat=float(obj.y_lat), bbox=bbox, visible=visible))
        return out

    def frames(self):
        for i in range(self.n_frames):
            yield i, self.ts_at(i), self.render(i)


# ------------------------------------------------------------------- scenarios
# 每个场景：物体布局 + 默认时长/车速/是否叠加割台轮廓。相机由配置给出。
SCENARIOS: dict[str, dict] = {
    "pipe_forward": {
        "objects": [SynthObject("pipe", x0_fwd=18.0, y_lat=0.0, size_m=0.219, height_m=0.5, pad=True)],
        "duration_s": 8.0,
        "speed_mps": 2.0,
        "header_overlay": False,
    },
    "stone_forward": {
        "objects": [SynthObject("stone", x0_fwd=16.0, y_lat=-0.1, size_m=0.30, height_m=0.20)],
        "duration_s": 8.0,
        "speed_mps": 2.0,
        "header_overlay": False,
    },
    "mixed_forward": {
        "objects": [
            SynthObject("pipe", x0_fwd=22.0, y_lat=0.0, size_m=0.219, height_m=0.5, pad=True),
            SynthObject("stone", x0_fwd=12.0, y_lat=-0.15, size_m=0.28, height_m=0.18),
            SynthObject("stone", x0_fwd=17.0, y_lat=2.6, size_m=0.30, height_m=0.2),  # 路外，不应 ≥L2
        ],
        "duration_s": 11.0,
        "speed_mps": 2.0,
        "header_overlay": False,
    },
    "pipe_header": {
        "objects": [SynthObject("pipe", x0_fwd=4.0, y_lat=0.6, size_m=0.219, height_m=0.5)],
        "duration_s": 3.0,
        "speed_mps": 1.0,
        "header_overlay": True,
    },
    "header_selfview": {
        "objects": [],
        "duration_s": 4.0,
        "speed_mps": 2.0,
        "header_overlay": True,
    },
    "empty": {
        "objects": [],
        "duration_s": 4.0,
        "speed_mps": 2.0,
        "header_overlay": False,
    },
}


def make_scene(
    scenario: str,
    camera: PinholeCamera,
    fps: float = 15.0,
    speed_mps: float | None = None,
    duration_s: float | None = None,
    seed: int | None = None,
    header_overlay: bool | None = None,
    dust: float | None = None,
) -> SyntheticScene:
    if scenario not in SCENARIOS:
        raise KeyError(f"未知合成场景 {scenario!r}，可选: {sorted(SCENARIOS)}")
    sc = SCENARIOS[scenario]
    cfg = SynthConfig(
        width=camera.width,
        height=camera.height,
        fps=fps,
        duration_s=sc["duration_s"] if duration_s is None else duration_s,
        speed_mps=sc["speed_mps"] if speed_mps is None else speed_mps,
        camera=camera,
        objects=list(sc["objects"]),
        header_overlay=sc["header_overlay"] if header_overlay is None else header_overlay,
        seed=0 if seed is None else seed,
    )
    if dust is not None:
        cfg.dust = dust
    return SyntheticScene(cfg)


def write_video(scene: SyntheticScene, path: str | Path, labels_dir: str | Path | None = None) -> Path:
    """把场景写成视频（优先 mp4v，失败回退 MJPG .avi）；可选输出 YOLO 格式标签。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kinds = {"stone": 0, "pipe": 1, "stake": 2}
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), scene.cfg.fps, (scene.cfg.width, scene.cfg.height))
    if not writer.isOpened():
        path = path.with_suffix(".avi")
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), scene.cfg.fps, (scene.cfg.width, scene.cfg.height))
    if labels_dir is not None:
        labels_dir = Path(labels_dir)
        (labels_dir / "images").mkdir(parents=True, exist_ok=True)
        (labels_dir / "labels").mkdir(parents=True, exist_ok=True)
    try:
        for i, _ts, img in scene.frames():
            writer.write(img)
            if labels_dir is not None:
                cv2.imwrite(str(labels_dir / "images" / f"{i:05d}.jpg"), img)
                lines = []
                for gt in scene.ground_truth(i):
                    if gt.bbox is None or not gt.visible:
                        continue
                    x1, y1, x2, y2 = gt.bbox
                    cx, cy = (x1 + x2) / 2 / scene.cfg.width, (y1 + y2) / 2 / scene.cfg.height
                    bw, bh = (x2 - x1) / scene.cfg.width, (y2 - y1) / scene.cfg.height
                    lines.append(f"{kinds.get(gt.kind, 3)} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
                (labels_dir / "labels" / f"{i:05d}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
    finally:
        writer.release()
    return path
