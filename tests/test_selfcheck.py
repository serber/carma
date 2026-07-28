import numpy as np

from carma.selfcheck import check_camera, check_model
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


def test_model_ok(monkeypatch):
    monkeypatch.setattr("carma.selfcheck.PlateDetector", lambda name, thresh: object())
    assert check_model("some-model", 0.4) is not None


def test_model_failed_to_load(monkeypatch):
    def boom(name, thresh):
        raise RuntimeError("no internet and model not cached")

    monkeypatch.setattr("carma.selfcheck.PlateDetector", boom)
    assert check_model("some-model", 0.4) is None
