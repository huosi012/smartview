import numpy as np
import pytest

onnx = pytest.importorskip("onnx")
pytest.importorskip("onnxruntime")

from onnx import TensorProto, helper, numpy_helper  # noqa: E402

from smartview.detect.yolo_onnx import YoloOnnxDetector  # noqa: E402


def _tiny_model(path, layout: str, nc: int = 6, n: int = 100):
    """输入 images(1,3,640,640)，输出为常量张量（植入一个框：cx=320,cy=200,w=50,h=100,类别 1）。"""
    attrs = nc + 4
    arr = np.zeros((attrs, n), dtype=np.float32)
    arr[0, 3], arr[1, 3], arr[2, 3], arr[3, 3] = 320, 200, 50, 100
    arr[4 + 1, 3] = 0.88
    # 第二个重叠框分数更低，应被 NMS 抑制
    arr[0, 4], arr[1, 4], arr[2, 4], arr[3, 4] = 322, 202, 50, 100
    arr[4 + 1, 4] = 0.6
    out = arr[None] if layout == "cn" else np.ascontiguousarray(arr[None].transpose(0, 2, 1))
    const = numpy_helper.from_array(out, name="const_out")
    # 让输出依赖输入（Shape 不改变数值）：output = const + 0 * ReduceMean(images)
    x_in = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, 640, 640])
    y_out = helper.make_tensor_value_info("output0", TensorProto.FLOAT, list(out.shape))
    zero = numpy_helper.from_array(np.array(0.0, dtype=np.float32), name="zero")
    nodes = [
        helper.make_node("ReduceMean", ["images"], ["m"], keepdims=0),
        helper.make_node("Mul", ["m", "zero"], ["mz"]),
        helper.make_node("Add", ["const_out", "mz"], ["output0"]),
    ]
    graph = helper.make_graph(nodes, "tiny_yolo", [x_in], [y_out], initializer=[const, zero])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    onnx.save(model, str(path))
    return path


@pytest.mark.parametrize("layout", ["cn", "nc"])
def test_onnx_detector_end_to_end(tmp_path, layout):
    p = _tiny_model(tmp_path / f"tiny_{layout}.onnx", layout)
    det = YoloOnnxDetector(str(p), classes=["stone", "well_pipe", "stake", "concrete_pile", "person", "animal"], conf_thr=0.3, num_threads=1)
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    dets = det.detect(img)
    assert len(dets) == 1
    d = dets[0]
    assert d.cls_name == "well_pipe" and abs(d.score - 0.88) < 1e-5
    # letterbox 上下各填充 140 px → 原图 y 需减去 140
    assert np.allclose(d.bbox, [295, 10, 345, 110], atol=1.0)
