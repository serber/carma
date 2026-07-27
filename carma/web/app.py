# FastAPI dashboard: MJPEG live preview, CPU temp / FPS / per-stage
# counters, browsable recent hits with cropped images, tail of the log.
# Served at http://192.168.4.1:8000 over the Pi's own AP (see README).
#
# TODO(stage 1, atomic step 8): create_app(source, counters) with a "/" page
# and a "/stream.mjpg" endpoint reading frames from the capture source.
# TODO(stage 2): counters on the page.
# TODO(stage 3): recent-hits list with images.
# TODO(stage 4): watchlist highlight, CPU temp/FPS, log tail.

from fastapi import FastAPI


def create_app() -> FastAPI:
    raise NotImplementedError
