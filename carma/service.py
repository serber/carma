# Main loop: wires capture -> motion -> detect -> ocr -> dedup -> storage,
# and starts the dashboard. Entry point used by carma/__main__.py.
#
# TODO(stage 1): load config, set up logging, run the startup self-check
# (camera OK / model loaded OK / config OK), start the capture source and
# the FastAPI/uvicorn dashboard with the MJPEG stream + counters.
# TODO(stage 2-4): wire in motion, detect, ocr, dedup, storage per build order.


def run(config_path: str) -> int:
    raise NotImplementedError("stage 1: wire the skeleton main loop")
