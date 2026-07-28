import sys
import types
from unittest.mock import MagicMock

from carma.capture.picamera2_source import Picamera2Source


def _install_fake_picamera2(monkeypatch, camera_controls: dict) -> MagicMock:
    mock_instance = MagicMock()
    mock_instance.camera_controls = camera_controls
    mock_class = MagicMock(return_value=mock_instance)

    fake_picamera2_module = types.ModuleType("picamera2")
    fake_picamera2_module.Picamera2 = mock_class
    monkeypatch.setitem(sys.modules, "picamera2", fake_picamera2_module)

    fake_controls = types.SimpleNamespace(
        AfModeEnum=types.SimpleNamespace(Continuous="continuous")
    )
    fake_libcamera_module = types.ModuleType("libcamera")
    fake_libcamera_module.controls = fake_controls
    monkeypatch.setitem(sys.modules, "libcamera", fake_libcamera_module)

    return mock_instance


def test_enables_continuous_autofocus_when_supported(monkeypatch):
    mock_instance = _install_fake_picamera2(monkeypatch, camera_controls={"AfMode": (0, 2, 0)})

    source = Picamera2Source(resolution=(640, 480), framerate=30)
    source.start()

    mock_instance.set_controls.assert_called_once_with({"AfMode": "continuous"})


def test_skips_autofocus_when_not_supported(monkeypatch):
    # Fixed-focus modules don't expose AfMode at all.
    mock_instance = _install_fake_picamera2(monkeypatch, camera_controls={})

    source = Picamera2Source(resolution=(640, 480), framerate=30)
    source.start()

    mock_instance.set_controls.assert_not_called()


def test_start_configures_and_starts_camera(monkeypatch):
    mock_instance = _install_fake_picamera2(monkeypatch, camera_controls={})

    source = Picamera2Source(resolution=(1280, 720), framerate=25)
    source.start()

    mock_instance.create_video_configuration.assert_called_once_with(
        main={"size": (1280, 720), "format": "BGR888"},
        controls={"FrameRate": 25},
    )
    mock_instance.configure.assert_called_once()
    mock_instance.start.assert_called_once()
