# Startup self-check: verifies each subsystem and logs a clear OK/FAILED
# line, so init failures are visible instead of silent.
# Config is checked by config.load_config() raising ConfigError before this
# module is ever reached (see service.run()).
from __future__ import annotations

import logging
import time

from carma.capture.base import FrameSource
from carma.pipeline.detect import PlateDetector
from carma.pipeline.ocr import PlateReader
from carma.storage.db import HitStore

logger = logging.getLogger(__name__)


def check_camera(source: FrameSource, attempts: int = 10, delay: float = 0.1) -> bool:
    """Starts the camera and waits briefly for a first frame. Returns False
    only if the device fails to open at all — a slow-to-warm-up camera that
    opens fine but hasn't produced a frame yet still counts as OK, since
    the capture loop keeps reading afterward and the frames_captured
    counter reflects the real, ongoing state on the dashboard.
    """
    try:
        source.start()
    except Exception:
        logger.exception("camera FAILED to start")
        return False

    for _ in range(attempts):
        frame = source.read()
        if frame is not None:
            logger.info("camera OK frame_shape=%s", frame.shape)
            return True
        time.sleep(delay)

    logger.warning(
        "camera started but produced no frame within %.1fs; "
        "the capture loop will keep retrying — check aim/cabling",
        attempts * delay,
    )
    return True


def check_model(model_name: str, confidence_threshold: float) -> PlateDetector | None:
    """Loads the plate detector. A registered model that isn't cached yet
    needs network access once (see scripts/fetch_models.py, run at install
    time); if that hasn't happened, this fails clearly here instead of the
    pipeline silently never producing detections. Returns None on failure
    so the capture loop can keep running motion-only (detections counter
    stays at 0 -- diagnostic, same pattern as a dead camera).
    """
    try:
        detector = PlateDetector(model_name, confidence_threshold)
    except Exception:
        logger.exception("model FAILED to load")
        return None

    logger.info("model OK name=%s", model_name)
    return detector


def check_ocr(model_name: str) -> PlateReader | None:
    """Loads the OCR model. Same offline-caching and non-fatal-failure
    pattern as check_model() -- see scripts/fetch_models.py."""
    try:
        reader = PlateReader(model_name)
    except Exception:
        logger.exception("ocr FAILED to load")
        return None

    logger.info("ocr OK name=%s", model_name)
    return reader


def check_storage(db_path: str) -> HitStore | None:
    """Opens (creating if needed) the SQLite hit store."""
    try:
        store = HitStore(db_path)
    except Exception:
        logger.exception("storage FAILED to open")
        return None

    logger.info("storage OK path=%s", db_path)
    return store
