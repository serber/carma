# Main loop: wires capture -> motion -> detect -> ocr -> dedup -> storage,
# and starts the dashboard. Entry point used by carma/__main__.py.
import logging
import sys
from pathlib import Path

import uvicorn

from carma.capture.factory import create_source
from carma.capture_loop import CaptureLoop
from carma.config import ConfigError, load_config
from carma.counters import Counters
from carma.logging_setup import configure_logging
from carma.pipeline.dedup import Deduper
from carma.pipeline.motion import MotionDetector
from carma.pipeline.watchlist import Watchlist
from carma.selfcheck import check_camera, check_model, check_ocr, check_storage
from carma.settings import RuntimeSettings
from carma.web.app import create_app

logger = logging.getLogger(__name__)


def run(config_path: str) -> int:
    try:
        config = load_config(config_path)
    except ConfigError as e:
        # Logging isn't configured yet without a parsed config's log_level,
        # so this failure has to be visible on stderr by default.
        print(f"carma: config FAILED: {e}", file=sys.stderr)
        return 1

    configure_logging(config.log_level)
    logger.info("config OK path=%s", config_path)

    source = create_source(config.camera)
    camera_ok = check_camera(source)

    plate_detector = check_model(
        config.detection.model_name, config.detection.confidence_threshold
    )
    plate_reader = check_ocr(config.ocr.model_name)
    hit_store = check_storage(config.storage.db_path)

    motion_detector = MotionDetector(
        config.motion.threshold, config.motion.min_area, config.motion.roi
    )
    deduper = Deduper(config.dedup.window_seconds)
    watchlist = Watchlist(config.watchlist.enabled, config.watchlist.plates)
    settings_path = Path(config.storage.db_path).parent / "runtime_settings.json"
    settings = RuntimeSettings(
        config.storage.min_confidence, config.camera.color_mode, persist_path=str(settings_path)
    )

    counters = Counters()
    capture_loop = CaptureLoop(
        source,
        counters,
        motion_detector,
        plate_detector,
        plate_reader,
        hit_store,
        config.storage.images_dir,
        deduper,
        watchlist,
        settings,
    )
    if camera_ok:
        capture_loop.start()
    else:
        logger.warning(
            "starting dashboard without a live capture loop — "
            "fix the camera and restart carma"
        )

    self_check = {
        "config": True,
        "camera": camera_ok,
        "model": plate_detector is not None,
        "ocr": plate_reader is not None,
        "storage": hit_store is not None,
    }
    app = create_app(
        capture_loop, counters, self_check, hit_store, config.storage.images_dir, settings
    )

    logger.info(
        "dashboard starting host=%s port=%s",
        config.dashboard.host, config.dashboard.port,
    )
    try:
        uvicorn.run(
            app,
            host=config.dashboard.host,
            port=config.dashboard.port,
            log_level=config.log_level.lower(),
        )
    finally:
        capture_loop.stop()
        if hit_store is not None:
            hit_store.close()

    return 0
