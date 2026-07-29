from pathlib import Path

import pytest

from carma.config import ConfigError, load_config

EXAMPLE = Path(__file__).parent.parent / "config.example.yaml"


def test_loads_example_config():
    config = load_config(EXAMPLE)
    assert config.camera.backend == "picamera2"
    assert config.camera.resolution == (1280, 720)
    assert config.camera.color_mode == "color"
    assert config.detection.min_interval_ms == 0
    assert config.motion.roi is None
    assert config.detection.model_name == "yolo-v9-t-384-license-plate-end2end"
    assert config.ocr.model_name == "cct-xs-v2-global-model"
    assert config.dashboard.port == 8000
    assert config.log_level == "INFO"


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "does-not-exist.yaml")


def test_unknown_top_level_key(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("bogus_section: {}\n")
    with pytest.raises(ConfigError, match="unknown top-level key"):
        load_config(path)


def test_invalid_camera_backend(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("camera:\n  backend: gopro\n")
    with pytest.raises(ConfigError, match="camera.backend"):
        load_config(path)


def test_negative_detection_min_interval_ms(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("detection:\n  min_interval_ms: -1\n")
    with pytest.raises(ConfigError, match="detection.min_interval_ms"):
        load_config(path)


def test_invalid_camera_color_mode(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("camera:\n  color_mode: sepia\n")
    with pytest.raises(ConfigError, match="camera.color_mode"):
        load_config(path)


def test_watchlist_enabled_without_plates(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("watchlist:\n  enabled: true\n  plates: []\n")
    with pytest.raises(ConfigError, match="watchlist"):
        load_config(path)


def test_defaults_when_sections_omitted(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("log_level: debug\n")
    config = load_config(path)
    assert config.log_level == "DEBUG"
    assert config.storage.db_path == "data/carma.db"


def test_invalid_detection_model_name(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("detection:\n  model_name: not-a-real-model\n")
    with pytest.raises(ConfigError, match="detection.model_name"):
        load_config(path)


def test_detection_model_name_accepts_local_onnx_path(tmp_path):
    model_file = tmp_path / "custom_detector.onnx"
    model_file.write_bytes(b"not a real onnx file, just needs to exist")
    path = tmp_path / "config.yaml"
    path.write_text(f"detection:\n  model_name: {model_file}\n")

    config = load_config(path)
    assert config.detection.model_name == str(model_file)


def test_invalid_ocr_model_name(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("ocr:\n  model_name: not-a-real-model\n")
    with pytest.raises(ConfigError, match="ocr.model_name"):
        load_config(path)


def test_ocr_model_name_accepts_local_onnx_path(tmp_path):
    model_file = tmp_path / "custom_ocr.onnx"
    model_file.write_bytes(b"not a real onnx file, just needs to exist")
    path = tmp_path / "config.yaml"
    path.write_text(f"ocr:\n  model_name: {model_file}\n")

    config = load_config(path)
    assert config.ocr.model_name == str(model_file)


def test_storage_min_confidence_default_is_zero():
    config = load_config(EXAMPLE)
    assert config.storage.min_confidence == 0.0


def test_invalid_storage_min_confidence(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("storage:\n  min_confidence: 1.5\n")
    with pytest.raises(ConfigError, match="storage.min_confidence"):
        load_config(path)
