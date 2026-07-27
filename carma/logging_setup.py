# Structured logging setup, called once at startup. Every module logs via
# logging.getLogger(__name__), so output is labelled per pipeline stage
# (carma.capture.picamera2_source, carma.pipeline.motion, carma.web.app, ...)
# and `journalctl -u carma -f -o cat` reads as one line per event, stage
# visible at a glance.
from __future__ import annotations

import logging
import sys

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%dT%H:%M:%S%z"


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger. journald adds its own timestamp/priority
    when carma runs under systemd (StandardOutput=journal in
    systemd/carma.service); the explicit format here keeps output just as
    readable when running `carma` directly in a terminal.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))

    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()
    root.addHandler(handler)
