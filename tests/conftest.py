import numpy as np
import pytest

from carma.capture.base import FrameSource
from carma.storage.db import Hit


class FakeSource(FrameSource):
    """In-memory FrameSource for tests: no real hardware, no cv2/picamera2."""

    def __init__(self, frames: list[np.ndarray | None] | None = None, fail_start: bool = False) -> None:
        self._frames = frames if frames is not None else [np.zeros((4, 4, 3), dtype=np.uint8)]
        self._index = 0
        self._fail_start = fail_start
        self.started = False
        self.stopped = False

    def start(self) -> None:
        if self._fail_start:
            raise RuntimeError("no such device")
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def read(self) -> np.ndarray | None:
        if not self._frames:
            return None
        frame = self._frames[self._index % len(self._frames)]
        self._index += 1
        return frame

    @property
    def fps(self) -> float:
        return 0.0


@pytest.fixture
def fake_source() -> FakeSource:
    return FakeSource()


class FakePlateDetector:
    """Duck-typed stand-in for PlateDetector: only needs .detect(frame)."""

    def __init__(self, boxes: list[tuple[int, int, int, int, float]] | None = None) -> None:
        self._boxes = boxes if boxes is not None else []
        self.calls = 0

    def detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int, float]]:
        self.calls += 1
        return list(self._boxes)


class FakePlateReader:
    """Duck-typed stand-in for PlateReader: only needs .read(crop)."""

    def __init__(self, result: tuple[str, float, str] | None = ("123ABC02", 0.9, "KZ")) -> None:
        self._result = result
        self.calls = 0

    def read(self, crop: np.ndarray) -> tuple[str, float, str] | None:
        self.calls += 1
        return self._result


class FakeHitStore:
    """Duck-typed stand-in for HitStore: records insert() calls in memory."""

    def __init__(self) -> None:
        self.inserted: list[tuple] = []

    def insert(
        self,
        timestamp: str,
        plate: str,
        confidence: float,
        format_: str,
        watchlist_match: bool,
        frame_filename: str,
        crop_filename: str,
    ) -> int:
        self.inserted.append(
            (timestamp, plate, confidence, format_, watchlist_match, frame_filename, crop_filename)
        )
        return len(self.inserted)

    def recent(self, limit: int = 50) -> list[Hit]:
        rows = list(reversed(self.inserted))[:limit]
        return [
            Hit(
                id=i, timestamp=t, plate=p, confidence=c, format=f,
                watchlist_match=w, frame_filename=ff, crop_filename=cf,
            )
            for i, (t, p, c, f, w, ff, cf) in enumerate(rows)
        ]

    def count(self) -> int:
        return len(self.inserted)

    def clear(self) -> None:
        self.inserted = []
