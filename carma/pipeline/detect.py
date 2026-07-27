# Plate detection: YOLO-style ONNX model via onnxruntime. Detection is
# plate-agnostic (KZ/RU format handling happens in ocr.py), so a generic
# pretrained plate detector is fine here.
#
# TODO(stage 2): load model from config.detection.model_path, run inference,
# return bounding boxes above config.detection.confidence_threshold (feeds
# the "detections" counter).

import numpy as np


def detect_plates(frame: np.ndarray, confidence_threshold: float) -> list[tuple[int, int, int, int, float]]:
    """Returns a list of (x, y, w, h, confidence) boxes."""
    raise NotImplementedError
