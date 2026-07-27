# USB camera backend via OpenCV / V4L2 (camera.backend: opencv). Also handy
# for developing/testing off-Pi with a laptop webcam before deploying.
#
# TODO(stage 1, atomic step 6): wrap cv2.VideoCapture(device), configure
# resolution/framerate from config, implement start/stop/read/fps.

import numpy as np

from carma.capture.base import FrameSource


class OpenCVSource(FrameSource):
    def __init__(self, device: int | str, resolution: tuple[int, int], framerate: int) -> None:
        self._device = device
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
