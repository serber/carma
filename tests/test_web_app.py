import tempfile

from fastapi.testclient import TestClient

from carma.capture_loop import CaptureLoop
from carma.counters import Counters
from carma.pipeline.dedup import Deduper
from carma.pipeline.motion import MotionDetector
from carma.pipeline.watchlist import Watchlist
from carma.web.app import _mjpeg_generator, create_app
from tests.conftest import FakeHitStore, FakeSource


def _client(camera_ok: bool = True, model_ok: bool = True, hit_store=None) -> TestClient:
    source = FakeSource()
    counters = Counters()
    counters.increment("frames_captured", by=5)
    loop = CaptureLoop(
        source, counters, MotionDetector(threshold=25, min_area=500), None, None, None,
        "unused", Deduper(window_seconds=0), Watchlist(enabled=False, plates=[]),
    )
    self_check = {
        "config": True, "camera": camera_ok, "model": model_ok, "ocr": True, "storage": True,
    }
    images_dir = tempfile.mkdtemp()
    app = create_app(loop, counters, self_check, hit_store, images_dir)
    return TestClient(app)


def test_index_lists_self_check():
    client = _client(camera_ok=False)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "camera: FAILED" in resp.text
    assert "config: OK" in resp.text
    assert "model: OK" in resp.text


def test_index_includes_log_tail_section():
    client = _client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="log"' in resp.text


def test_status_reports_counters_and_self_check():
    client = _client()
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["frames_captured"] == 5
    assert data["self_check"] == {
        "config": True, "camera": True, "model": True, "ocr": True, "storage": True,
    }
    assert "fps" in data
    assert "cpu_temp_celsius" in data


def test_log_endpoint_returns_text():
    client = _client()
    resp = client.get("/api/log")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")


def test_hits_page_with_no_store_shows_empty_state():
    client = _client(hit_store=None)
    resp = client.get("/hits")
    assert resp.status_code == 200
    assert "no hits yet" in resp.text


def test_hits_page_lists_recent_hits():
    hit_store = FakeHitStore()
    hit_store.insert("2026-07-28T12:00:00+00:00", "123ABC02", 0.91, "KZ", False, "f1.jpg", "c1.jpg")
    client = _client(hit_store=hit_store)

    resp = client.get("/hits")
    assert resp.status_code == 200
    assert "123ABC02" in resp.text
    assert "KZ" in resp.text
    assert "/images/c1.jpg" in resp.text
    assert "/images/f1.jpg" in resp.text


def test_hits_page_highlights_watchlist_matches():
    hit_store = FakeHitStore()
    hit_store.insert("2026-07-28T12:00:00+00:00", "123ABC02", 0.91, "KZ", True, "f1.jpg", "c1.jpg")
    client = _client(hit_store=hit_store)

    resp = client.get("/hits")
    assert resp.status_code == 200
    assert "watchlist-match" in resp.text


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
