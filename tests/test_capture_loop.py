import time

import numpy as np

from carma.capture_loop import CaptureLoop
from carma.counters import Counters
from carma.pipeline.dedup import Deduper
from carma.pipeline.motion import MotionDetector
from carma.pipeline.watchlist import Watchlist
from tests.conftest import FakeHitStore, FakePlateDetector, FakePlateReader, FakeSource


def _quiet_motion() -> MotionDetector:
    return MotionDetector(threshold=25, min_area=500)


def _always_motion() -> MotionDetector:
    # threshold=0, min_area=0: any frame after the first baseline reports
    # motion, regardless of actual content -- deterministic for tests.
    return MotionDetector(threshold=0, min_area=0)


def _no_dedup() -> Deduper:
    return Deduper(window_seconds=0)


def _no_watchlist() -> Watchlist:
    return Watchlist(enabled=False, plates=[])


def _wait_until(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        time.sleep(0.01)


def _make_loop(
    source, counters, motion_detector, plate_detector=None, plate_reader=None,
    hit_store=None, images_dir="unused", deduper=None, watchlist=None,
) -> CaptureLoop:
    return CaptureLoop(
        source, counters, motion_detector, plate_detector, plate_reader, hit_store,
        images_dir, deduper or _no_dedup(), watchlist or _no_watchlist(),
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
    assert saved[4] is False  # watchlist_match
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


def test_dedup_suppresses_repeated_plate(tmp_path):
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    source = FakeSource(frames=[frame])
    counters = Counters()
    plate_detector = FakePlateDetector(boxes=[(1, 1, 4, 4, 0.9)])
    plate_reader = FakePlateReader(result=("123ABC02", 0.87, "KZ"))
    hit_store = FakeHitStore()
    images_dir = tmp_path / "images"
    # window_seconds huge: the same plate seen repeatedly is only stored once
    loop = _make_loop(
        source, counters, _always_motion(), plate_detector, plate_reader,
        hit_store, str(images_dir), deduper=Deduper(window_seconds=9999),
    )

    loop.start()
    _wait_until(lambda: counters.snapshot()["ocr_reads"] > 3)
    loop.stop()

    assert counters.snapshot()["ocr_reads"] > 3  # OCR still ran every time
    assert len(hit_store.inserted) == 1  # but only stored once


def test_watchlist_match_flagged_on_insert(tmp_path):
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    source = FakeSource(frames=[frame])
    counters = Counters()
    plate_detector = FakePlateDetector(boxes=[(1, 1, 4, 4, 0.9)])
    plate_reader = FakePlateReader(result=("123ABC02", 0.87, "KZ"))
    hit_store = FakeHitStore()
    images_dir = tmp_path / "images"
    loop = _make_loop(
        source, counters, _always_motion(), plate_detector, plate_reader,
        hit_store, str(images_dir), watchlist=Watchlist(enabled=True, plates=["ABC02"]),
    )

    loop.start()
    _wait_until(lambda: len(hit_store.inserted) > 0)
    loop.stop()

    assert hit_store.inserted[0][4] is True  # watchlist_match


def test_bad_frame_does_not_kill_the_loop():
    class BoomOnceMotion(MotionDetector):
        def __init__(self):
            super().__init__(threshold=0, min_area=0)
            self.calls = 0

        def update(self, frame):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("simulated processing error")
            return super().update(frame)

    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    source = FakeSource(frames=[frame])
    counters = Counters()
    motion = BoomOnceMotion()
    loop = _make_loop(source, counters, motion)

    loop.start()
    _wait_until(lambda: motion.calls > 2)
    loop.stop()

    # the loop kept running (frames_captured kept incrementing) despite the
    # first call raising
    assert counters.snapshot()["frames_captured"] > 2
