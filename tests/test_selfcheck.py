import numpy as np

from carma.selfcheck import check_camera
from tests.conftest import FakeSource


def test_camera_ok_with_frame():
    source = FakeSource(frames=[None, None, np.zeros((2, 2, 3))])
    assert check_camera(source, attempts=5, delay=0) is True
    assert source.started is True


def test_camera_failed_start():
    source = FakeSource(fail_start=True)
    assert check_camera(source) is False


def test_camera_started_but_no_frame_yet_is_still_ok():
    source = FakeSource(frames=[])
    assert check_camera(source, attempts=3, delay=0) is True
    assert source.started is True
