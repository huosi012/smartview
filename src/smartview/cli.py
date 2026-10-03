"""命令行入口：run / replay / demo / synth / calib-mask / export-events / selftest / bench。"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path

from smartview import __version__

log = logging.getLogger("smartview")


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def find_default_config() -> Path | None:
    for cand in (Path.cwd() / "configs" / "replay_synthetic.yaml", _repo_root() / "configs" / "replay_synthetic.yaml"):
        if cand.exists():
            return cand
    return None


def _load_cfg(path: str | None):
    from smartview.config import SmartViewConfig

    p = Path(path) if path else find_default_config()
    if p is None or not p.exists():
        raise SystemExit("找不到配置文件，请用 -c/--config 指定（示例：configs/replay_synthetic.yaml）")
    return SmartViewConfig.load(p)


# ------------------------------------------------------------------ commands
def cmd_run(args) -> int:
    from smartview.pipeline import SmartViewApp

    cfg = _load_cfg(args.config)
    app = SmartViewApp(cfg, live=True, hmi=not args.no_hmi, log_detections=args.log_detections)
    log.info("真机模式启动：%d 路相机，检测后端 %s", len(cfg.cameras), cfg.detector.backend)
    app.run_threaded()
    return 0


def _replay(cfg, args, hold: bool) -> int:
    from smartview.pipeline import SmartViewApp

    app = SmartViewApp(
        cfg,
        live=False,
        hmi=bool(args.hmi),
        realtime=bool(args.realtime),
        log_detections=getattr(args, "log_detections", None),
        seed=getattr(args, "seed", None),
        duration_s=getattr(args, "duration", None),
    )
    if args.hmi:
        app.start_hmi()
        print(f"HMI: http://127.0.0.1:{cfg.hmi.port}/  （Ctrl-C 退出）", flush=True)
    try:
        summary = app.run_sync(max_frames=getattr(args, "max_frames", None))
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2), flush=True)
        if hold and args.hmi:
            print("回放结束，HMI 继续运行，按 Ctrl-C 退出", flush=True)
            while True:
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        app.shutdown()
    return 0


def cmd_replay(args) -> int:
    cfg = _load_cfg(args.config)
    return _replay(cfg, args, hold=bool(args.hold))


def cmd_demo(args) -> int:
    cfg = _load_cfg(args.config)
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cfg.storage.db_path = str(out / "events.db")
    cfg.storage.clip_dir = str(out / "clips")
    cfg.base_dir = str(out)
    if args.scenario:
        for cam in cfg.cameras:
            if cam.role == "forward":
                cam.source = f"synthetic:{args.scenario}"
    print(f"演示：合成场景回放 → 检测 → 跟踪 → 测距 → 分级报警；事件库与片段写入 {out}", flush=True)
    return _replay(cfg, args, hold=bool(args.hmi))


def cmd_synth(args) -> int:
    from smartview.geometry.camera import PinholeCamera
    from smartview.synth.scene import SCENARIOS, make_scene, write_video

    role = args.role or ("header" if SCENARIOS[args.scenario]["header_overlay"] else "forward")
    if role == "forward":
        cam = PinholeCamera.from_fov(args.width, args.height, 60, x_fwd_m=-2.5, z_m=3.2, pitch_deg=15)
    else:
        cam = PinholeCamera.from_fov(args.width, args.height, 100, x_fwd_m=0.3, y_lat_m=0.6, z_m=0.5, pitch_deg=25)
    scene = make_scene(args.scenario, cam, fps=args.fps, speed_mps=args.speed, duration_s=args.duration, seed=args.seed)
    out = write_video(scene, Path(args.out), labels_dir=args.labels)
    print(f"写入 {out}（{scene.n_frames} 帧，{scene.cfg.width}x{scene.cfg.height}@{scene.cfg.fps:g}fps）")
    return 0


def cmd_calib_mask(args) -> int:
    import cv2
    import yaml

    from smartview.tools.selfmask import learn_from_video

    mask, polys, preview, n = learn_from_video(args.video, max_frames=args.max_frames, stride=args.stride, margin_frac=args.margin)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), mask)
    prev_path = out.with_name(out.stem + "_preview.jpg")
    cv2.imwrite(str(prev_path), preview)
    frac = float((mask > 127).mean())
    print(f"使用 {n} 帧，自身区域占画面 {frac*100:.1f}%；遮罩 → {out}，预览 → {prev_path}")
    snippet = {"exclude_mask_png": str(out), "exclude_polygons": [[list(p) for p in poly] for poly in polys]}
    print("可写入相机配置的片段：")
    print(yaml.safe_dump(snippet, allow_unicode=True, sort_keys=False, default_flow_style=None))
    return 0


def cmd_export_events(args) -> int:
    from smartview.storage import EventStore

    cfg = _load_cfg(args.config)
    store = EventStore(cfg.resolve(cfg.storage.db_path) or cfg.storage.db_path)
    rows = [e.to_dict() for e in store.list(limit=args.limit)]
    store.close()
    out = Path(args.out)
    with out.open("w", newline="", encoding="utf-8") as f:
        if not rows:
            f.write("")
        else:
            cols = [c for c in rows[0] if c != "extra"]
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow({c: r[c] for c in cols})
    print(f"导出 {len(rows)} 条事件 → {out}")
    return 0


def cmd_selftest(args) -> int:
    from smartview.alarm import ConsoleSink, FakeGpioDriver, GpioSink
    from smartview.capture import build_source
    from smartview.detect import RegionMask, build_detector
    from smartview.geometry import GroundProjector
    from smartview.types import AlarmLevel, AlarmState, RiskAssessment

    cfg = _load_cfg(args.config)
    ok = True
    print("== 相机 / 检测器 ==")
    for cam in cfg.cameras:
        try:
            src = build_source(cam, cfg.speed)
            src.open()
            fr = src.read()
            src.close()
            if fr is None:
                raise RuntimeError("读不到帧")
            proj = GroundProjector(cam, cfg.machine)
            region = RegionMask.from_camera(cam, base_dir=cfg.base_dir)
            det = build_detector(cfg.detector, projector=proj, region=region, base_dir=cfg.base_dir)
            t0 = time.perf_counter()
            dets = det.detect(fr.image)
            dt = (time.perf_counter() - t0) * 1000
            near, far = proj.camera.ground_visible_range()
            print(f"  [OK] {cam.id:8s} {fr.image.shape[1]}x{fr.image.shape[0]} 首帧检测 {len(dets)} 个 {dt:.0f} ms；可见地面 {near:.1f} m ~ {'地平线' if far is None else f'{far:.1f} m'}；排除区 {'有' if region.has_exclusions else '无'}")
        except Exception as exc:  # noqa: BLE001
            ok = False
            print(f"  [FAIL] {cam.id}: {exc}")
    print("== 报警输出 ==")
    drv = FakeGpioDriver()
    gs = GpioSink(cfg.alarm.gpio, driver=drv)
    con = ConsoleSink()
    for lvl in (AlarmLevel.L1, AlarmLevel.L2, AlarmLevel.L3, AlarmLevel.L0):
        top = RiskAssessment("selftest", 0, lvl, 1.0, 6.2, 3.0, ["自检"], "well_pipe", None, True) if lvl else None
        st = AlarmState(level=lvl, ts=time.monotonic(), top=top, buzzer_on=lvl >= AlarmLevel.L2, lamp_on=lvl >= AlarmLevel.L2)
        con.on_state(st)
        gs.on_state(st)
        print(f"    GPIO 引脚状态: {drv.pins}")
        time.sleep(0.2 if not args.quick else 0)
    gs.close()
    print("自检", "通过" if ok else "失败")
    return 0 if ok else 1


def cmd_bench(args) -> int:
    import numpy as np

    from smartview.detect.base import DEFAULT_CLASSES
    from smartview.detect.yolo_onnx import YoloOnnxDetector

    det = YoloOnnxDetector(args.model, DEFAULT_CLASSES, input_size=args.size, num_threads=args.threads)
    det.warmup()
    img = (np.random.default_rng(0).random((720, 1280, 3)) * 255).astype(np.uint8)
    t0 = time.perf_counter()
    for _ in range(args.n):
        det.detect(img)
    dt = (time.perf_counter() - t0) / args.n
    print(f"{args.model}: {dt*1000:.1f} ms/帧（{1/dt:.1f} fps），输入 {det.input_size}，线程 {args.threads}")
    return 0


# -------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="smartview", description="玉米收获机垄内异物视觉预警系统")
    p.add_argument("--version", action="version", version=f"smartview {__version__}")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd")

    r = sub.add_parser("run", help="真机运行（多线程、HMI）")
    r.add_argument("-c", "--config", required=True)
    r.add_argument("--no-hmi", action="store_true")
    r.add_argument("--log-detections", default=None, help="逐帧检测/轨迹 JSONL 输出")
    r.set_defaults(func=cmd_run)

    rp = sub.add_parser("replay", help="回放（文件 / 合成场景），确定性")
    rp.add_argument("-c", "--config", required=True)
    rp.add_argument("--realtime", action="store_true", help="按时间戳节拍回放")
    rp.add_argument("--hmi", action="store_true", help="同时启动 HMI")
    rp.add_argument("--no-hmi", dest="hmi", action="store_false")
    rp.add_argument("--hold", action="store_true", help="回放结束后保持 HMI 运行")
    rp.add_argument("--max-frames", type=int, default=None)
    rp.add_argument("--log-detections", default=None)
    rp.add_argument("--seed", type=int, default=None)
    rp.add_argument("--duration", type=float, default=None, help="合成场景时长（秒）")
    rp.set_defaults(func=cmd_replay, hmi=False)

    d = sub.add_parser("demo", help="一键演示：合成场景 → 全链路报警（可选 --hmi）")
    d.add_argument("-c", "--config", default=None)
    d.add_argument("--out", default="data/demo")
    d.add_argument("--scenario", default=None, help="前视相机场景（pipe_forward / stone_forward / mixed_forward / empty）")
    d.add_argument("--hmi", action="store_true")
    d.add_argument("--realtime", action="store_true")
    d.add_argument("--seed", type=int, default=None)
    d.add_argument("--duration", type=float, default=None)
    d.set_defaults(func=cmd_demo, max_frames=None, log_detections=None)

    s = sub.add_parser("synth", help="生成合成场景视频 / 标签")
    s.add_argument("--scenario", default="pipe_forward")
    s.add_argument("--role", default=None, choices=["forward", "header"])
    s.add_argument("--out", required=True)
    s.add_argument("--labels", default=None)
    s.add_argument("--width", type=int, default=640)
    s.add_argument("--height", type=int, default=360)
    s.add_argument("--fps", type=float, default=15)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--duration", type=float, default=None)
    s.add_argument("--speed", type=float, default=None)
    s.set_defaults(func=cmd_synth)

    cm = sub.add_parser("calib-mask", help="从行驶视频学习割台/机身自身区域遮罩")
    cm.add_argument("--video", required=True)
    cm.add_argument("--out", required=True, help="输出 PNG 遮罩（白=排除）")
    cm.add_argument("--max-frames", type=int, default=300)
    cm.add_argument("--stride", type=int, default=1)
    cm.add_argument("--margin", type=float, default=0.01, help="安全裕量（画面尺寸比例）")
    cm.set_defaults(func=cmd_calib_mask)

    ex = sub.add_parser("export-events", help="导出事件 CSV")
    ex.add_argument("-c", "--config", required=True)
    ex.add_argument("--out", default="events.csv")
    ex.add_argument("--limit", type=int, default=10000)
    ex.set_defaults(func=cmd_export_events)

    st = sub.add_parser("selftest", help="自检：相机、检测器、报警输出")
    st.add_argument("-c", "--config", required=True)
    st.add_argument("--quick", action="store_true")
    st.set_defaults(func=cmd_selftest)

    b = sub.add_parser("bench", help="ONNX 模型推理基准")
    b.add_argument("--model", required=True)
    b.add_argument("--size", type=int, default=640)
    b.add_argument("--n", type=int, default=30)
    b.add_argument("--threads", type=int, default=2)
    b.set_defaults(func=cmd_bench)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(getattr(args, "verbose", False))
    if not getattr(args, "cmd", None):
        parser.print_help()
        return 0
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
