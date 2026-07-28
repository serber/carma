# Plate detection: YOLO-style ONNX model via open-image-models (built on
# onnxruntime). Detection is plate-agnostic (KZ/RU format handling happens
# in ocr.py), so a generic pretrained plate detector is fine here.
#
# Default model (yolo-v9-t-384-license-plate-end2end) is the same one
# fast-alpr pairs with fast-plate-ocr by default -- both projects are by
# the same author and built to work together. Registered models are
# downloaded once (scripts/fetch_models.py, run at install time) and
# cached under ~/.cache/open-image-models/, so normal offline operation
# never needs network access.
from __future__ import annotations

import logging

import numpy as np
from open_image_models import create_detector

logger = logging.getLogger(__name__)

Box = tuple[int, int, int, int, float]  # x1, y1, x2, y2, confidence


class PlateDetector:
    def __init__(self, model_name: str, confidence_threshold: float) -> None:
        self._detector = create_detector(model_name, conf_thresh=confidence_threshold)
        logger.info(
            "plate detector loaded model=%s confidence_threshold=%s",
            model_name, confidence_threshold,
        )

    def detect(self, frame: np.ndarray) -> list[Box]:
        results = self._detector.predict(frame)
        return [
            (
                result.bounding_box.x1,
                result.bounding_box.y1,
                result.bounding_box.x2,
                result.bounding_box.y2,
                result.confidence,
            )
            for result in results
        ]
