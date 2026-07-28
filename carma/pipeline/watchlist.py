# Flags plates matching a user-supplied full or partial string
# (config: watchlist.enabled / watchlist.plates).
from __future__ import annotations

from carma.pipeline.ocr import normalize_plate


class Watchlist:
    def __init__(self, enabled: bool, plates: list[str]) -> None:
        self._enabled = enabled
        self._entries = [normalize_plate(p) for p in plates]

    def matches(self, plate: str) -> bool:
        if not self._enabled or not self._entries:
            return False
        normalized = normalize_plate(plate)
        return any(entry in normalized for entry in self._entries)
