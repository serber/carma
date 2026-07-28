# Background thread that continuously pulls frames from a FrameSource, runs
# them through motion -> detection -> ocr -> dedup -> storage, and keeps
# the latest frame JPEG-encoded (with any detection boxes drawn) ready for
# the dashboard's MJPEG stream.
from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime

import cv2
import numpy as np

from carma.capture.base import FrameSource
from carma.counters import Counters
from carma.pipeline.dedup import Deduper
from carma.pipeline.detect import Box, PlateDetector
from carma.pipeline.motion import MotionDetector
from carma.pipeline.ocr import PlateReader
from carma.pipeline.watchlist import Watchlist
from carma.storage.db import HitStore
from carma.storage.images import save_hit_images

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
        plate_reader: PlateReader | None,
        hit_store: HitStore | None,
        images_dir: str,
        deduper: Deduper,
        watchlist: Watchlist,
    ) -> None:
        self._source = source
        self._counters = counters
        self._motion_detector = motion_detector
        self._plate_detector = plate_detector
        self._plate_reader = plate_reader
        self._hit_store = hit_store
        self._images_dir = images_dir
        self._deduper = deduper
        self._watchlist = watchlist
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
            try:
                frame = self._source.read()
            except Exception:
                # A flaky driver raising instead of returning None must not
                # silently kill the capture thread -- that's exactly the
                # "turned it on, nothing happens, can't tell why" failure
                # mode the dashboard exists to prevent.
                logger.exception("error reading frame; continuing")
                self._stop_event.wait(0.05)
                continue

            if frame is None:
                self._stop_event.wait(0.05)
                continue
            self._counters.increment("frames_captured")
            try:
                detections = self._process(frame)
                self._encode(frame, detections)
            except Exception:
                logger.exception("error processing frame; continuing")

    def _process(self, frame: np.ndarray) -> list[tuple[Box, str | None]]:
        if not self._motion_detector.update(frame):
            return []
        self._counters.increment("motion_events")

        if self._plate_detector is None:
            return []
        boxes = self._plate_detector.detect(frame)
        if boxes:
            self._counters.increment("detections", by=len(boxes))

        return [(box, self._read_and_store(frame, box)) for box in boxes]

    def _read_and_store(self, frame: np.ndarray, box: Box) -> str | None:
        if self._plate_reader is None:
            return None

        crop = _crop(frame, box, frame.shape[1], frame.shape[0])
        result = self._plate_reader.read(crop)
        if result is None:
            return None
        plate, confidence, plate_format = result
        self._counters.increment("ocr_reads")

        # Dedup only gates storage -- the live overlay should still show
        # every read, even a repeat of a plate that's sitting in frame.
        if self._hit_store is not None and self._deduper.should_record(plate):
            watchlist_match = self._watchlist.matches(plate)
            frame_filename, crop_filename = save_hit_images(frame, crop, self._images_dir)
            timestamp = datetime.now(UTC).isoformat()
            self._hit_store.insert(
                timestamp, plate, confidence, plate_format, watchlist_match,
                frame_filename, crop_filename,
            )
        return plate

    def _encode(self, frame: np.ndarray, detections: list[tuple[Box, str | None]]) -> None:
        if detections:
            frame = frame.copy()
            for (x1, y1, x2, y2, _confidence), plate in detections:
                cv2.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR, 2)
                if plate:
                    _draw_label(frame, x1, y1, plate)

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ok:
            logger.warning("failed to JPEG-encode frame")
            return
        with self._frame_lock:
            self._latest_jpeg = buf.tobytes()


def _draw_label(frame: np.ndarray, x: int, y: int, text: str) -> None:
    """Draws a filled label (plate text on a green background, same as the
    box) anchored above (x, y) -- the detection box's top-left corner --
    or below it if there's no room above."""
    font, scale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
    (text_w, text_h), baseline = cv2.getTextSize(text, font, scale, thickness)
    pad = 4
    label_h = text_h + baseline + 2 * pad
    label_y1 = y - label_h if y - label_h >= 0 else y
    label_y2 = label_y1 + label_h
    cv2.rectangle(frame, (x, label_y1), (x + text_w + 2 * pad, label_y2), BOX_COLOR, cv2.FILLED)
    cv2.putText(
        frame, text, (x + pad, label_y2 - pad - baseline), font, scale, (0, 0, 0),
        thickness, cv2.LINE_AA,
    )


def _crop(frame: np.ndarray, box: Box, frame_width: int, frame_height: int) -> np.ndarray:
    x1, y1, x2, y2, _confidence = box
    x1 = max(0, min(x1, frame_width))
    y1 = max(0, min(y1, frame_height))
    x2 = max(0, min(x2, frame_width))
    y2 = max(0, min(y2, frame_height))
    return frame[y1:y2, x1:x2]
