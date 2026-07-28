#!/usr/bin/env python3
"""Pre-downloads the ONNX models config.yaml points at, so the device never
needs network access at runtime (see SPEC.md "Offline-first"). Run once
during scripts/install.sh, or manually after changing a model name in
config.yaml. Needs the carma venv (run via .venv/bin/python).
"""
import argparse
import sys

from open_image_models.detection.core.hub import DETECTION_MODELS, download_model

from carma.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", default="config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    model_name = config.detection.model_name

    if model_name not in DETECTION_MODELS:
        print(
            f"detection.model_name={model_name!r} is a local path, not a "
            f"registered model name -- nothing to pre-download",
            file=sys.stderr,
        )
        return 0

    print(f"downloading detector model: {model_name}")
    path = download_model(model_name)
    print(f"cached at {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
