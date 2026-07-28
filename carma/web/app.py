# FastAPI dashboard: MJPEG live preview + per-stage counters + CPU temp +
# log tail + browsable recent hits (watchlist matches highlighted). Served
# at http://192.168.4.1:8000 over the Pi's own AP (see README).
from __future__ import annotations

import html
import time
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles

from carma.capture_loop import CaptureLoop
from carma.counters import Counters
from carma.logging_setup import get_recent_logs
from carma.storage.db import Hit, HitStore
from carma.sysinfo import cpu_temperature_celsius

MJPEG_BOUNDARY = "frame"


def create_app(
    capture_loop: CaptureLoop,
    counters: Counters,
    self_check: dict[str, bool],
    hit_store: HitStore | None,
    images_dir: str,
) -> FastAPI:
    app = FastAPI(title="carma")
    unavailable_jpeg = _placeholder_jpeg("camera unavailable - see logs")

    Path(images_dir).mkdir(parents=True, exist_ok=True)
    app.mount("/images", StaticFiles(directory=images_dir), name="images")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _render_index(self_check)

    @app.get("/api/status")
    def status() -> JSONResponse:
        data = counters.snapshot()
        data["fps"] = round(capture_loop.fps, 1)
        data["cpu_temp_celsius"] = cpu_temperature_celsius()
        data["self_check"] = self_check
        return JSONResponse(data)

    @app.get("/api/log", response_class=PlainTextResponse)
    def log() -> str:
        return "\n".join(get_recent_logs())

    @app.get("/stream.mjpg")
    def stream() -> StreamingResponse:
        return StreamingResponse(
            _mjpeg_generator(capture_loop, unavailable_jpeg),
            media_type=f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}",
        )

    @app.get("/hits", response_class=HTMLResponse)
    def hits() -> str:
        recent = hit_store.recent(limit=50) if hit_store is not None else []
        return _render_hits(recent)

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
    pre {{ font-family: monospace; white-space: pre-wrap; word-break: break-all; }}
    #log {{ max-height: 300px; overflow-y: auto; background: #000; padding: 8px; }}
    a {{ color: #6cf; }}
  </style>
</head>
<body>
  <h1>carma</h1>
  <ul>{checks}</ul>
  <p><a href="/hits">recent hits &rarr;</a></p>
  <img src="/stream.mjpg" alt="live preview">
  <h2>Counters</h2>
  <pre id="counters">loading...</pre>
  <h2>Log tail</h2>
  <pre id="log">loading...</pre>
  <script>
    async function poll() {{
      const r = await fetch('/api/status');
      document.getElementById('counters').textContent =
        JSON.stringify(await r.json(), null, 2);
      const logEl = document.getElementById('log');
      const atBottom = logEl.scrollTop + logEl.clientHeight >= logEl.scrollHeight - 5;
      logEl.textContent = await (await fetch('/api/log')).text();
      if (atBottom) logEl.scrollTop = logEl.scrollHeight;
    }}
    setInterval(poll, 1000);
    poll();
  </script>
</body>
</html>"""


def _render_hits(hits: list[Hit]) -> str:
    if not hits:
        rows = '<tr><td colspan="6">no hits yet</td></tr>'
    else:
        rows = "".join(
            f'<tr class="{"watchlist-match" if hit.watchlist_match else ""}">'
            f"<td>{html.escape(hit.timestamp)}</td>"
            f'<td>{"&#9888; " if hit.watchlist_match else ""}{html.escape(hit.plate)}</td>'
            f"<td>{html.escape(hit.format)}</td>"
            f"<td>{hit.confidence:.2f}</td>"
            f"<td>{'yes' if hit.watchlist_match else ''}</td>"
            f'<td><a href="/images/{html.escape(hit.frame_filename)}">'
            f'<img src="/images/{html.escape(hit.crop_filename)}" '
            f'alt="{html.escape(hit.plate)}"></a></td>'
            "</tr>"
            for hit in hits
        )
    return f"""<!doctype html>
<html>
<head>
  <title>carma — hits</title>
  <meta charset="utf-8">
  <style>
    body {{ font-family: sans-serif; background: #111; color: #eee; }}
    table {{ border-collapse: collapse; width: 100%; }}
    td, th {{ border: 1px solid #333; padding: 4px 8px; text-align: left; }}
    img {{ max-height: 60px; display: block; }}
    a {{ color: #6cf; }}
    tr.watchlist-match {{ background: #533; }}
  </style>
</head>
<body>
  <h1>carma — recent hits</h1>
  <p><a href="/">&larr; live view</a></p>
  <table>
    <tr><th>timestamp</th><th>plate</th><th>format</th><th>confidence</th><th>watchlist</th><th>crop (click for full frame)</th></tr>
    {rows}
  </table>
</body>
</html>"""
