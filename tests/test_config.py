import pytest
from pydantic import ValidationError

from smartview.config import CameraConfig, SmartViewConfig


def test_defaults_are_sane():
    cfg = SmartViewConfig.from_dict({})
    assert cfg.machine.n_rows == 4
    assert cfg.risk.hold_s == {"L1": 1.0, "L2": 2.0, "L3": 3.0}
    assert cfg.detector.backend == "classical"
    assert cfg.alarm.purge.enabled is False


def test_load_replay_config(replay_config_path):
    cfg = SmartViewConfig.load(replay_config_path)
    ids = [c.id for c in cfg.cameras]
    assert ids == ["fwd", "hdr_l"]
    hdr = cfg.camera("hdr_l")
    assert hdr.role == "header"
    assert len(hdr.exclude_polygons) == 1 and len(hdr.exclude_polygons[0]) == 6
    assert cfg.camera("fwd").detect_crop == (0.05, 0.25, 0.95, 1.0)
    # 相对路径按配置文件目录解析
    assert cfg.resolve("data/events.db").endswith("configs/data/events.db")
    assert cfg.resolve("/abs/x.db") == "/abs/x.db"


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        SmartViewConfig.from_dict({"machine": {"n_rows": 4, "typo_field": 1}})


def test_duplicate_camera_ids_rejected():
    cams = [
        {"id": "a", "role": "forward"},
        {"id": "a", "role": "header"},
    ]
    with pytest.raises(ValidationError):
        SmartViewConfig.from_dict({"cameras": cams})


def test_polygon_must_be_normalized():
    with pytest.raises(ValidationError):
        CameraConfig(id="x", role="header", exclude_polygons=[[[0, 0], [2, 0], [1, 1]]])
    with pytest.raises(ValidationError):
        CameraConfig(id="x", role="header", roi_polygon=[[0, 0], [1, 0]])


def test_detect_crop_validation():
    with pytest.raises(ValidationError):
        CameraConfig(id="x", role="forward", detect_crop=(0.5, 0.0, 0.4, 1.0))


def test_purge_requires_channels():
    with pytest.raises(ValidationError):
        SmartViewConfig.from_dict({"alarm": {"purge": {"enabled": True}}})
    with pytest.raises(ValidationError):
        SmartViewConfig.from_dict(
            {
                "alarm": {"purge": {"enabled": True, "channels": {"a": 1}}},
                "cameras": [{"id": "c", "role": "header", "purge_channel": "missing"}],
            }
        )


def test_yaml_roundtrip(replay_config_path):
    cfg = SmartViewConfig.load(replay_config_path)
    text = cfg.to_yaml()
    import yaml

    cfg2 = SmartViewConfig.from_dict(yaml.safe_load(text))
    assert cfg2.model_dump() == cfg.model_dump()
