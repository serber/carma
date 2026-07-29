# FastAPI dashboard: MJPEG live preview + per-stage counters + CPU temp +
# log tail + browsable recent hits (watchlist matches highlighted). Served
# at http://192.168.4.1:8000 over the Pi's own AP (see README).
from __future__ import annotations

import dataclasses
import html
import logging
import time
from pathlib import Path
from typing import Literal

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

from carma import device, wifi
from carma.capture_loop import CaptureLoop
from carma.counters import Counters
from carma.logging_setup import get_recent_logs
from carma.settings import RuntimeSettings
from carma.storage.db import Hit, HitStore
from carma.storage.images import clear_images, images_dir_size
from carma.sysinfo import cpu_temperature_celsius, disk_usage

logger = logging.getLogger(__name__)


class SettingsUpdate(BaseModel):
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    color_mode: Literal["color", "grayscale"] | None = None


class WifiConnectRequest(BaseModel):
    ssid: str = Field(min_length=1, max_length=32)
    password: str = Field(default="", max_length=63)


class WifiForgetRequest(BaseModel):
    ssid: str = Field(min_length=1, max_length=32)


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
        return _render_index(self_check)

    @app.get("/api/settings")
    def get_settings() -> JSONResponse:
        return JSONResponse({
            "min_confidence": settings.min_confidence,
            "color_mode": settings.color_mode,
        })

    @app.post("/api/settings")
    def update_settings(body: SettingsUpdate) -> JSONResponse:
        if body.min_confidence is not None:
            settings.min_confidence = body.min_confidence
            logger.info("min_confidence set to %.2f via dashboard", body.min_confidence)
        if body.color_mode is not None:
            settings.color_mode = body.color_mode
            logger.info("color_mode set to %s via dashboard", body.color_mode)
        return JSONResponse({
            "min_confidence": settings.min_confidence,
            "color_mode": settings.color_mode,
        })

    @app.get("/api/status")
    def status() -> JSONResponse:
        data = counters.snapshot()
        data["fps"] = round(capture_loop.fps, 1)
        data["cpu_temp_celsius"] = cpu_temperature_celsius()
        usage = disk_usage(images_dir)
        data["disk_free_bytes"] = usage.free_bytes if usage else None
        data["disk_total_bytes"] = usage.total_bytes if usage else None
        data["images_bytes"] = images_dir_size(images_dir)
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
        total = hit_store.count() if hit_store is not None else 0
        return _render_hits(recent, total, images_dir_size(images_dir))

    @app.post("/api/hits/clear")
    def clear_hits() -> JSONResponse:
        count = hit_store.count() if hit_store is not None else 0
        if hit_store is not None:
            hit_store.clear()
        clear_images(images_dir)
        logger.warning("cleared %d hit(s) and their images via dashboard", count)
        return JSONResponse({"cleared": count})

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page() -> str:
        return _render_settings(wifi.available(), settings.min_confidence, settings.color_mode)

    @app.post("/api/device/restart-service")
    def restart_service() -> JSONResponse:
        ok, message = device.restart_service()
        logger.warning("service restart requested via dashboard: %s", "ok" if ok else message)
        return JSONResponse({"ok": ok, "message": message}, status_code=200 if ok else 502)

    @app.post("/api/device/reboot")
    def reboot_device() -> JSONResponse:
        ok, message = device.reboot_device()
        logger.warning("device reboot requested via dashboard: %s", "ok" if ok else message)
        return JSONResponse({"ok": ok, "message": message}, status_code=200 if ok else 502)

    @app.get("/api/wifi/status")
    def wifi_status() -> JSONResponse:
        return JSONResponse(dataclasses.asdict(wifi.get_status()))

    @app.get("/api/wifi/networks")
    def wifi_networks() -> JSONResponse:
        return JSONResponse({"networks": [dataclasses.asdict(n) for n in wifi.scan_networks()]})

    @app.get("/api/wifi/saved")
    def wifi_saved() -> JSONResponse:
        return JSONResponse({"profiles": [dataclasses.asdict(p) for p in wifi.list_saved_profiles()]})

    @app.post("/api/wifi/connect")
    def wifi_connect(body: WifiConnectRequest) -> JSONResponse:
        ok, message = wifi.connect(body.ssid, body.password)
        logger.info("wifi connect to %r via dashboard: %s", body.ssid, "ok" if ok else message)
        return JSONResponse({"ok": ok, "message": message}, status_code=200 if ok else 502)

    @app.post("/api/wifi/forget")
    def wifi_forget(body: WifiForgetRequest) -> JSONResponse:
        ok, message = wifi.forget(body.ssid)
        logger.info("wifi forget of %r via dashboard: %s", body.ssid, "ok" if ok else message)
        return JSONResponse({"ok": ok, "message": message}, status_code=200 if ok else 502)

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
    .hits-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
    .hits-toolbar h2 { margin: 0; }
    .danger-button {
      background: var(--critical); color: #fff; border: none; border-radius: 6px;
      padding: 6px 14px; font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap;
    }
    .danger-button:hover { opacity: 0.9; }
    .secondary-button {
      background: var(--surface-2); color: var(--text); border: 1px solid var(--border);
      border-radius: 6px; padding: 6px 14px; font-size: 13px; font-weight: 600; cursor: pointer;
    }
    .secondary-button:hover { opacity: 0.9; }
    .mode-button {
      background: var(--surface-2); color: var(--text); border: 1px solid var(--border);
      border-radius: 6px; padding: 6px 14px; font-size: 13px; font-weight: 600; cursor: pointer;
    }
    .mode-button:hover { opacity: 0.9; }
    .mode-button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
    .network-row {
      display: flex; align-items: center; justify-content: space-between; gap: 12px;
      padding: 8px 10px; border-bottom: 1px solid var(--border); font-size: 14px; cursor: pointer;
    }
    .network-row:last-child { border-bottom: none; }
    .network-row:hover { background: var(--surface-2); }
    .network-row.static { cursor: default; }
    .network-row.static:hover { background: none; }
    .settings-row input[type="text"], .settings-row input[type="password"] {
      background: var(--surface-2); border: 1px solid var(--border); border-radius: 6px;
      color: var(--text); padding: 6px 10px; font-size: 14px; flex: 1 1 200px;
    }
