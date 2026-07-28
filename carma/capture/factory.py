# Builds the configured FrameSource. Backend modules are imported lazily
# here so that, e.g., picamera2's on-Pi-only import doesn't get pulled in
# when running with camera.backend: opencv.
from carma.capture.base import FrameSource
from carma.config import CameraConfig


def create_source(config: CameraConfig) -> FrameSource:
    if config.backend == "picamera2":
        from carma.capture.picamera2_source import Picamera2Source
        return Picamera2Source(config.resolution, config.framerate)

    if config.backend == "opencv":
        from carma.capture.opencv_source import OpenCVSource
        return OpenCVSource(config.device, config.resolution, config.framerate)

    # config.load_config() already restricts backend to a known value;
    # this only guards direct construction of a CameraConfig, e.g. in tests.
    raise ValueError(f"unknown camera backend: {config.backend!r}")
