from carma.counters import Counters


def test_starts_at_zero():
    counters = Counters()
    snap = counters.snapshot()
    assert snap["frames_captured"] == 0
    assert snap["motion_events"] == 0
    assert snap["detections"] == 0
    assert snap["ocr_reads"] == 0


def test_increment():
    counters = Counters()
    counters.increment("frames_captured")
    counters.increment("frames_captured")
    counters.increment("detections", by=3)
    snap = counters.snapshot()
    assert snap["frames_captured"] == 2
    assert snap["detections"] == 3


def test_snapshot_includes_uptime():
    counters = Counters()
    snap = counters.snapshot()
    assert snap["uptime_seconds"] >= 0
