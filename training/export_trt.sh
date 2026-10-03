#!/usr/bin/env bash
# 在目标 Jetson 上把 ONNX 构建为 TensorRT 引擎（引擎与 GPU / TensorRT 版本绑定，不能跨机复制）。
# 用法：bash training/export_trt.sh models/smartview.onnx models/smartview_fp16.engine [fp16|int8] [calib_dir]
set -euo pipefail
ONNX="${1:?onnx 路径}"
ENGINE="${2:?engine 输出路径}"
MODE="${3:-fp16}"
CALIB_DIR="${4:-}"
TRTEXEC="${TRTEXEC:-/usr/src/tensorrt/bin/trtexec}"
[ -x "$TRTEXEC" ] || { echo "找不到 trtexec（$TRTEXEC），请确认 JetPack 已安装 TensorRT"; exit 1; }

COMMON=(--onnx="$ONNX" --saveEngine="$ENGINE" --workspace=2048 --useCudaGraph --warmUp=500 --iterations=200)
case "$MODE" in
  fp16)
    "$TRTEXEC" "${COMMON[@]}" --fp16 ;;
  int8)
    # INT8 需要校准：用 ~500 张有代表性的田间图（不同光照/粉尘）生成校准缓存。
    # trtexec 自带的随机校准不可用于生产；推荐用 Python 熵校准器（见 docs/30 第 6 节）生成 calib.cache 后：
    CACHE="${ENGINE%.engine}.calib.cache"
    [ -f "$CACHE" ] || { echo "缺少校准缓存 $CACHE（先运行 python training/int8_calibrate.py --images $CALIB_DIR --onnx $ONNX --out $CACHE）"; exit 1; }
    "$TRTEXEC" "${COMMON[@]}" --int8 --fp16 --calib="$CACHE" ;;
  *) echo "MODE 必须是 fp16 或 int8"; exit 1 ;;
esac
echo "引擎已生成：$ENGINE"
echo "把 engine 路径填入配置 detector.model_path，并把 model.json 复制到同目录（类别 / 输入尺寸）"
cp -f "${ONNX%.onnx}.json" "${ENGINE%.engine}.json" 2>/dev/null || true
