"""报警分级规则（纯函数，便于单测与文档对照）。

| 相机 | L1 | L2 | L3 |
|---|---|---|---|
| 前视 | 邻近/在路、hits≥2、d≤20 m | 在路且确认，且 (d≤12 m 或 TTC≤6 s)，score·w≥0.4 | 在路且确认，且 (d≤6 m 或 TTC≤3 s)；人/动物在路 d≤10 m |
| 割台 | 确认但不在路/邻近范围外 | 邻近路径且确认 (d≤3 m)；在路但 d>3 m | 在路且确认 (hits≥2) 且 d≤3 m |
"""

from __future__ import annotations

from dataclasses import dataclass

from smartview.config import MachineConfig, RiskConfig
from smartview.types import AlarmLevel, RiskAssessment, Track

LIVING = {"person", "animal"}


@dataclass(frozen=True)
class SensitivityParams:
    conf_thr: float
    min_hits: int


_SENS = {
    "low": SensitivityParams(0.45, 4),
    "medium": SensitivityParams(0.35, 3),
    "high": SensitivityParams(0.25, 2),
}


def sensitivity_params(name: str) -> SensitivityParams:
    return _SENS.get(name, _SENS["medium"])


def half_path(machine: MachineConfig) -> float:
    return machine.header_width_m / 2.0 + machine.path_margin_m


def assess_track(track: Track, role: str, cfg: RiskConfig, machine: MachineConfig) -> RiskAssessment:
    """对单条（已确认的）轨迹给出风险等级与原因。"""
    th = cfg.thresholds
    sens = sensitivity_params(cfg.sensitivity)
    w = cfg.class_weights.get(track.cls_name, 0.6)
    weighted = track.score * w
    reasons: list[str] = []
    g = track.ground
    dist = track.dist_m if track.dist_m is not None else (g.x_fwd if g else None)
    ttc = track.ttc_s
    level = AlarmLevel.L0

    def mk(level: AlarmLevel) -> RiskAssessment:
        return RiskAssessment(
            cam_id=track.cam_id,
            track_id=track.track_id,
            level=level,
            score=float(weighted),
            dist_m=dist,
            ttc_s=ttc,
            reasons=reasons,
            cls_name=track.cls_name,
            row=g.row if g else None,
            in_path=bool(g.in_path) if g else False,
        )

    if track.score < sens.conf_thr:
        reasons.append("置信度不足")
        return mk(AlarmLevel.L0)
    confirmed = track.hits >= sens.min_hits
    if track.hits < 2:
        reasons.append("未确认")
        return mk(AlarmLevel.L0)
    if g is None or dist is None:
        reasons.append("无法定位")
        return mk(AlarmLevel.L1)

    hp = half_path(machine)
    in_path = abs(g.y_lat) <= hp
    adjacent = abs(g.y_lat) <= hp + th.adjacent_margin_m

    if role == "forward":
        if not adjacent:
            reasons.append("路径外")
            return mk(AlarmLevel.L0)
        if dist > th.fwd_l1_max_dist_m:
            reasons.append(f"距离 {dist:.0f} m 超出关注范围")
            return mk(AlarmLevel.L0)
        level = AlarmLevel.L1
        reasons.append("邻近路径" if not in_path else "在路径内")
        if in_path and confirmed:
            near3 = dist <= th.fwd_l3_dist_m or (ttc is not None and ttc <= th.fwd_l3_ttc_s)
            near2 = dist <= th.fwd_l2_dist_m or (ttc is not None and ttc <= th.fwd_l2_ttc_s)
            if track.cls_name in LIVING and dist <= th.person_l3_dist_m:
                reasons.append("路径内有人/动物")
                return mk(AlarmLevel.L3)
            if weighted >= th.min_weighted_score:
                if near3:
                    reasons.append(f"距离 {dist:.1f} m" + (f"，TTC {ttc:.1f} s" if ttc is not None else ""))
                    return mk(AlarmLevel.L3)
                if near2:
                    reasons.append(f"距离 {dist:.1f} m" + (f"，TTC {ttc:.1f} s" if ttc is not None else ""))
                    return mk(AlarmLevel.L2)
            else:
                reasons.append("加权置信度不足")
        elif in_path and not confirmed:
            reasons.append("待确认")
        return mk(level)

    # 割台近场相机
    if not confirmed:
        reasons.append("待确认")
        return mk(AlarmLevel.L1 if adjacent else AlarmLevel.L0)
    if in_path:
        if dist <= th.header_l3_dist_m:
            reasons.append(f"割台前方 {dist:.1f} m，路径内")
            return mk(AlarmLevel.L3)
        reasons.append(f"路径内 {dist:.1f} m")
        return mk(AlarmLevel.L2)
    if adjacent:
        if dist <= th.header_l2_dist_m:
            reasons.append(f"邻近路径 {dist:.1f} m")
            return mk(AlarmLevel.L2)
        reasons.append("邻近路径")
        return mk(AlarmLevel.L1)
    reasons.append("路径外")
    return mk(AlarmLevel.L1)
