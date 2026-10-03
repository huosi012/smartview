# 训练与数据工具

本目录不参与 CI，面向模型训练与田间评估。完整方案见 [docs/30-感知算法与数据方案.md](../docs/30-感知算法与数据方案.md)。

| 脚本 | 作用 |
|---|---|
| `classes.yaml` | 类别定义（顺序 = 类别 id），标注最小尺寸 |
| `prepare_dataset.py` | LabelMe / YOLO 标注 → YOLO 数据集，**按序列**划分，统计类别与目标像素高度分布 |
| `copy_paste_aug.py` | 按相机几何把井口钢管 / 石块抠图贴入真实背景，自动生成标签（解决井口样本稀缺） |
| `train.py` | Ultralytics 训练封装（含田间增强参数），训练后自动导出 ONNX |
| `export_onnx.py` | 导出 ONNX + `model.json`（类别 / 输入尺寸 / 输出布局），可做 PyTorch↔ONNX 一致性校验 |
| `export_trt.sh` | 在 Jetson 上用 `trtexec` 构建 FP16 / INT8 引擎 |
| `int8_calibrate.py` | INT8 熵校准（TensorRT ≥ 10，Jetson 上运行） |
| `evaluate_field.py` | 回放 / 田间评估：按距离分桶召回、精度、首次预警距离、预警时间、每小时误报 |

## 快速流程

```bash
# 1. 采集：用车上同款相机、同安装位置录制（smartview run --log-detections 可同时记录推理结果）
# 2. 标注：CVAT / X-AnyLabeling / LabelMe，类别按 classes.yaml
python training/prepare_dataset.py --src data/raw --out datasets/v1
# 3. 合成扩充（可选）
python training/copy_paste_aug.py --backgrounds data/bg --cutouts data/cutouts --out datasets/cp --config configs/jetson_4row.yaml --cam fwd
# 4. 训练 + 导出
python training/train.py --data datasets/v1/data.yaml --model yolov8s.pt --epochs 120
# 5. Jetson 上构建引擎
bash training/export_trt.sh models/smartview.onnx /opt/smartview/models/smartview_fp16.engine fp16
# 6. 评估（合成场景示例）
smartview replay -c configs/replay_synthetic.yaml --no-hmi --log-detections /tmp/dets.jsonl
python training/evaluate_field.py --dets /tmp/dets.jsonl --synthetic pipe_forward --config configs/replay_synthetic.yaml --cam fwd
```

## 许可证

Ultralytics YOLOv5/v8/v11 为 **AGPL-3.0**：商用产品需购买 Ultralytics Enterprise License，或采用 Apache-2.0 架构
（YOLOX、PP-YOLOE+ / RT-DETR（PaddleDetection）、DAMO-YOLO、D-FINE）。smartview 的推理后端只依赖 ONNX 输出布局
`(1, 4+nc, N)` 或 `(1, N, 4+nc)`（以及 v5 风格 `(1, N, 5+nc)`），与训练框架无关。
