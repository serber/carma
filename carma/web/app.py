# FastAPI dashboard: MJPEG live preview + per-stage counters + CPU temp +
# log tail + browsable recent hits (watchlist matches highlighted). Served
# at http://192.168.4.1:8000 over the Pi's own AP (see README).
from __future__ import annotations

import html
import logging
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
from pydantic import BaseModel, Field

from carma.capture_loop import CaptureLoop
from carma.counters import Counters
from carma.logging_setup import get_recent_logs
from carma.settings import RuntimeSettings
from carma.storage.db import Hit, HitStore
from carma.sysinfo import cpu_temperature_celsius, disk_usage

logger = logging.getLogger(__name__)


class SettingsUpdate(BaseModel):
    min_confidence: float = Field(ge=0.0, le=1.0)


MJPEG_BOUNDARY = "frame"


def create_app(
    capture_loop: CaptureLoop,
    counters: Counters,
    self_check: dict[str, bool],
    hit_store: HitStore | None,
    images_dir: str,
    settings: RuntimeSettings,
) -> FastAPI:
    app = FastAPI(title="carma")
    unavailable_jpeg = _placeholder_jpeg("camera unavailable - see logs")

    Path(images_dir).mkdir(parents=True, exist_ok=True)
    app.mount("/images", StaticFiles(directory=images_dir), name="images")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _render_index(self_check, settings.min_confidence)

    @app.get("/api/settings")
    def get_settings() -> JSONResponse:
        return JSONResponse({"min_confidence": settings.min_confidence})

    @app.post("/api/settings")
    def update_settings(body: SettingsUpdate) -> JSONResponse:
        settings.min_confidence = body.min_confidence
        logger.info("min_confidence set to %.2f via dashboard", body.min_confidence)
        return JSONResponse({"min_confidence": settings.min_confidence})

    @app.get("/api/status")
    def status() -> JSONResponse:
        data = counters.snapshot()
        data["fps"] = round(capture_loop.fps, 1)
        data["cpu_temp_celsius"] = cpu_temperature_celsius()
        usage = disk_usage(images_dir)
        data["disk_free_bytes"] = usage.free_bytes if usage else None
        data["disk_total_bytes"] = usage.total_bytes if usage else None
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


