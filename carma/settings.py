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


class RuntimeSettings:
    def __init__(self, min_confidence: float, persist_path: str | None = None) -> None:
        self._lock = threading.Lock()
        self._persist_path = Path(persist_path) if persist_path else None
        self._min_confidence = self._load_persisted(default=min_confidence)

    def _load_persisted(self, default: float) -> float:
        if self._persist_path is None or not self._persist_path.is_file():
            return default
        try:
            value = float(json.loads(self._persist_path.read_text())["min_confidence"])
        except (OSError, ValueError, KeyError, TypeError) as e:
            logger.warning(
                "failed to load persisted settings from %s (%s); using config default",
                self._persist_path, e,
            )
            return default
        if not (0.0 <= value <= 1.0):
            logger.warning(
                "persisted min_confidence=%r out of range; using config default", value
            )
            return default
        logger.info("loaded persisted min_confidence=%.2f from %s", value, self._persist_path)
        return value

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

    def _persist(self) -> None:
        if self._persist_path is None:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._persist_path.write_text(json.dumps({"min_confidence": self._min_confidence}))
        except OSError:
            logger.exception("failed to persist settings to %s", self._persist_path)
