# Don't record the same plate repeatedly within a configurable time window.
# Not thread-safe -- used only from the single capture-loop thread.
from __future__ import annotations

import time


class Deduper:
    def __init__(self, window_seconds: float) -> None:
        self._window_seconds = window_seconds
        self._last_recorded: dict[str, float] = {}

    def should_record(self, plate: str, now: float | None = None) -> bool:
        """Returns True (and marks the plate as recorded now) if this plate
        hasn't been recorded within the dedup window; False if it's a
        repeat that should be skipped."""
        now = time.monotonic() if now is None else now
        self._evict_stale(now)

        last = self._last_recorded.get(plate)
        if last is not None and now - last < self._window_seconds:
            return False

        self._last_recorded[plate] = now
        return True

    def _evict_stale(self, now: float) -> None:
        stale = [
            plate for plate, seen_at in self._last_recorded.items()
            if now - seen_at >= self._window_seconds
        ]
        for plate in stale:
            del self._last_recorded[plate]
