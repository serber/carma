from unittest.mock import MagicMock

import numpy as np

from carma.pipeline.detect import PlateDetector


class _FakeBoundingBox:
    def __init__(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2


class _FakeDetectionResult:
    def __init__(self, box: _FakeBoundingBox, confidence: float) -> None:
        self.bounding_box = box
        self.confidence = confidence


def test_detect_converts_results_to_box_tuples(monkeypatch):
    fake_backend = MagicMock()
    fake_backend.predict.return_value = [
        _FakeDetectionResult(_FakeBoundingBox(1, 2, 3, 4), 0.87),
    ]
    monkeypatch.setattr(
        "carma.pipeline.detect.create_detector", lambda *a, **k: fake_backend
    )

    detector = PlateDetector("yolo-v9-t-384-license-plate-end2end", 0.4)
    boxes = detector.detect(np.zeros((10, 10, 3), dtype=np.uint8))

    assert boxes == [(1, 2, 3, 4, 0.87)]
    fake_backend.predict.assert_called_once()


def test_detect_returns_empty_list_when_no_detections(monkeypatch):
    fake_backend = MagicMock()
    fake_backend.predict.return_value = []
    monkeypatch.setattr(
        "carma.pipeline.detect.create_detector", lambda *a, **k: fake_backend
    )

    detector = PlateDetector("yolo-v9-t-384-license-plate-end2end", 0.4)
    assert detector.detect(np.zeros((10, 10, 3), dtype=np.uint8)) == []


def test_model_name_and_confidence_threshold_passed_through(monkeypatch):
    captured = {}

    def fake_create_detector(model_name, conf_thresh=None):
        captured["model_name"] = model_name
        captured["conf_thresh"] = conf_thresh
        return MagicMock(predict=MagicMock(return_value=[]))

    monkeypatch.setattr("carma.pipeline.detect.create_detector", fake_create_detector)

    PlateDetector("yolo-v9-t-256-license-plate-end2end", 0.6)

    assert captured == {
        "model_name": "yolo-v9-t-256-license-plate-end2end",
        "conf_thresh": 0.6,
    }
