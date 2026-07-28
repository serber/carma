# Structured logging setup, called once at startup. Every module logs via
# logging.getLogger(__name__), so output is labelled per pipeline stage
# (carma.capture.picamera2_source, carma.pipeline.motion, carma.web.app, ...)
# and `journalctl -u carma -f -o cat` reads as one line per event, stage
# visible at a glance. Also keeps an in-memory tail of recent log lines for
# the dashboard (get_recent_logs()) -- journalctl needs a shell, the
# dashboard is what's reachable from a phone at mount time.
from __future__ import annotations

import collections
import logging
import sys

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%dT%H:%M:%S%z"
_LOG_BUFFER_SIZE = 200

_log_buffer: collections.deque[str] = collections.deque(maxlen=_LOG_BUFFER_SIZE)


class _RingBufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _log_buffer.append(self.format(record))


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger. journald adds its own timestamp/priority
    when carma runs under systemd (StandardOutput=journal in
    systemd/carma.service); the explicit format here keeps output just as
    readable when running `carma` directly in a terminal.
    """
    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    buffer_handler = _RingBufferHandler()
    buffer_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()
    root.addHandler(stream_handler)
    root.addHandler(buffer_handler)


def get_recent_logs(limit: int = _LOG_BUFFER_SIZE) -> list[str]:
    return list(_log_buffer)[-limit:]
