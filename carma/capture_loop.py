# Background thread that continuously pulls frames from a FrameSource, runs
# them through motion -> detection, and keeps the latest frame
# JPEG-encoded (with any detection boxes drawn) ready for the dashboard's
# MJPEG stream.
from __future__ import annotations

import logging
import threading

import cv2
import numpy as np

from carma.capture.base import FrameSource
from carma.counters import Counters
from carma.pipeline.detect import Box, PlateDetector
from carma.pipeline.motion import MotionDetector

logger = logging.getLogger(__name__)

JPEG_QUALITY = 80
BOX_COLOR = (0, 255, 0)


class CaptureLoop:
    def __init__(
        self,
        source: FrameSource,
        counters: Counters,
        motion_detector: MotionDetector,
        plate_detector: PlateDetector | None,
    ) -> None:
        self._source = source
        self._counters = counters
        self._motion_detector = motion_detector
        self._plate_detector = plate_detector
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
            boxes = self._process(frame)
            self._encode(frame, boxes)

    def _process(self, frame: np.ndarray) -> list[Box]:
        if not self._motion_detector.update(frame):
            return []
        self._counters.increment("motion_events")

        if self._plate_detector is None:
            return []
        boxes = self._plate_detector.detect(frame)
        if boxes:
            self._counters.increment("detections", by=len(boxes))
        return boxes

    def _encode(self, frame: np.ndarray, boxes: list[Box]) -> None:
        if boxes:
            frame = frame.copy()
            for x1, y1, x2, y2, _confidence in boxes:
                cv2.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR, 2)

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ok:
            logger.warning("failed to JPEG-encode frame")
            return
        with self._frame_lock:
            self._latest_jpeg = buf.tobytes()
