from abc import ABC, abstractmethod

import numpy as np


class FrameSource(ABC):
    """Abstract camera source. Concrete backends: Picamera2Source (CSI,
    default) and OpenCVSource (USB) — selected in config via camera.backend.
    """

    @abstractmethod
    def start(self) -> None:
        """Open the device and begin producing frames."""

    @abstractmethod
    def stop(self) -> None:
        """Release the device."""

    @abstractmethod
    def read(self) -> np.ndarray | None:
        """Return the latest frame as BGR ndarray, or None if none is
        available yet (used by the startup self-check and dead-camera
        detection: 0 frames read means the camera stage is stuck)."""

    @property
    @abstractmethod
    def fps(self) -> float:
        """Measured capture FPS, surfaced on the dashboard."""
