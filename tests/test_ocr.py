from unittest.mock import MagicMock

import numpy as np
import pytest

from carma.pipeline.ocr import PlateReader, classify_plate, normalize_plate


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("А123ВС77", "A123BC77"),  # Cyrillic homoglyphs -> latin
        ("123 abc 02", "123ABC02"),  # lowercase + spaces
        ("123ABC02", "123ABC02"),  # already normalized
    ],
)
def test_normalize_plate(raw, expected):
    assert normalize_plate(raw) == expected


@pytest.mark.parametrize(
    ("plate", "expected"),
    [
        ("123ABC02", "KZ"),
        ("777XYZ99", "KZ"),
        ("A123BC77", "RU"),
        ("A123BC777", "RU"),  # 3-digit region
        ("", "unknown"),
        ("HELLO", "unknown"),
        ("123ABC1", "unknown"),  # too short for KZ
    ],
)
def test_classify_plate(plate, expected):
    assert classify_plate(plate) == expected


class _FakePrediction:
    def __init__(self, plate: str, char_probs) -> None:
        self.plate = plate
        self.char_probs = char_probs


class _FakeConfig:
    image_color_mode = "rgb"


def _fake_recognizer(plate: str, char_probs) -> MagicMock:
    recognizer = MagicMock()
    recognizer.config = _FakeConfig()
    recognizer.run_one.return_value = _FakePrediction(plate, char_probs)
    return recognizer


def test_read_returns_plate_confidence_and_format(monkeypatch):
    char_probs = np.array([0.9, 0.8, 0.95, 0.7, 0.6, 0.99, 0.88, 0.77, 0.1, 0.1])
    recognizer = _fake_recognizer("123ABC02", char_probs)
    monkeypatch.setattr(
        "carma.pipeline.ocr.LicensePlateRecognizer", lambda hub_ocr_model: recognizer
    )

    reader = PlateReader("cct-xs-v2-global-model")
    plate, confidence, plate_format = reader.read(np.zeros((10, 10, 3), dtype=np.uint8))

    assert plate == "123ABC02"
    assert plate_format == "KZ"
    # mean of the first 8 (len("123ABC02")) probs only, not the padding tail
    assert confidence == pytest.approx(np.mean(char_probs[:8]))


def test_read_returns_none_for_empty_crop(monkeypatch):
    recognizer = _fake_recognizer("", np.array([]))
    monkeypatch.setattr(
        "carma.pipeline.ocr.LicensePlateRecognizer", lambda hub_ocr_model: recognizer
    )

    reader = PlateReader("cct-xs-v2-global-model")
    result = reader.read(np.zeros((0, 0, 3), dtype=np.uint8))

    assert result is None
    recognizer.run_one.assert_not_called()