# Dark palette: chart chrome/ink + status roles from the reference palette
# (good/warning/critical are fixed status colors, never repurposed for
# anything else). Every status/format cue below always ships with a text
# label too -- color is never the only signal.
_STYLE = """
    :root {
      color-scheme: dark;
      --bg: #0d0d0d;
      --surface: #1a1a19;
      --surface-2: #232322;
      --text: #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted: #898781;
      --border: rgba(255,255,255,0.10);
      --accent: #3987e5;
      --good: #0ca30c;
      --warning: #fab219;
      --critical: #d03b3b;
      --radius: 10px;
    }
    * { box-sizing: border-box; min-width: 0; }
    html, body { max-width: 100%; overflow-x: hidden; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      line-height: 1.5;
    }
    header.topbar {
      display: flex; align-items: center; justify-content: space-between;
      flex-wrap: wrap; row-gap: 6px;
      padding: 14px 20px; border-bottom: 1px solid var(--border);
      position: sticky; top: 0; background: var(--bg); z-index: 10;
    }
    header.topbar h1 { font-size: 18px; margin: 0; font-weight: 600; letter-spacing: 0.02em; }
    header.topbar nav a { color: var(--text-secondary); text-decoration: none; font-size: 14px; margin-left: 16px; }
    header.topbar nav a:hover { color: var(--text); }
    header.topbar nav a.active { color: var(--text); font-weight: 600; }
    main { max-width: 960px; margin: 0 auto; padding: 20px; }
    .card {
      background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
      padding: 16px; margin-bottom: 20px;
    }
    .card h2 {
      margin: 0 0 12px; font-size: 13px; text-transform: uppercase;
      letter-spacing: 0.06em; color: var(--text-muted); font-weight: 600;
    }
    .badges { display: flex; flex-wrap: wrap; gap: 8px; }
    .badge {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 4px 10px; border-radius: 999px; font-size: 13px; font-weight: 500;
      background: var(--surface-2); border: 1px solid var(--border);
    }
    .badge .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--good); }
    .badge.fail .dot { background: var(--critical); }
    .badge.fail { color: var(--critical); }
    .preview-wrap {
      position: relative; border-radius: var(--radius); overflow: hidden;
      border: 1px solid var(--border); line-height: 0;
    }
    .preview-wrap img { display: block; width: 100%; height: auto; background: #000; }
    .live-pill {
      position: absolute; top: 10px; left: 10px;
      background: rgba(0,0,0,0.6); color: var(--critical);
      padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; letter-spacing: 0.05em;
      display: flex; align-items: center; gap: 6px;
    }
    .live-pill .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--critical); }
    .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; }
    .stat-tile { background: var(--surface-2); border-radius: 8px; padding: 12px 14px; }
    .stat-tile .value { font-size: 26px; font-weight: 600; }
    .stat-tile .label { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
    .stat-tile.warning .value { color: var(--warning); }
    .stat-tile.critical .value { color: var(--critical); }
    #log {
      max-height: 280px; overflow-y: auto; background: var(--bg); border-radius: 8px;
      padding: 10px 12px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px;
    }
    #log .line { white-space: pre-wrap; word-break: break-all; color: var(--text-secondary); }
    #log .line.warn { color: var(--warning); }
    #log .line.err { color: var(--critical); }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; }
    th {
      text-align: left; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em;
      color: var(--text-muted); padding: 8px 10px; border-bottom: 1px solid var(--border);
    }
    td { padding: 8px 10px; border-bottom: 1px solid var(--border); font-size: 14px; vertical-align: middle; }
    tr.watchlist-match td { background: rgba(208,59,59,0.12); }
    .plate-crop { height: 48px; border-radius: 6px; display: block; }
    .fmt-badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }
    .fmt-badge.kz { background: rgba(57,135,229,0.18); color: #7db4f2; }
    .fmt-badge.ru { background: rgba(217,89,38,0.18); color: #f0a377; }
    .fmt-badge.unknown { background: var(--surface-2); color: var(--text-muted); }
    .meter {
      width: 60px; height: 6px; background: var(--surface-2); border-radius: 999px;
      overflow: hidden; display: inline-block; vertical-align: middle; margin-right: 6px;
    }
    .meter > span { display: block; height: 100%; background: var(--accent); }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    .settings-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
    .settings-row input[type="range"] { accent-color: var(--accent); flex: 1 1 160px; }
    .settings-row output { font-variant-numeric: tabular-nums; min-width: 3.5em; }
    .settings-row button {
      background: var(--accent); color: #fff; border: none; border-radius: 6px;
      padding: 6px 14px; font-size: 13px; font-weight: 600; cursor: pointer;
    }
    .settings-row button:hover { opacity: 0.9; }
    .settings-row .saved { color: var(--good); font-size: 13px; opacity: 0; transition: opacity 0.2s; }
    .settings-row .saved.show { opacity: 1; }
    .hint { color: var(--text-muted); font-size: 12px; margin: 8px 0 0; }
    .disk-track {
      height: 10px; background: var(--surface-2); border-radius: 999px; overflow: hidden;
    }
    .disk-fill { height: 100%; width: 0%; background: var(--accent); transition: width 0.3s; }
    .disk-fill.warning { background: var(--warning); }
    .disk-fill.critical { background: var(--critical); }
    .disk-label { color: var(--text-secondary); font-size: 13px; margin: 8px 0 16px; }
"""


def _page(title: str, active: str, body: str) -> str:
    def nav_link(href: str, label: str, key: str) -> str:
        css_class = ' class="active"' if key == active else ""
        return f'<a href="{href}"{css_class}>{label}</a>'

    nav = nav_link("/", "Live", "live") + nav_link("/hits", "Hits", "hits")
    return f"""<!doctype html>
<html>
<head>
  <title>{html.escape(title)}</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>{_STYLE}</style>
</head>
<body>
  <header class="topbar">
    <h1>carma</h1>
    <nav>{nav}</nav>
  </header>
  <main>
{body}
  </main>
</body>
</html>"""


