# FastAPI dashboard: MJPEG live preview + per-stage counters. Served at
# http://192.168.4.1:8000 over the Pi's own AP (see README).
# TODO(stage 3): recent-hits list with images.
# TODO(stage 4): watchlist highlight, CPU temp, log tail.
from __future__ import annotations

import time

import cv2
import numpy as np
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from carma.capture_loop import CaptureLoop
from carma.counters import Counters

MJPEG_BOUNDARY = "frame"


def create_app(
    capture_loop: CaptureLoop, counters: Counters, self_check: dict[str, bool]
) -> FastAPI:
    app = FastAPI(title="carma")
    unavailable_jpeg = _placeholder_jpeg("camera unavailable - see logs")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _render_index(self_check)

    @app.get("/api/status")
    def status() -> JSONResponse:
        data = counters.snapshot()
        data["fps"] = round(capture_loop.fps, 1)
        data["self_check"] = self_check
        return JSONResponse(data)

    @app.get("/stream.mjpg")
    def stream() -> StreamingResponse:
        return StreamingResponse(
            _mjpeg_generator(capture_loop, unavailable_jpeg),
            media_type=f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}",
        )

    return app


def _mjpeg_generator(capture_loop: CaptureLoop, unavailable_jpeg: bytes):
    while True:
        jpeg = capture_loop.latest_jpeg() or unavailable_jpeg
        yield (
            f"--{MJPEG_BOUNDARY}\r\n"
            "Content-Type: image/jpeg\r\n"
            f"Content-Length: {len(jpeg)}\r\n\r\n"
        ).encode() + jpeg + b"\r\n"
        time.sleep(0.05)


def _placeholder_jpeg(text: str) -> bytes:
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(
        img, text, (20, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA
    )
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


def _render_index(self_check: dict[str, bool]) -> str:
    checks = "".join(
        f"<li>{name}: {'OK' if ok else 'FAILED'}</li>"
        for name, ok in self_check.items()
    )
    return f"""<!doctype html>
<html>
<head>
  <title>carma</title>
  <meta charset="utf-8">
  <style>
    body {{ font-family: sans-serif; background: #111; color: #eee; }}
    img {{ max-width: 100%; border: 1px solid #333; display: block; }}
    pre {{ font-family: monospace; }}
  </style>
</head>
<body>
  <h1>carma</h1>
  <ul>{checks}</ul>
  <img src="/stream.mjpg" alt="live preview">
  <h2>Counters</h2>
  <pre id="counters">loading...</pre>
  <script>
    async function poll() {{
      const r = await fetch('/api/status');
      document.getElementById('counters').textContent =
        JSON.stringify(await r.json(), null, 2);
    }}
    setInterval(poll, 1000);
    poll();
  </script>
</body>
</html>"""
