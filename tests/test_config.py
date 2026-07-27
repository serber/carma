from pathlib import Path

import pytest

from carma.config import ConfigError, load_config

EXAMPLE = Path(__file__).parent.parent / "config.example.yaml"


def test_loads_example_config():
    config = load_config(EXAMPLE)
    assert config.camera.backend == "picamera2"
    assert config.camera.resolution == (1280, 720)
    assert config.motion.roi is None
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
