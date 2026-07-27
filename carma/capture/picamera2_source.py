# CSI camera backend via picamera2. Default backend (see config.example.yaml,
# camera.backend: picamera2) — this device has a ribbon-cable CSI camera.
# picamera2 is only importable on Raspberry Pi OS (system package
# python3-picamera2); the import is deferred to start() so the module can
# still be imported (and the class constructed) on other platforms.
import logging

import numpy as np

from carma.capture.base import FrameRateTracker, FrameSource

logger = logging.getLogger(__name__)


class Picamera2Source(FrameSource):
    def __init__(self, resolution: tuple[int, int], framerate: int) -> None:
        self._resolution = resolution
        self._framerate = framerate
        self._picam2 = None
        self._rate = FrameRateTracker()

    def start(self) -> None:
        from picamera2 import Picamera2

        self._picam2 = Picamera2()
        config = self._picam2.create_video_configuration(
            main={"size": self._resolution, "format": "BGR888"},
            controls={"FrameRate": self._framerate},
        )
        self._picam2.configure(config)
        self._picam2.start()
        logger.info(
            "picamera2 started resolution=%s framerate=%s",
            self._resolution, self._framerate,
        )

    def stop(self) -> None:
        if self._picam2 is not None:
            self._picam2.stop()
            self._picam2.close()
            self._picam2 = None

    def read(self) -> np.ndarray | None:
        if self._picam2 is None:
            return None
        # BGR888 configuration hands back an ndarray already in BGR order,
        # ready for cv2/onnxruntime use downstream.
        frame = self._picam2.capture_array()
        self._rate.tick()
        return frame

    @property
    def fps(self) -> float:
        return self._rate.fps
