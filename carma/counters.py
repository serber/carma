# Per-stage counters surfaced on the dashboard. Where the pipeline goes
# silent tells you which stage is stuck: dead camera -> 0 frames, threshold
# too high -> frames but 0 motion, bad angle/focus -> motion but 0
# detections, unreadable plates -> 0 OCR reads.
from __future__ import annotations

import dataclasses
import threading
import time


@dataclasses.dataclass
class _Counts:
    frames_captured: int = 0
    motion_events: int = 0
    detections: int = 0
    ocr_reads: int = 0


class Counters:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts = _Counts()
        self._started_at = time.monotonic()

    def increment(self, field: str, by: int = 1) -> None:
        with self._lock:
            setattr(self._counts, field, getattr(self._counts, field) + by)

    def snapshot(self) -> dict[str, int | float]:
        with self._lock:
            data = dataclasses.asdict(self._counts)
        data["uptime_seconds"] = round(time.monotonic() - self._started_at, 1)
        return data
