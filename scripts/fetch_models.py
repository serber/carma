#!/usr/bin/env python3
"""Pre-downloads the ONNX models config.yaml points at, so the device never
needs network access at runtime (see SPEC.md "Offline-first"). Run once
during scripts/install.sh, or manually after changing a model name in
config.yaml. Needs the carma venv (run via .venv/bin/python).
"""
import argparse
import sys

from fast_plate_ocr.inference.hub import AVAILABLE_ONNX_MODELS as OCR_MODELS
from fast_plate_ocr.inference.hub import download_model as download_ocr_model
from open_image_models.detection.core.hub import DETECTION_MODELS
from open_image_models.detection.core.hub import (
    download_model as download_detection_model,
)

from carma.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", default="config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)

    detection_name = config.detection.model_name
    if detection_name not in DETECTION_MODELS:
        print(
            f"detection.model_name={detection_name!r} is a local path, not a "
            f"registered model name -- nothing to pre-download",
            file=sys.stderr,
        )
    else:
        print(f"downloading detector model: {detection_name}")
        path = download_detection_model(detection_name)
        print(f"cached at {path}")

    ocr_name = config.ocr.model_name
    if ocr_name not in OCR_MODELS:
        print(
            f"ocr.model_name={ocr_name!r} is a local path, not a "
            f"registered model name -- nothing to pre-download",
            file=sys.stderr,
        )
    else:
        print(f"downloading OCR model: {ocr_name}")
        model_path, config_path = download_ocr_model(ocr_name)
        print(f"cached at {model_path} and {config_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
