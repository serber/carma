import numpy as np
import pytest

from carma.capture.base import FrameSource


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

    def detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int, float]]:
        return list(self._boxes)
