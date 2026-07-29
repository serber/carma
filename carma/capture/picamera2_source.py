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
            # picamera2/libcamera name these after the DRM/register format,
            # not the in-memory byte order, so they're the opposite of what
            # you'd guess: "RGB888" is what actually hands back BGR-ordered
            # bytes (cv2's native order); "BGR888" would give RGB-ordered
            # bytes and show every colour inverted-ish (blues rendering as
            # yellows, etc.) once treated as BGR downstream.
            main={"size": self._resolution, "format": "RGB888"},
            controls={"FrameRate": self._framerate},
        )
        self._picam2.configure(config)
        self._picam2.start()
        self._enable_continuous_autofocus()
        logger.info(
            "picamera2 started resolution=%s framerate=%s",
            self._resolution, self._framerate,
        )

    def _enable_continuous_autofocus(self) -> None:
        # Fixed-focus modules don't expose AfMode at all; autofocus-capable
        # ones (e.g. Camera Module 3, Arducam IMX519) default to AfMode
        # "Manual" with whatever lens position it last had -- continuous AF
        # is what a curb-side camera needs, since subject distance varies
        # car to car and libcamera won't engage it on its own.
        if "AfMode" not in self._picam2.camera_controls:
            return
        from libcamera import controls

        self._picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        logger.info("continuous autofocus enabled")

    def stop(self) -> None:
        if self._picam2 is not None:
            self._picam2.stop()
            self._picam2.close()
            self._picam2 = None

    def read(self) -> np.ndarray | None:
        if self._picam2 is None:
            return None
        # RGB888 configuration (see start()) hands back an ndarray already
        # in BGR order, ready for cv2/onnxruntime use downstream.
        frame = self._picam2.capture_array()
        self._rate.tick()
        return frame

    @property
    def fps(self) -> float:
        return self._rate.fps
