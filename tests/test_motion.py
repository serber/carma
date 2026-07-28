import numpy as np

from carma.pipeline.motion import MotionDetector


def _frame(value: int, shape: tuple[int, int, int] = (10, 10, 3)) -> np.ndarray:
    return np.full(shape, value, dtype=np.uint8)


def test_first_frame_never_reports_motion():
    detector = MotionDetector(threshold=25, min_area=1)
    assert detector.update(_frame(0)) is False


def test_identical_frames_report_no_motion():
    detector = MotionDetector(threshold=25, min_area=1)
    detector.update(_frame(50))
    assert detector.update(_frame(50)) is False


def test_large_change_reports_motion():
    detector = MotionDetector(threshold=10, min_area=1)
    detector.update(_frame(0))
    assert detector.update(_frame(255)) is True


def test_high_min_area_suppresses_motion():
    detector = MotionDetector(threshold=10, min_area=10_000_000)
    detector.update(_frame(0))
    assert detector.update(_frame(255)) is False


def test_roi_restricts_comparison_region():
    frame_a = np.zeros((20, 20, 3), dtype=np.uint8)
    frame_b = frame_a.copy()
    frame_b[15:, 15:] = 255  # change entirely outside the ROI below

    detector = MotionDetector(threshold=10, min_area=1, roi=(0, 0, 8, 8))
    detector.update(frame_a)
    assert detector.update(frame_b) is False


def test_roi_detects_change_inside_region():
    frame_a = np.zeros((20, 20, 3), dtype=np.uint8)
    frame_b = frame_a.copy()
    frame_b[0:8, 0:8] = 255  # change inside the ROI below

    detector = MotionDetector(threshold=10, min_area=1, roi=(0, 0, 8, 8))
    detector.update(frame_a)
    assert detector.update(frame_b) is True
