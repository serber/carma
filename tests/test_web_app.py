from fastapi.testclient import TestClient

from carma.capture_loop import CaptureLoop
from carma.counters import Counters
from carma.web.app import _mjpeg_generator, create_app
from tests.conftest import FakeSource


def _client(camera_ok: bool = True) -> TestClient:
    source = FakeSource()
    counters = Counters()
    counters.increment("frames_captured", by=5)
    loop = CaptureLoop(source, counters)
    app = create_app(loop, counters, {"config": True, "camera": camera_ok})
    return TestClient(app)


def test_index_lists_self_check():
    client = _client(camera_ok=False)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "camera: FAILED" in resp.text
    assert "config: OK" in resp.text


def test_status_reports_counters_and_self_check():
    client = _client()
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["frames_captured"] == 5
    assert data["self_check"] == {"config": True, "camera": True}
    assert "fps" in data


def test_mjpeg_generator_falls_back_to_placeholder_when_no_frame():
    class NoFrameLoop:
        def latest_jpeg(self):
            return None

    placeholder = b"placeholder-bytes"
    gen = _mjpeg_generator(NoFrameLoop(), placeholder)
    chunk = next(gen)
    assert b"--frame" in chunk
    assert b"Content-Type: image/jpeg" in chunk
    assert placeholder in chunk


def test_mjpeg_generator_prefers_latest_frame():
    class FixedFrameLoop:
        def latest_jpeg(self):
            return b"real-jpeg-bytes"

    gen = _mjpeg_generator(FixedFrameLoop(), b"placeholder")
    chunk = next(gen)
    assert b"real-jpeg-bytes" in chunk
