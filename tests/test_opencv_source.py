from unittest.mock import MagicMock

import numpy as np
import pytest

from carma.capture.opencv_source import OpenCVSource


def test_start_raises_when_device_not_opened(monkeypatch):
    fake_cap = MagicMock()
    fake_cap.isOpened.return_value = False
    monkeypatch.setattr("cv2.VideoCapture", lambda device: fake_cap)

    source = OpenCVSource(device=99, resolution=(640, 480), framerate=30)
    with pytest.raises(RuntimeError, match="could not open camera device"):
        source.start()
    fake_cap.release.assert_called_once()


def test_read_returns_frame_when_opened(monkeypatch):
    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    fake_cap = MagicMock()
    fake_cap.isOpened.return_value = True
    fake_cap.read.return_value = (True, frame)
    monkeypatch.setattr("cv2.VideoCapture", lambda device: fake_cap)

    source = OpenCVSource(device=0, resolution=(640, 480), framerate=30)
    source.start()
    result = source.read()

    assert result is frame
    assert source.fps == 0.0  # single read: not enough samples for a rate yet


def test_read_returns_none_on_failed_grab(monkeypatch):
    fake_cap = MagicMock()
    fake_cap.isOpened.return_value = True
    fake_cap.read.return_value = (False, None)
    monkeypatch.setattr("cv2.VideoCapture", lambda device: fake_cap)

    source = OpenCVSource(device=0, resolution=(640, 480), framerate=30)
    source.start()
    assert source.read() is None


def test_stop_releases_capture(monkeypatch):
    fake_cap = MagicMock()
    fake_cap.isOpened.return_value = True
    monkeypatch.setattr("cv2.VideoCapture", lambda device: fake_cap)

    source = OpenCVSource(device=0, resolution=(640, 480), framerate=30)
    source.start()
    source.stop()
    fake_cap.release.assert_called_once()


def test_stop_before_start_is_a_no_op():
    source = OpenCVSource(device=0, resolution=(640, 480), framerate=30)
    source.stop()  # must not raise
