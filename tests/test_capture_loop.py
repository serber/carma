import time

import numpy as np

from carma.capture_loop import CaptureLoop
from carma.counters import Counters
from carma.pipeline.motion import MotionDetector
from tests.conftest import FakePlateDetector, FakeSource


def _quiet_motion() -> MotionDetector:
    return MotionDetector(threshold=25, min_area=500)


def _always_motion() -> MotionDetector:
    # threshold=0, min_area=0: any frame after the first baseline reports
    # motion, regardless of actual content -- deterministic for tests.
    return MotionDetector(threshold=0, min_area=0)


def _wait_until(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        time.sleep(0.01)


def test_captures_frames_and_encodes_jpeg():
    source = FakeSource(frames=[np.zeros((8, 8, 3), dtype=np.uint8)])
    counters = Counters()
    loop = CaptureLoop(source, counters, _quiet_motion(), None)

    loop.start()
    _wait_until(lambda: loop.latest_jpeg() is not None)
    loop.stop()

    assert loop.latest_jpeg() is not None
    assert counters.snapshot()["frames_captured"] > 0
    assert source.stopped is True


def test_none_frames_do_not_increment_counter():
    source = FakeSource(frames=[None])
    counters = Counters()
    loop = CaptureLoop(source, counters, _quiet_motion(), None)

    loop.start()
    time.sleep(0.1)
    loop.stop()

    assert counters.snapshot()["frames_captured"] == 0
    assert loop.latest_jpeg() is None


def test_motion_and_detection_counters_increment():
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    source = FakeSource(frames=[frame])
    counters = Counters()
    plate_detector = FakePlateDetector(boxes=[(1, 1, 4, 4, 0.9)])
    loop = CaptureLoop(source, counters, _always_motion(), plate_detector)

    loop.start()
    _wait_until(lambda: counters.snapshot()["detections"] > 0)
    loop.stop()

    snap = counters.snapshot()
    assert snap["motion_events"] > 0
    assert snap["detections"] > 0


def test_no_plate_detector_means_no_detections():
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    source = FakeSource(frames=[frame])
    counters = Counters()
    loop = CaptureLoop(source, counters, _always_motion(), None)

    loop.start()
    _wait_until(lambda: counters.snapshot()["motion_events"] > 0)
    loop.stop()

    snap = counters.snapshot()
    assert snap["motion_events"] > 0
    assert snap["detections"] == 0


def test_quiet_motion_detector_keeps_detections_at_zero():
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    source = FakeSource(frames=[frame])
    counters = Counters()
    plate_detector = FakePlateDetector(boxes=[(1, 1, 4, 4, 0.9)])
    loop = CaptureLoop(source, counters, _quiet_motion(), plate_detector)

    loop.start()
    _wait_until(lambda: counters.snapshot()["frames_captured"] > 3)
    loop.stop()

    snap = counters.snapshot()
    assert snap["motion_events"] == 0
    assert snap["detections"] == 0
