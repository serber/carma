# CSI camera backend via picamera2. Default backend (see config.example.yaml,
# camera.backend: picamera2) — this device has a ribbon-cable CSI camera.
#
# TODO(stage 1, atomic step 5): wrap picamera2.Picamera2(), configure
# resolution/framerate from config, implement start/stop/read/fps.

import numpy as np

from carma.capture.base import FrameSource


class Picamera2Source(FrameSource):
    def __init__(self, resolution: tuple[int, int], framerate: int) -> None:
        self._resolution = resolution
        self._framerate = framerate

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def read(self) -> np.ndarray | None:
        raise NotImplementedError

    @property
    def fps(self) -> float:
        raise NotImplementedError
