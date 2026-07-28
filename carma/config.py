# Loads and validates config.yaml (see config.example.yaml).
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import yaml
from fast_plate_ocr.inference.hub import AVAILABLE_ONNX_MODELS as OCR_MODELS
from open_image_models.detection.core.hub import DETECTION_MODELS

VALID_CAMERA_BACKENDS = {"picamera2", "opencv"}
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class ConfigError(ValueError):
    """Config.yaml is missing, malformed, or has an invalid value.

    Raised with a message naming the offending file/section/key so the
    startup self-check can log a clear "config OK" / "config FAILED: ..."
    line instead of a bare traceback.
    """


@dataclasses.dataclass
class CameraConfig:
    backend: str = "picamera2"  # picamera2 (CSI, default) | opencv (USB)
    device: int | str = 0        # opencv backend only: V4L2 index or /dev/videoN
    resolution: tuple[int, int] = (1280, 720)
    framerate: int = 30


@dataclasses.dataclass
class MotionConfig:
    threshold: int = 25
    min_area: int = 500
    roi: tuple[int, int, int, int] | None = None  # [x, y, w, h] pixels


@dataclasses.dataclass
class DetectionConfig:
    # A registered open-image-models plate detector name (auto-downloaded
    # and cached, see scripts/fetch_models.py), or a path to a local ONNX
    # file for a custom-trained model.
    model_name: str = "yolo-v9-t-384-license-plate-end2end"
    confidence_threshold: float = 0.4


@dataclasses.dataclass
class OCRConfig:
    # A registered fast-plate-ocr model name (auto-downloaded and cached,
    # see scripts/fetch_models.py), or a path to a local ONNX file. Default
    # matches what fast-alpr pairs with our detector by default. Its
    # alphabet is plain 0-9A-Z -- no Cyrillic needed, see pipeline/ocr.py.
    model_name: str = "cct-xs-v2-global-model"


@dataclasses.dataclass
class DedupConfig:
    window_seconds: float = 30


@dataclasses.dataclass
class WatchlistConfig:
    enabled: bool = False
    plates: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class DashboardConfig:
    host: str = "0.0.0.0"
    port: int = 8000


@dataclasses.dataclass
class StorageConfig:
    db_path: str = "data/carma.db"
    images_dir: str = "data/images"
    # OCR reads below this confidence aren't stored (still shown live on
    # the MJPEG overlay -- this only trims what gets written). 0 = store
    # everything. Adjustable live from the dashboard without a restart;
    # this is just the value at startup -- see carma/settings.py.
    min_confidence: float = 0.0


@dataclasses.dataclass
class Config:
    camera: CameraConfig
    motion: MotionConfig
    detection: DetectionConfig
    ocr: OCRConfig
    dedup: DedupConfig
    watchlist: WatchlistConfig
    dashboard: DashboardConfig
    storage: StorageConfig
    log_level: str = "INFO"


def _build_section(cls: type, data: Any, section: str, path: Path):
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: '{section}' must be a mapping")

    valid_keys = {f.name for f in dataclasses.fields(cls)}
    unknown = set(data) - valid_keys
    if unknown:
        raise ConfigError(
            f"{path}: unknown key(s) in '{section}': {sorted(unknown)}"
        )

    try:
        return cls(**data)
    except TypeError as e:
        raise ConfigError(f"{path}: invalid '{section}' config: {e}") from e


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")

    with path.open("r") as f:
        try:
            raw = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"{path}: invalid YAML: {e}") from e

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top-level YAML must be a mapping")

    valid_sections = {
        "camera", "motion", "detection", "ocr", "dedup", "watchlist",
        "dashboard", "storage", "log_level",
    }
    unknown = set(raw) - valid_sections
    if unknown:
        raise ConfigError(f"{path}: unknown top-level key(s): {sorted(unknown)}")

    camera = _build_section(CameraConfig, raw.get("camera"), "camera", path)
    motion = _build_section(MotionConfig, raw.get("motion"), "motion", path)
    detection = _build_section(DetectionConfig, raw.get("detection"), "detection", path)
    ocr = _build_section(OCRConfig, raw.get("ocr"), "ocr", path)
    dedup = _build_section(DedupConfig, raw.get("dedup"), "dedup", path)
    watchlist = _build_section(WatchlistConfig, raw.get("watchlist"), "watchlist", path)
    dashboard = _build_section(DashboardConfig, raw.get("dashboard"), "dashboard", path)
    storage = _build_section(StorageConfig, raw.get("storage"), "storage", path)
    log_level = raw.get("log_level", "INFO")

    if camera.backend not in VALID_CAMERA_BACKENDS:
        raise ConfigError(
            f"{path}: camera.backend must be one of "
            f"{sorted(VALID_CAMERA_BACKENDS)}, got {camera.backend!r}"
        )
    if len(camera.resolution) != 2:
        raise ConfigError(f"{path}: camera.resolution must be [width, height]")
    camera.resolution = (int(camera.resolution[0]), int(camera.resolution[1]))
    if camera.framerate <= 0:
        raise ConfigError(f"{path}: camera.framerate must be > 0")

    if motion.roi is not None:
        if len(motion.roi) != 4:
            raise ConfigError(f"{path}: motion.roi must be [x, y, w, h] or null")
        motion.roi = tuple(int(v) for v in motion.roi)
    if motion.threshold < 0:
        raise ConfigError(f"{path}: motion.threshold must be >= 0")
    if motion.min_area < 0:
        raise ConfigError(f"{path}: motion.min_area must be >= 0")

    if not (0.0 <= detection.confidence_threshold <= 1.0):
        raise ConfigError(
            f"{path}: detection.confidence_threshold must be between 0 and 1"
        )
    if detection.model_name not in DETECTION_MODELS and not Path(detection.model_name).is_file():
        raise ConfigError(
            f"{path}: detection.model_name must be one of "
            f"{sorted(DETECTION_MODELS)}, or an existing local .onnx path, "
            f"got {detection.model_name!r}"
        )

    if ocr.model_name not in OCR_MODELS and not Path(ocr.model_name).is_file():
        raise ConfigError(
            f"{path}: ocr.model_name must be one of "
            f"{sorted(OCR_MODELS)}, or an existing local .onnx path, "
            f"got {ocr.model_name!r}"
        )

    if dedup.window_seconds < 0:
        raise ConfigError(f"{path}: dedup.window_seconds must be >= 0")

    if watchlist.enabled and not watchlist.plates:
        raise ConfigError(
            f"{path}: watchlist.enabled is true but watchlist.plates is empty"
        )

    if not (1 <= dashboard.port <= 65535):
        raise ConfigError(f"{path}: dashboard.port must be a valid TCP port")

    if not (0.0 <= storage.min_confidence <= 1.0):
        raise ConfigError(f"{path}: storage.min_confidence must be between 0 and 1")

    log_level = str(log_level).upper()
    if log_level not in VALID_LOG_LEVELS:
        raise ConfigError(
            f"{path}: log_level must be one of {sorted(VALID_LOG_LEVELS)}, "
            f"got {log_level!r}"
        )

    return Config(
        camera=camera,
        motion=motion,
        detection=detection,
        ocr=ocr,
        dedup=dedup,
        watchlist=watchlist,
        dashboard=dashboard,
        storage=storage,
        log_level=log_level,
    )
