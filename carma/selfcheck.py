# Startup self-check: verifies each subsystem and logs a clear OK/FAILED
# line, so init failures are visible instead of silent.
# Config is checked by config.load_config() raising ConfigError before this
# module is ever reached (see service.run()).
# TODO(stage 2): add a "model loaded OK" check once the detector model is
# wired in (pipeline/detect.py).
from __future__ import annotations

import logging
import time

from carma.capture.base import FrameSource

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
