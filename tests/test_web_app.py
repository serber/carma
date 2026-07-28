import tempfile

from fastapi.testclient import TestClient

from carma.capture_loop import CaptureLoop
from carma.counters import Counters
from carma.pipeline.dedup import Deduper
from carma.pipeline.motion import MotionDetector
from carma.pipeline.watchlist import Watchlist
from carma.settings import RuntimeSettings
from carma.web.app import _mjpeg_generator, create_app
from tests.conftest import FakeHitStore, FakeSource


def _client(
    camera_ok: bool = True, model_ok: bool = True, hit_store=None, settings=None,
) -> TestClient:
    source = FakeSource()
    counters = Counters()
    counters.increment("frames_captured", by=5)
    settings = settings or RuntimeSettings(min_confidence=0.0)
    loop = CaptureLoop(
        source, counters, MotionDetector(threshold=25, min_area=500), None, None, None,
        "unused", Deduper(window_seconds=0), Watchlist(enabled=False, plates=[]), settings,
    )
    self_check = {
        "config": True, "camera": camera_ok, "model": model_ok, "ocr": True, "storage": True,
    }
    images_dir = tempfile.mkdtemp()
    app = create_app(loop, counters, self_check, hit_store, images_dir, settings)
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


def test_index_includes_disk_usage_meter():
    client = _client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="disk-fill"' in resp.text
    assert 'id="disk-label"' in resp.text


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


def test_status_reports_real_disk_usage_for_existing_images_dir():
    # _client() uses a real tempdir for images_dir, so disk usage should
    # resolve to actual numbers, not the "path doesn't exist yet" None case
    client = _client()
    resp = client.get("/api/status")
    data = resp.json()
    assert isinstance(data["disk_free_bytes"], int)
    assert isinstance(data["disk_total_bytes"], int)
    assert data["disk_total_bytes"] > 0


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


def test_index_shows_current_min_confidence():
    client = _client(settings=RuntimeSettings(min_confidence=0.65))
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'value="0.65"' in resp.text
    assert "0.65" in resp.text


def test_get_settings_returns_current_value():
    client = _client(settings=RuntimeSettings(min_confidence=0.3))
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    assert resp.json() == {"min_confidence": 0.3}


def test_post_settings_updates_value():
    settings = RuntimeSettings(min_confidence=0.0)
    client = _client(settings=settings)

    resp = client.post("/api/settings", json={"min_confidence": 0.75})

    assert resp.status_code == 200
    assert resp.json() == {"min_confidence": 0.75}
    assert settings.min_confidence == 0.75


def test_post_settings_rejects_out_of_range_value():
    client = _client(settings=RuntimeSettings(min_confidence=0.2))

    resp = client.post("/api/settings", json={"min_confidence": 1.5})

    assert resp.status_code == 422


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
