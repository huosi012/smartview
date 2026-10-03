#!/usr/bin/env python3
"""生成合成演示视频（可选同时输出 YOLO 格式标签）。

示例::

    python scripts/make_demo_video.py --scenario pipe_forward --out data/demo/pipe_forward.mp4
    python scripts/make_demo_video.py --scenario header_selfview --role header --out data/demo/header.mp4 --labels data/demo/labels
"""

from __future__ import annotations

import argparse
from pathlib import Path

from smartview.geometry.camera import PinholeCamera
from smartview.synth.scene import SCENARIOS, make_scene, write_video


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default="pipe_forward", choices=sorted(SCENARIOS))
    ap.add_argument("--role", default=None, choices=["forward", "header"], help="相机角色，默认按场景推断")
    ap.add_argument("--out", required=True)
    ap.add_argument("--labels", default=None, help="输出 YOLO 标签目录")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=360)
    ap.add_argument("--fps", type=float, default=15)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--duration", type=float, default=None)
    ap.add_argument("--speed", type=float, default=None, help="车速 m/s")
    args = ap.parse_args()

    role = args.role or ("header" if SCENARIOS[args.scenario]["header_overlay"] else "forward")
    if role == "forward":
        cam = PinholeCamera.from_fov(args.width, args.height, 60, x_fwd_m=-2.5, z_m=3.2, pitch_deg=15)
    else:
        cam = PinholeCamera.from_fov(args.width, args.height, 100, x_fwd_m=0.3, y_lat_m=0.6, z_m=0.5, pitch_deg=25)
    scene = make_scene(args.scenario, cam, fps=args.fps, speed_mps=args.speed, duration_s=args.duration, seed=args.seed)
    out = write_video(scene, Path(args.out), labels_dir=args.labels)
    print(f"写入 {out}（{scene.n_frames} 帧，{scene.cfg.width}x{scene.cfg.height}@{scene.cfg.fps:g}fps）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