def _render_index(self_check: dict[str, bool], min_confidence: float) -> str:
    badges = "".join(
        f'<span class="badge{"" if ok else " fail"}">'
        f'<span class="dot"></span>{html.escape(name)}: {"OK" if ok else "FAILED"}'
        "</span>"
        for name, ok in self_check.items()
    )
    body = f"""
    <div class="card">
      <h2>System status</h2>
      <div class="badges">{badges}</div>
    </div>
    <div class="card">
      <h2>Live preview</h2>
      <div class="preview-wrap">
        <span class="live-pill"><span class="dot"></span>LIVE</span>
        <img src="/stream.mjpg" alt="live preview">
      </div>
    </div>
    <div class="card">
      <h2>Storage</h2>
      <div class="disk-track"><div class="disk-fill" id="disk-fill"></div></div>
      <p class="disk-label" id="disk-label">loading&hellip;</p>
      <div class="settings-row">
        <label for="min-confidence">Minimum confidence to store a hit</label>
        <input type="range" id="min-confidence" min="0" max="1" step="0.05" value="{min_confidence}">
        <output id="min-confidence-value">{min_confidence:.2f}</output>
        <button id="save-settings" type="button">Save</button>
        <span class="saved" id="settings-saved">Saved</span>
      </div>
      <p class="hint">
        Reads below this confidence still show live on the preview and count
        toward OCR reads -- they just aren't written to <a href="/hits">Hits</a>.
        0 stores everything.
      </p>
    </div>
    <div class="card">
      <h2>Counters</h2>
      <div class="stat-grid">
        <div class="stat-tile"><div class="value" id="stat-frames">&ndash;</div><div class="label">Frames captured</div></div>
        <div class="stat-tile"><div class="value" id="stat-motion">&ndash;</div><div class="label">Motion events</div></div>
        <div class="stat-tile"><div class="value" id="stat-detections">&ndash;</div><div class="label">Detections</div></div>
        <div class="stat-tile"><div class="value" id="stat-ocr">&ndash;</div><div class="label">OCR reads</div></div>
        <div class="stat-tile"><div class="value" id="stat-fps">&ndash;</div><div class="label">FPS</div></div>
        <div class="stat-tile" id="tile-temp"><div class="value" id="stat-temp">&ndash;</div><div class="label">CPU temp</div></div>
      </div>
    </div>
    <div class="card">
      <h2>Log tail</h2>
      <div id="log">loading&hellip;</div>
    </div>
    <script>
      const minConfidenceInput = document.getElementById('min-confidence');
      const minConfidenceValue = document.getElementById('min-confidence-value');
      minConfidenceInput.addEventListener('input', () => {{
        minConfidenceValue.textContent = parseFloat(minConfidenceInput.value).toFixed(2);
      }});
      document.getElementById('save-settings').addEventListener('click', async () => {{
        await fetch('/api/settings', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{min_confidence: parseFloat(minConfidenceInput.value)}}),
        }});
        const saved = document.getElementById('settings-saved');
        saved.classList.add('show');
        setTimeout(() => saved.classList.remove('show'), 1500);
      }});

      function tempClass(t) {{
        if (t === null || t === undefined) return '';
        if (t >= 80) return 'critical';
        if (t >= 70) return 'warning';
        return '';
      }}
      function lineClass(line) {{
        if (line.includes(' ERROR ') || line.includes(' CRITICAL ')) return 'err';
        if (line.includes(' WARNING ')) return 'warn';
        return '';
      }}
      function diskClass(usedPct) {{
        if (usedPct >= 95) return 'critical';
        if (usedPct >= 80) return 'warning';
        return '';
      }}
      function formatBytes(bytes) {{
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let v = bytes, i = 0;
        while (v >= 1024 && i < units.length - 1) {{ v /= 1024; i++; }}
        return v.toFixed(1) + ' ' + units[i];
      }}
      async function poll() {{
        const data = await (await fetch('/api/status')).json();
        document.getElementById('stat-frames').textContent = data.frames_captured;
        document.getElementById('stat-motion').textContent = data.motion_events;
        document.getElementById('stat-detections').textContent = data.detections;
        document.getElementById('stat-ocr').textContent = data.ocr_reads;
        document.getElementById('stat-fps').textContent = data.fps;
        document.getElementById('stat-temp').textContent =
          data.cpu_temp_celsius === null ? 'n/a' : data.cpu_temp_celsius.toFixed(1) + '°C';
        document.getElementById('tile-temp').className = 'stat-tile ' + tempClass(data.cpu_temp_celsius);

        const diskFill = document.getElementById('disk-fill');
        const diskLabel = document.getElementById('disk-label');
        if (data.disk_free_bytes === null || !data.disk_total_bytes) {{
          diskFill.style.width = '0%';
          diskLabel.textContent = 'disk usage unavailable';
        }} else {{
          const usedPct = 100 * (1 - data.disk_free_bytes / data.disk_total_bytes);
          diskFill.style.width = usedPct.toFixed(1) + '%';
          diskFill.className = 'disk-fill ' + diskClass(usedPct);
          diskLabel.textContent =
            formatBytes(data.disk_free_bytes) + ' free of ' + formatBytes(data.disk_total_bytes);
        }}

        const logEl = document.getElementById('log');
        const atBottom = logEl.scrollTop + logEl.clientHeight >= logEl.scrollHeight - 5;
        const text = await (await fetch('/api/log')).text();
        logEl.textContent = '';
        for (const line of text.split('\\n')) {{
          const div = document.createElement('div');
          div.className = 'line ' + lineClass(line);
          div.textContent = line;
          logEl.appendChild(div);
        }}
        if (atBottom) logEl.scrollTop = logEl.scrollHeight;
      }}
      setInterval(poll, 1000);
      poll();
    </script>"""
    return _page("carma", "live", body)


