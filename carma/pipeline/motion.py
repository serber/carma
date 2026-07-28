# Frame differencing so inference doesn't run on every captured frame.
from __future__ import annotations

import cv2
import numpy as np


class MotionDetector:
    """Stateful frame-differencing motion trigger.

    threshold: per-pixel intensity delta to count as "changed".
    min_area: minimum count of changed pixels before it's reported as
      motion.
    roi: optional (x, y, w, h) pixel region to restrict comparison to
      (None = full frame). Detection itself still runs on the full frame
      once triggered -- this only narrows where motion is looked for.
    """

    def __init__(
        self,
        threshold: int,
        min_area: int,
        roi: tuple[int, int, int, int] | None = None,
    ) -> None:
        self._threshold = threshold
        self._min_area = min_area
        self._roi = roi
        self._prev_gray: np.ndarray | None = None

    def update(self, frame: np.ndarray) -> bool:
        gray = self._prepare(frame)

        if self._prev_gray is None or self._prev_gray.shape != gray.shape:
            # First frame, or the ROI/resolution changed mid-stream: there's
            # no baseline to diff against yet.
            self._prev_gray = gray
            return False

        diff = cv2.absdiff(self._prev_gray, gray)
        self._prev_gray = gray
        changed_pixels = int(np.count_nonzero(diff > self._threshold))
        return changed_pixels >= self._min_area

    def _prepare(self, frame: np.ndarray) -> np.ndarray:
        if self._roi is not None:
            x, y, w, h = self._roi
            frame = frame[y:y + h, x:x + w]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(gray, (21, 21), 0)
