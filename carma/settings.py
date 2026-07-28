# Runtime-adjustable settings -- unlike Config (loaded once from
# config.yaml at startup), these can change while the service is running,
# e.g. via the dashboard. Read from the capture loop thread, written from
# HTTP request handler threads, so access is lock-guarded.
from __future__ import annotations

import threading


class RuntimeSettings:
    def __init__(self, min_confidence: float) -> None:
        self._lock = threading.Lock()
        self._min_confidence = min_confidence

    @property
    def min_confidence(self) -> float:
        with self._lock:
            return self._min_confidence

    @min_confidence.setter
    def min_confidence(self, value: float) -> None:
        if not (0.0 <= value <= 1.0):
            raise ValueError("min_confidence must be between 0 and 1")
        with self._lock:
            self._min_confidence = value
