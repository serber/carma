import threading
import time
from abc import ABC, abstractmethod

import numpy as np


class FrameRateTracker:
    """Measures FPS from a rolling window of read() timestamps. Shared by
    the concrete FrameSource backends so each one just calls tick() from
    read() and exposes fps via this object's fps property."""

    def __init__(self, window_seconds: float = 5.0) -> None:
        self._window_seconds = window_seconds
        self._times: list[float] = []
        self._lock = threading.Lock()

    def tick(self) -> None:
        with self._lock:
            now = time.monotonic()
            self._times.append(now)
            cutoff = now - self._window_seconds
            self._times = [t for t in self._times if t >= cutoff]

    @property
    def fps(self) -> float:
        with self._lock:
            if len(self._times) < 2:
                return 0.0
            span = self._times[-1] - self._times[0]
            return (len(self._times) - 1) / span if span > 0 else 0.0


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