_FORMAT_CLASS = {"KZ": "kz", "RU": "ru"}


def _format_badge(fmt: str) -> str:
    css_class = _FORMAT_CLASS.get(fmt, "unknown")
    return f'<span class="fmt-badge {css_class}">{html.escape(fmt)}</span>'


def _confidence_meter(confidence: float) -> str:
    pct = max(0, min(100, round(confidence * 100)))
    return f'<span class="meter"><span style="width:{pct}%"></span></span>{confidence:.2f}'


def _render_hits(hits: list[Hit]) -> str:
    if not hits:
        rows = '<tr><td colspan="6">no hits yet</td></tr>'
    else:
        rows = "".join(
            f'<tr class="{"watchlist-match" if hit.watchlist_match else ""}">'
            f"<td>{html.escape(hit.timestamp)}</td>"
            f'<td>{"&#9888; " if hit.watchlist_match else ""}{html.escape(hit.plate)}</td>'
            f"<td>{_format_badge(hit.format)}</td>"
            f"<td>{_confidence_meter(hit.confidence)}</td>"
            f'<td>{"&#9888; watchlist" if hit.watchlist_match else ""}</td>'
            f'<td><a href="/images/{html.escape(hit.frame_filename)}">'
            f'<img class="plate-crop" src="/images/{html.escape(hit.crop_filename)}" '
            f'alt="{html.escape(hit.plate)}"></a></td>'
            "</tr>"
            for hit in hits
        )
    body = f"""
    <div class="card">
      <h2>Recent hits</h2>
      <div class="table-wrap">
        <table>
          <tr><th>Timestamp</th><th>Plate</th><th>Format</th><th>Confidence</th><th>Watchlist</th><th>Crop</th></tr>
          {rows}
        </table>
      </div>
    </div>"""
    return _page("carma — hits", "hits", body)
