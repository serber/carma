# Background thread that continuously pulls frames from a FrameSource,
# increments counters.frames_captured, and keeps the latest frame
# JPEG-encoded and ready for the dashboard's MJPEG stream.
from __future__ import annotations

import logging
import threading

import cv2
import numpy as np

from carma.capture.base import FrameSource
from carma.counters import Counters

logger = logging.getLogger(__name__)

JPEG_QUALITY = 80


class CaptureLoop:
    def __init__(self, source: FrameSource, counters: Counters) -> None:
        self._source = source
        self._counters = counters
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._frame_lock = threading.Lock()
        self._latest_jpeg: bytes | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name="carma-capture-loop", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._source.stop()

    def latest_jpeg(self) -> bytes | None:
        with self._frame_lock:
            return self._latest_jpeg

    @property
    def fps(self) -> float:
        return self._source.fps

    def _run(self) -> None:
        while not self._stop_event.is_set():
            frame = self._source.read()
            if frame is None:
                self._stop_event.wait(0.05)
                continue
            self._counters.increment("frames_captured")
            self._encode(frame)

    def _encode(self, frame: np.ndarray) -> None:
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ok:
            logger.warning("failed to JPEG-encode frame")
            return
        with self._frame_lock:
            self._latest_jpeg = buf.tobytes()
