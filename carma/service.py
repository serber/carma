# Main loop: wires capture -> motion -> detect -> ocr -> dedup -> storage,
# and starts the dashboard. Entry point used by carma/__main__.py.
#
# TODO(stage 3-4): wire in ocr, dedup, storage per build order.
import logging
import sys

import uvicorn

from carma.capture.factory import create_source
from carma.capture_loop import CaptureLoop
from carma.config import ConfigError, load_config
from carma.counters import Counters
from carma.logging_setup import configure_logging
from carma.pipeline.motion import MotionDetector
from carma.selfcheck import check_camera, check_model
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

    motion_detector = MotionDetector(
        config.motion.threshold, config.motion.min_area, config.motion.roi
    )

    counters = Counters()
    capture_loop = CaptureLoop(source, counters, motion_detector, plate_detector)
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
    }
    app = create_app(capture_loop, counters, self_check)

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

    return 0
