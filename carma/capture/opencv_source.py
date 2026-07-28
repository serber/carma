# USB camera backend via OpenCV / V4L2 (camera.backend: opencv). Also handy
# for developing/testing off-Pi with a laptop webcam before deploying.
import logging

import cv2
import numpy as np

from carma.capture.base import FrameRateTracker, FrameSource

logger = logging.getLogger(__name__)


class OpenCVSource(FrameSource):
    def __init__(self, device: int | str, resolution: tuple[int, int], framerate: int) -> None:
        self._device = device
        self._resolution = resolution
        self._framerate = framerate
        self._cap: cv2.VideoCapture | None = None
        self._rate = FrameRateTracker()

    def start(self) -> None:
        cap = cv2.VideoCapture(self._device)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._resolution[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._resolution[1])
        cap.set(cv2.CAP_PROP_FPS, self._framerate)

        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"could not open camera device {self._device!r}")

        self._cap = cap
        logger.info(
            "opencv camera started device=%s resolution=%s framerate=%s",
            self._device, self._resolution, self._framerate,
        )

    def stop(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def read(self) -> np.ndarray | None:
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        if not ok:
            return None
        self._rate.tick()
        return frame

    @property
    def fps(self) -> float:
        return self._rate.fps
