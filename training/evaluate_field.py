#!/usr/bin/env python3
"""田间 / 回放评估：按距离分桶的召回、精度、首次预警距离、预警时间、每小时误报。

输入：
* ``--dets``：``smartview replay --log-detections dets.jsonl`` 输出的逐帧检测 / 轨迹 / 等级；
* 真值二选一：``--gt gt.jsonl``（每行 ``{"cam","seq","objects":[{"cls","bbox":[x1,y1,x2,y2],"dist_m":..}]}``），
  或 ``--synthetic <scenario> --config cfg --cam id``（由合成场景重建真值，用于离线演示 / 回归）。

示例::

    smartview replay -c configs/replay_synthetic.yaml --no-hmi --log-detections /tmp/dets.jsonl
    python training/evaluate_field.py --dets /tmp/dets.jsonl --synthetic pipe_forward --config configs/replay_synthetic.yaml --cam fwd
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
from pathlib import Path


def iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    iw, ih = max(0.0, min(ax2, bx2) - max(ax1, bx1)), max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    ua = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / ua if ua > 0 else 0.0


def matched(det_box, gt_box, iou_thr=0.3, foot_px=12.0) -> bool:
    if iou(det_box, gt_box) >= iou_thr:
        return True
    fx, fy = (det_box[0] + det_box[2]) / 2, det_box[3]
    gx, gy = (gt_box[0] + gt_box[2]) / 2, gt_box[3]
    return abs(fx - gx) <= foot_px and abs(fy - gy) <= foot_px


def load_dets(path: Path, cam: str) -> dict[int, dict]:
    out = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec["cam"] == cam:
                out[int(rec["seq"])] = rec
    return out


def gt_from_synthetic(scenario: str, config: str, cam_id: str) -> tuple[dict[int, list[dict]], float, float]:
    from smartview.config import SmartViewConfig
    from smartview.geometry.camera import PinholeCamera
    from smartview.synth.scene import make_scene

    cfg = SmartViewConfig.load(config)
    cam = cfg.camera(cam_id)
    scene = make_scene(scenario, PinholeCamera.from_mount(cam.width, cam.height, cam.mount), fps=cam.fps, speed_mps=cfg.speed.manual_mps)
    kind_map = {"pipe": "well_pipe", "stone": "stone", "stake": "stake"}
    gt = {}
    for i in range(scene.n_frames):
        objs = []
        for g in scene.ground_truth(i):
            if g.bbox is None or not g.visible:
                continue
            objs.append({"cls": kind_map.get(g.kind, g.kind), "bbox": list(g.bbox), "dist_m": g.x_fwd})
        gt[i] = objs
    return gt, scene.cfg.fps, scene.cfg.speed_mps


def load_gt(path: Path, cam: str) -> dict[int, list[dict]]:
    out = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec["cam"] == cam:
                out[int(rec["seq"])] = rec["objects"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dets", required=True)
    ap.add_argument("--cam", required=True)
    ap.add_argument("--gt", default=None)
    ap.add_argument("--synthetic", default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--fps", type=float, default=15.0)
    ap.add_argument("--speed", type=float, default=None, help="车速 m/s（预警时间 = 距离 / 车速）")
    ap.add_argument("--buckets", default="0,3,6,10,15,20")
    ap.add_argument("--out-csv", default=None)
    args = ap.parse_args()

    dets = load_dets(Path(args.dets), args.cam)
    if args.synthetic:
        if not args.config:
            raise SystemExit("--synthetic 需要 --config")
        gt, fps, speed = gt_from_synthetic(args.synthetic, args.config, args.cam)
        args.fps, args.speed = fps, args.speed or speed
    elif args.gt:
        gt = load_gt(Path(args.gt), args.cam)
    else:
        raise SystemExit("需要 --gt 或 --synthetic")
    edges = [float(x) for x in args.buckets.split(",")]
    labels = [f"{edges[i]:g}-{edges[i+1]:g}m" for i in range(len(edges) - 1)]

    def bucket(d):
        for i in range(len(edges) - 1):
            if edges[i] <= d < edges[i + 1]:
                return labels[i]
        return None

    # 检测级召回 / 精度（按距离桶）
    tp = collections.Counter()
    gt_n = collections.Counter()
    det_tp = det_total = 0
    track_tp = collections.Counter()
    first_track_dist = []
    seen_track_match = False
    for seq, objs in sorted(gt.items()):
        rec = dets.get(seq)
        rec_dets = rec["dets"] if rec else []
        rec_tracks = rec["tracks"] if rec else []
        for o in objs:
            b = bucket(o["dist_m"])
            if b is None:
                continue
            key = (o["cls"], b)
            gt_n[key] += 1
            if any(matched(d["bbox"], o["bbox"]) for d in rec_dets):
                tp[key] += 1
            if any(matched(t["bbox"], o["bbox"]) for t in rec_tracks):
                track_tp[key] += 1
                if not seen_track_match:
                    seen_track_match = True
                    first_track_dist.append(o["dist_m"])
        for d in rec_dets:
            det_total += 1
            if any(matched(d["bbox"], o["bbox"]) for o in objs):
                det_tp += 1
    # 报警级指标
    first_alarm = {2: None, 3: None}
    fa_frames = 0
    alarm_episodes = 0
    prev_alarm = False
    for seq in sorted(dets):
        rec = dets[seq]
        lvl = rec.get("level", 0)
        objs = gt.get(seq, [])
        near = any(o["dist_m"] <= 20.0 for o in objs)
        for L in (2, 3):
            if lvl >= L and first_alarm[L] is None:
                first_alarm[L] = (seq, min((o["dist_m"] for o in objs), default=None))
        is_fa = lvl >= 2 and not near
        fa_frames += int(is_fa)
        if is_fa and not prev_alarm:
            alarm_episodes += 1
        prev_alarm = is_fa
    hours = (len(dets) / args.fps) / 3600.0 if dets else 0.0

    rows = []
    print("## 按类别 / 距离桶的召回（检测级 / 轨迹级）\n")
    print("| 类别 | 距离桶 | 真值帧数 | 检测召回 | 轨迹召回 |\n|---|---|---|---|---|")
    for (cls, b) in sorted(gt_n, key=lambda k: (k[0], labels.index(k[1]))):
        n = gt_n[(cls, b)]
        r1, r2 = tp[(cls, b)] / n, track_tp[(cls, b)] / n
        print(f"| {cls} | {b} | {n} | {r1:.2%} | {r2:.2%} |")
        rows.append({"class": cls, "bucket": b, "gt_frames": n, "det_recall": round(r1, 4), "track_recall": round(r2, 4)})
    prec = det_tp / det_total if det_total else float("nan")
    print(f"\n检测精度（与任一真值匹配）：{prec:.2%}（{det_tp}/{det_total}）")
    for L in (2, 3):
        fa = first_alarm[L]
        if fa and fa[1] is not None:
            t = fa[1] / args.speed if args.speed else float("nan")
            print(f"首次 L{L}：帧 {fa[0]}，目标距离 {fa[1]:.1f} m，预警时间 {t:.1f} s（车速 {args.speed} m/s）")
        else:
            print(f"首次 L{L}：未触发")
    if first_track_dist:
        print(f"首次形成确认轨迹时目标距离：{first_track_dist[0]:.1f} m")
    print(f"误报（≥L2 且 20 m 内无真值）：{alarm_episodes} 次 / {fa_frames} 帧；折合 {alarm_episodes / hours if hours else float('nan'):.1f} 次/小时（素材 {hours*3600:.0f} s）")
    if args.out_csv:
        with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["class", "bucket", "gt_frames", "det_recall", "track_recall"])
            w.writeheader()
            w.writerows(rows)
        print(f"CSV → {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
