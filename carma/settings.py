# Runtime-adjustable settings -- unlike Config (loaded once from
# config.yaml at startup), these can change while the service is running,
# e.g. via the dashboard. Read from the capture loop thread, written from
# HTTP request handler threads, so access is lock-guarded.
#
# Optionally persisted to a small JSON file (separate from config.yaml, so
# editing config.yaml's comments/formatting is never at risk from a
# programmatic rewrite): once a value has been set via the dashboard, the
# persisted file wins over config.yaml's default on every future startup,
# until changed again from the dashboard.
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

VALID_COLOR_MODES = {"color", "grayscale"}


class RuntimeSettings:
    def __init__(
        self, min_confidence: float, color_mode: str = "color", persist_path: str | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._persist_path = Path(persist_path) if persist_path else None
        persisted = self._load_persisted()
        self._min_confidence = persisted.get("min_confidence", min_confidence)
        self._color_mode = persisted.get("color_mode", color_mode)

    def _load_persisted(self) -> dict:
        if self._persist_path is None or not self._persist_path.is_file():
            return {}
        try:
            raw = json.loads(self._persist_path.read_text())
        except (OSError, ValueError) as e:
            logger.warning(
                "failed to load persisted settings from %s (%s); using config defaults",
                self._persist_path, e,
            )
            return {}

        result: dict = {}
        if "min_confidence" in raw:
            try:
                value = float(raw["min_confidence"])
            except (ValueError, TypeError):
                logger.warning("persisted min_confidence=%r invalid; using config default", raw["min_confidence"])
            else:
                if 0.0 <= value <= 1.0:
                    result["min_confidence"] = value
                else:
                    logger.warning("persisted min_confidence=%r out of range; using config default", value)
        if "color_mode" in raw:
            value = raw["color_mode"]
            if value in VALID_COLOR_MODES:
                result["color_mode"] = value
            else:
                logger.warning("persisted color_mode=%r invalid; using config default", value)

        if result:
            logger.info("loaded persisted settings %s from %s", result, self._persist_path)
        return result

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
        self._persist()

    @property
    def color_mode(self) -> str:
        with self._lock:
            return self._color_mode

    @color_mode.setter
    def color_mode(self, value: str) -> None:
        if value not in VALID_COLOR_MODES:
            raise ValueError(f"color_mode must be one of {sorted(VALID_COLOR_MODES)}")
        with self._lock:
            self._color_mode = value
        self._persist()

    def _persist(self) -> None:
        if self._persist_path is None:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = {"min_confidence": self._min_confidence, "color_mode": self._color_mode}
            self._persist_path.write_text(json.dumps(data))
        except OSError:
            logger.exception("failed to persist settings to %s", self._persist_path)
