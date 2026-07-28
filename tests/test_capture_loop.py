import time

import numpy as np

from carma.capture_loop import CaptureLoop
from carma.counters import Counters
from carma.pipeline.motion import MotionDetector
from tests.conftest import FakeHitStore, FakePlateDetector, FakePlateReader, FakeSource


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


def _make_loop(
    source, counters, motion_detector, plate_detector=None, plate_reader=None,
    hit_store=None, images_dir="unused",
) -> CaptureLoop:
    return CaptureLoop(
        source, counters, motion_detector, plate_detector, plate_reader, hit_store, images_dir
    )


def test_captures_frames_and_encodes_jpeg():
    source = FakeSource(frames=[np.zeros((8, 8, 3), dtype=np.uint8)])
    counters = Counters()
    loop = _make_loop(source, counters, _quiet_motion())

    loop.start()
    _wait_until(lambda: loop.latest_jpeg() is not None)
    loop.stop()

    assert loop.latest_jpeg() is not None
    assert counters.snapshot()["frames_captured"] > 0
    assert source.stopped is True


def test_none_frames_do_not_increment_counter():
    source = FakeSource(frames=[None])
    counters = Counters()
    loop = _make_loop(source, counters, _quiet_motion())

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
    loop = _make_loop(source, counters, _always_motion(), plate_detector)

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
    loop = _make_loop(source, counters, _always_motion())

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
    loop = _make_loop(source, counters, _quiet_motion(), plate_detector)

    loop.start()
    _wait_until(lambda: counters.snapshot()["frames_captured"] > 3)
    loop.stop()

    snap = counters.snapshot()
    assert snap["motion_events"] == 0
    assert snap["detections"] == 0


def test_ocr_and_storage_wired_on_detection(tmp_path):
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    source = FakeSource(frames=[frame])
    counters = Counters()
    plate_detector = FakePlateDetector(boxes=[(1, 1, 4, 4, 0.9)])
    plate_reader = FakePlateReader(result=("123ABC02", 0.87, "KZ"))
    hit_store = FakeHitStore()
    images_dir = tmp_path / "images"
    loop = _make_loop(
        source, counters, _always_motion(), plate_detector, plate_reader,
        hit_store, str(images_dir),
    )

    loop.start()
    _wait_until(lambda: counters.snapshot()["ocr_reads"] > 0)
    loop.stop()

    assert counters.snapshot()["ocr_reads"] > 0
    assert plate_reader.calls > 0
    assert len(hit_store.inserted) > 0
    saved = hit_store.inserted[0]
    assert saved[1] == "123ABC02"
    assert saved[3] == "KZ"
    assert list(images_dir.glob("*_frame.jpg"))
    assert list(images_dir.glob("*_crop.jpg"))


def test_no_ocr_reads_without_plate_reader():
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    source = FakeSource(frames=[frame])
    counters = Counters()
    plate_detector = FakePlateDetector(boxes=[(1, 1, 4, 4, 0.9)])
    loop = _make_loop(source, counters, _always_motion(), plate_detector)

    loop.start()
    _wait_until(lambda: counters.snapshot()["detections"] > 0)
    loop.stop()

    assert counters.snapshot()["ocr_reads"] == 0


def test_no_storage_writes_without_hit_store(tmp_path):
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    source = FakeSource(frames=[frame])
    counters = Counters()
    plate_detector = FakePlateDetector(boxes=[(1, 1, 4, 4, 0.9)])
    plate_reader = FakePlateReader(result=("123ABC02", 0.87, "KZ"))
    images_dir = tmp_path / "images"
    loop = _make_loop(
        source, counters, _always_motion(), plate_detector, plate_reader,
        None, str(images_dir),
    )

    loop.start()
    _wait_until(lambda: counters.snapshot()["ocr_reads"] > 0)
    loop.stop()

    assert counters.snapshot()["ocr_reads"] > 0
    assert not images_dir.exists() or not list(images_dir.glob("*"))