"""


def _page(title: str, active: str, body: str) -> str:
    def nav_link(href: str, label: str, key: str) -> str:
        css_class = ' class="active"' if key == active else ""
        return f'<a href="{href}"{css_class}>{label}</a>'

    nav = (
        nav_link("/", "Live", "live")
        + nav_link("/hits", "Hits", "hits")
        + nav_link("/settings", "Settings", "settings")
    )
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


def _render_index(self_check: dict[str, bool]) -> str:
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
      <p class="disk-label" id="images-label">loading&hellip;</p>
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
        document.getElementById('images-label').textContent =
          formatBytes(data.images_bytes) + ' used by stored images';

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


def _wifi_fragment(nmcli_available: bool) -> str:
    """Wi-Fi status/scan/connect/saved cards, embedded in the Settings page."""
    unavailable_hint = (
        ""
        if nmcli_available
        else '<p class="hint">nmcli was not found -- Wi-Fi management only works on the Pi itself.</p>'
    )
    return f"""
    <div class="card">
      <h2>Current connection</h2>
      <div class="badges">
        <span class="badge" id="wifi-mode-badge"><span class="dot"></span><span id="wifi-mode-text">loading&hellip;</span></span>
      </div>
      <p class="hint" id="wifi-detail">&nbsp;</p>
      {unavailable_hint}
    </div>
    <div class="card">
      <h2>Available networks</h2>
      <p class="hint" id="scan-hint">Scanning&hellip;</p>
      <div id="network-list"></div>
      <p style="margin: 12px 0 0;"><button id="rescan" type="button" class="secondary-button">Rescan</button></p>
    </div>
    <div class="card">
      <h2>Connect to a network</h2>
      <div class="settings-row">
        <label for="wifi-ssid">SSID</label>
        <input type="text" id="wifi-ssid" maxlength="32" placeholder="Network name">
      </div>
      <div class="settings-row">
        <label for="wifi-password">Password</label>
        <input type="password" id="wifi-password" maxlength="63" placeholder="leave blank for open networks">
        <button id="wifi-connect" type="button">Connect</button>
      </div>
      <p class="hint" id="wifi-connect-status">&nbsp;</p>
      <p class="hint">
        Connecting switches wlan0 off the carma hotspot -- if you're on the
        "carma" Wi-Fi right now, this device will drop off it. It's
        reachable again at the new network's IP, or back on carma-ap if
        the connection fails.
      </p>
    </div>
    <div class="card">
      <h2>Saved networks</h2>
      <div id="saved-list" class="hint">loading&hellip;</div>
    </div>
    <script>
      function escapeHtml(s) {{
        const div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
      }}

      async function loadWifiStatus() {{
        const badge = document.getElementById('wifi-mode-badge');
        const modeText = document.getElementById('wifi-mode-text');
        const detail = document.getElementById('wifi-detail');
        const labels = {{
          client: 'Connected', ap: 'Hotspot (carma-ap)',
          disconnected: 'Disconnected', unavailable: 'Unavailable',
        }};
        try {{
          const data = await (await fetch('/api/wifi/status')).json();
          modeText.textContent = labels[data.mode] || data.mode;
          badge.className = 'badge' + (data.mode === 'client' ? '' : ' fail');
          if (data.mode === 'client') {{
            detail.textContent = (data.ssid || '') + ' \\u2014 ' + (data.ip_address || 'no IP yet');
          }} else if (data.mode === 'ap') {{
            detail.textContent = 'Serving its own hotspot -- no known network in range.';
          }} else {{
            detail.textContent = '';
          }}
        }} catch (e) {{
          modeText.textContent = 'error';
        }}
      }}

      async function loadNetworks() {{
        const list = document.getElementById('network-list');
        const hint = document.getElementById('scan-hint');
        hint.textContent = 'Scanning\\u2026';
        try {{
          const data = await (await fetch('/api/wifi/networks')).json();
          list.innerHTML = '';
          if (data.networks.length === 0) {{
            hint.textContent = 'No networks found.';
            return;
          }}
          hint.textContent = '';
          for (const net of data.networks) {{
            const row = document.createElement('div');
            row.className = 'network-row';
            row.innerHTML =
              '<span>' + (net.in_use ? '&#9679; ' : '') + escapeHtml(net.ssid) + '</span>' +
              '<span class="hint">' + (net.secured ? '&#128274;' : 'open') + ' ' + net.signal + '%</span>';
            row.addEventListener('click', () => {{
              document.getElementById('wifi-ssid').value = net.ssid;
              document.getElementById('wifi-password').focus();
            }});
            list.appendChild(row);
          }}
        }} catch (e) {{
          hint.textContent = 'Scan failed.';
        }}
      }}

      async function loadSaved() {{
        const list = document.getElementById('saved-list');
        try {{
          const data = await (await fetch('/api/wifi/saved')).json();
          if (data.profiles.length === 0) {{
            list.textContent = 'No saved networks yet.';
            return;
          }}
          list.innerHTML = '';
          for (const p of data.profiles) {{
            const row = document.createElement('div');
            row.className = 'network-row static';
            const nameSpan = document.createElement('span');
            nameSpan.textContent = p.name;
            const btn = document.createElement('button');
            btn.textContent = 'Forget';
            btn.type = 'button';
            btn.className = 'danger-button';
            btn.addEventListener('click', async (ev) => {{
              ev.stopPropagation();
              if (!confirm('Forget "' + p.name + '"?')) return;
              await fetch('/api/wifi/forget', {{
                method: 'POST', headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ssid: p.name}}),
              }});
              loadSaved();
            }});
            row.appendChild(nameSpan);
            row.appendChild(btn);
            list.appendChild(row);
          }}
        }} catch (e) {{
          list.textContent = 'Failed to load.';
        }}
      }}

      document.getElementById('rescan').addEventListener('click', loadNetworks);

      document.getElementById('wifi-connect').addEventListener('click', async () => {{
        const ssid = document.getElementById('wifi-ssid').value.trim();
        const password = document.getElementById('wifi-password').value;
        const status = document.getElementById('wifi-connect-status');
        if (!ssid) {{ status.textContent = 'Enter an SSID.'; return; }}
        status.textContent = 'Connecting\\u2026';
        try {{
          const resp = await fetch('/api/wifi/connect', {{
            method: 'POST', headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ssid, password}}),
          }});
          const data = await resp.json();
          status.textContent = data.ok ? 'Connected.' : ('Failed: ' + data.message);
          if (data.ok) {{
            document.getElementById('wifi-password').value = '';
            loadWifiStatus();
            loadSaved();
          }}
        }} catch (e) {{
          status.textContent = 'Request failed.';
        }}
      }});

      loadWifiStatus();
      loadNetworks();
      loadSaved();
    </script>"""


def _render_settings(nmcli_available: bool, min_confidence: float, color_mode: str) -> str:
    body = f"""
    <div class="card">
      <h2>Camera</h2>
      <div class="settings-row">
        <span>Color mode</span>
        <button type="button" class="mode-button" id="mode-color" data-mode="color">Color</button>
        <button type="button" class="mode-button" id="mode-grayscale" data-mode="grayscale">Black &amp; white</button>
      </div>
      <p class="hint">
        Applies to the live preview, detection/OCR, and stored hit images.
        Takes effect on the next captured frame -- no restart needed.
      </p>
    </div>
    <div class="card">
      <h2>Detection</h2>
      <div class="settings-row">
        <label for="min-confidence">Minimum confidence to store a hit</label>
        <input type="range" id="min-confidence" min="0" max="1" step="0.05" value="{min_confidence}">
        <output id="min-confidence-value">{min_confidence:.2f}</output>
        <button id="save-confidence" type="button">Save</button>
        <span class="saved" id="confidence-saved">Saved</span>
      </div>
      <p class="hint">
        Reads below this confidence still show live on the preview and count
        toward OCR reads -- they just aren't written to <a href="/hits">Hits</a>.
        0 stores everything. Saved value survives a restart.
      </p>
    </div>
    {_wifi_fragment(nmcli_available)}
    <div class="card">
      <h2>Restart</h2>
      <div class="settings-row">
        <button id="restart-service" type="button" class="secondary-button">Restart carma-app service</button>
        <button id="reboot-device" type="button" class="danger-button">Reboot device</button>
      </div>
      <p class="hint" id="restart-status">&nbsp;</p>
      <p class="hint">
        Restarting the service takes a few seconds and briefly drops the
        live preview. Rebooting takes longer, and also drops Wi-Fi if
        you're connected to carma-ap right now.
      </p>
    </div>
    <script>
      const modeButtons = document.querySelectorAll('.mode-button');
      function setActiveMode(mode) {{
        modeButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === mode));
      }}
      setActiveMode('{color_mode}');
      modeButtons.forEach(btn => {{
        btn.addEventListener('click', async () => {{
          await fetch('/api/settings', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{color_mode: btn.dataset.mode}}),
          }});
          setActiveMode(btn.dataset.mode);
        }});
      }});

      const minConfidenceInput = document.getElementById('min-confidence');
      const minConfidenceValue = document.getElementById('min-confidence-value');
      minConfidenceInput.addEventListener('input', () => {{
        minConfidenceValue.textContent = parseFloat(minConfidenceInput.value).toFixed(2);
      }});
      document.getElementById('save-confidence').addEventListener('click', async () => {{
        await fetch('/api/settings', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{min_confidence: parseFloat(minConfidenceInput.value)}}),
        }});
        const saved = document.getElementById('confidence-saved');
        saved.classList.add('show');
        setTimeout(() => saved.classList.remove('show'), 1500);
      }});

      document.getElementById('restart-service').addEventListener('click', async () => {{
        if (!confirm('Restart the carma-app service? The live preview drops for a few seconds.')) return;
        const status = document.getElementById('restart-status');
        status.textContent = 'Restarting\\u2026';
        try {{
          const resp = await fetch('/api/device/restart-service', {{ method: 'POST' }});
          const data = await resp.json();
          status.textContent = data.ok ? 'Restarting now.' : ('Failed: ' + data.message);
        }} catch (e) {{
          status.textContent = 'Request failed.';
        }}
      }});

      document.getElementById('reboot-device').addEventListener('click', async () => {{
        if (!confirm('Reboot the whole device? This takes longer than a service restart.')) return;
        const status = document.getElementById('restart-status');
        status.textContent = 'Rebooting\\u2026';
        try {{
          const resp = await fetch('/api/device/reboot', {{ method: 'POST' }});
          const data = await resp.json();
          status.textContent = data.ok ? 'Rebooting now.' : ('Failed: ' + data.message);
        }} catch (e) {{
          status.textContent = 'Request failed.';
        }}
      }});
    </script>"""
    return _page("carma — settings", "settings", body)


_FORMAT_CLASS = {"KZ": "kz", "RU": "ru"}


def _format_badge(fmt: str) -> str:
    css_class = _FORMAT_CLASS.get(fmt, "unknown")
    return f'<span class="fmt-badge {css_class}">{html.escape(fmt)}</span>'


def _confidence_meter(confidence: float) -> str:
    pct = max(0, min(100, round(confidence * 100)))
    return f'<span class="meter"><span style="width:{pct}%"></span></span>{confidence:.2f}'


def _format_bytes(n: int) -> str:
    """Mirrors the client-side formatBytes() in _render_index's script."""
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"  # unreachable, keeps type checkers happy


def _render_hits(hits: list[Hit], total_count: int, images_bytes: int) -> str:
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
      <div class="hits-toolbar">
        <div>
          <h2>Recent hits</h2>
          <p class="hint" style="margin-top:2px;">
            {total_count} stored &middot; {html.escape(_format_bytes(images_bytes))} of images
          </p>
        </div>
        <button id="clear-hits" type="button" class="danger-button">Clear all hits &amp; images</button>
      </div>
      <div class="table-wrap">
        <table>
          <tr><th>Timestamp</th><th>Plate</th><th>Format</th><th>Confidence</th><th>Watchlist</th><th>Crop</th></tr>
          {rows}
        </table>
      </div>
    </div>
    <script>
      document.getElementById('clear-hits').addEventListener('click', async () => {{
        if (!confirm('Delete all {total_count} stored hit(s) and their images? This cannot be undone.')) {{
          return;
        }}
        const resp = await fetch('/api/hits/clear', {{ method: 'POST' }});
        if (resp.ok) location.reload();
      }});
    </script>"""
    return _page("carma — hits", "hits", body)
