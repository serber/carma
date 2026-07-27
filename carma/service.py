# Main loop: wires capture -> motion -> detect -> ocr -> dedup -> storage,
# and starts the dashboard. Entry point used by carma/__main__.py.
#
# TODO(stage 1): startup self-check (camera OK / model loaded OK / config
# OK), start the capture source and the FastAPI/uvicorn dashboard with the
# MJPEG stream + counters.
# TODO(stage 2-4): wire in motion, detect, ocr, dedup, storage per build order.
import logging
import sys

from carma.config import ConfigError, load_config
from carma.logging_setup import configure_logging

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

    raise NotImplementedError("stage 1: capture source + startup self-check + dashboard")
