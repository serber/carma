import time

import numpy as np

from carma.capture_loop import CaptureLoop
from carma.counters import Counters
from tests.conftest import FakeSource


def test_captures_frames_and_encodes_jpeg():
    source = FakeSource(frames=[np.zeros((8, 8, 3), dtype=np.uint8)])
    counters = Counters()
    loop = CaptureLoop(source, counters)

    loop.start()
    deadline = time.monotonic() + 2
    while loop.latest_jpeg() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    loop.stop()

    assert loop.latest_jpeg() is not None
    assert counters.snapshot()["frames_captured"] > 0
    assert source.stopped is True


def test_none_frames_do_not_increment_counter():
    source = FakeSource(frames=[None])
    counters = Counters()
    loop = CaptureLoop(source, counters)

    loop.start()
    time.sleep(0.1)
    loop.stop()

    assert counters.snapshot()["frames_captured"] == 0
    assert loop.latest_jpeg() is None
