import pytest

from carma.capture.factory import create_source
from carma.capture.opencv_source import OpenCVSource
from carma.capture.picamera2_source import Picamera2Source
from carma.config import CameraConfig


def test_picamera2_backend():
    config = CameraConfig(backend="picamera2", resolution=(640, 480), framerate=30)
    source = create_source(config)
    assert isinstance(source, Picamera2Source)


def test_opencv_backend():
    config = CameraConfig(backend="opencv", device=0, resolution=(640, 480), framerate=30)
    source = create_source(config)
    assert isinstance(source, OpenCVSource)


def test_unknown_backend():
    config = CameraConfig(backend="bogus")
    with pytest.raises(ValueError, match="unknown camera backend"):
        create_source(config)
