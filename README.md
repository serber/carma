# carma
Raspberry Pi ANPR box: spots and reads passing plates, live Wi-Fi dashboard

See [SPEC.md](SPEC.md) for the full build spec.

See [PLAN.md](PLAN.md) for the atomic build-order steps and current progress.

## Bring-up checklist

_Filled in as each piece lands — see build order in SPEC.md._

- [ ] Flash Raspberry Pi OS Lite (64-bit, Trixie)
- [x] Wire the CSI camera ribbon cable — **power off first**, CSI isn't
      hot-pluggable. The Pi 4 has two similar-looking connectors; camera
      goes in the one marked **CAMERA**, not **DISPLAY** (easy to mix up).
      Push the connector's locking tab up before inserting, down to lock
      after. If using a **third-party sensor** (e.g. Arducam IMX519, not
      the official Camera Module 3/IMX708), `camera_auto_detect=1` won't
      find it — see [Third-party camera sensors](#third-party-camera-sensors)
      below
- [x] Install carma (`sudo scripts/install.sh`) — creates the `carma-svc`
      service user (deliberately not `carma`: that collides with a Pi
      login username someone might pick, especially since it's the
      project name — see the script's comment), a venv at
      `/opt/carma/.venv` (with `--system-site-packages` for picamera2),
      seeds `config.yaml`, pre-downloads the plate-detector and OCR models
      (needs internet once — see `scripts/fetch_models.py`), installs +
      enables the systemd unit
- [ ] Power on. **While developing**, leave the Pi joined to your regular
      Wi-Fi and open `http://<pi-ip>:8000` (`dashboard.host: 0.0.0.0`
      already listens on every interface, no AP needed — find the IP via
      your router or `ssh <user>@<hostname>.local`). **For field
      deployment**, switch to the AP instead — see
      [Wi-Fi access point](#wi-fi-access-point) below, then open
      `http://192.168.4.1:8000`
- [x] Confirm the live MJPEG preview and aim the camera — dashboard serves
      `/stream.mjpg` with detection boxes drawn on it; if the camera fails
      to open you'll see a red "camera unavailable" placeholder instead of
      a crash, and `frames_captured` stays at 0 on `/api/status`
- [x] Browse plate reads at `/hits` — timestamp, plate string, KZ/RU/unknown
      format tag, confidence, watchlist match (highlighted red with a ⚠ if
      `watchlist.enabled` and it matches a configured plate/substring), and
      the cropped plate image (click through to the full frame)
- [x] `journalctl -u carma -f` to watch structured logs — every module logs
      via its own name (`carma.capture.picamera2_source`, `carma.web.app`,
      ...) so the log line tells you which stage is talking; the same
      recent lines are also on the `/` dashboard (no SSH needed for a
      quick look) along with CPU temperature and FPS

## Third-party camera sensors

`camera_auto_detect=1` (the default in `/boot/firmware/config.txt`) only
reliably finds official Raspberry Pi camera modules (e.g. Camera Module
3 / IMX708). A third-party sensor — e.g. an Arducam 16MP IMX519 — needs
an explicit overlay instead:

```
camera_auto_detect=0
dtoverlay=imx519
```

(`imx519` here is the sensor name, matching a `.dtbo` file under
`/boot/firmware/overlays/` — swap in whatever's printed on your module.
Recent Raspberry Pi OS ships overlays for most common third-party sensors
already; no separate driver install needed.) Reboot, then verify with:

```sh
rpicam-hello --list-cameras
```

It should list your sensor with its supported resolutions. Note
`vcgencmd get_camera` is a legacy tool and often misreports
`detected=0` even when `rpicam-hello` sees the camera fine on the
libcamera-based stack — trust `rpicam-hello`, not `vcgencmd`, here.

## Wi-Fi access point

**Not needed for development.** carma listens on `0.0.0.0`, so while the
Pi is a normal Wi-Fi client on your network the dashboard is already
reachable at `http://<pi-ip>:8000` — no AP setup required. Only set this
up when you're ready to deploy in the field, away from any known Wi-Fi.

Raspberry Pi OS switched to **NetworkManager** as the default network stack
starting with Bookworm (Trixie too) — it can run the AP itself, so there's
no need for separate `hostapd`/`dnsmasq` services fighting NetworkManager
for control of `wlan0`. Fewer moving parts matters here: this device won't
have anyone around to fix a broken network stack.

**1. Create the AP profile (one-time, doesn't affect your current network).**
`autoconnect no` for now on purpose — this keeps it from fighting your
regular Wi-Fi profile for activation on every boot while you're still
developing:

```sh
sudo nmcli con add type wifi ifname wlan0 con-name carma-ap autoconnect no ssid carma
sudo nmcli con modify carma-ap 802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 7
sudo nmcli con modify carma-ap wifi-sec.key-mgmt wpa-psk
sudo nmcli con modify carma-ap wifi-sec.psk "<choose-a-real-password>"
sudo nmcli con modify carma-ap ipv4.method shared
sudo nmcli con modify carma-ap ipv4.address 192.168.4.1/24
```

**2. Switch to it whenever you want** (e.g. to test the AP flow, or for
real deployment):

```sh
sudo nmcli con up carma-ap
```

Verify with `nmcli con show --active` and by joining the `carma` network
from a phone/laptop and opening `http://192.168.4.1:8000`.

**3. Switch back to your regular Wi-Fi** for maintenance (e.g. re-running
`scripts/fetch_models.py` after changing a model, or just to get back to
normal development):

```sh
sudo nmcli con down carma-ap && sudo nmcli con up <your-home-wifi-profile>
```

**4. Only once you're actually deploying** in the field (no known Wi-Fi
around, no one there to fix a stuck network), make the AP come up on its
own after a power cycle:

```sh
sudo nmcli con modify carma-ap autoconnect yes
sudo nmcli con modify carma-ap connection.autoconnect-priority 10
```

## Development (off-Pi)

The capture/dashboard layer runs fine on a regular machine for iterating
without a Pi:

```sh
uv venv .venv
uv pip install -e ".[dev]"
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m carma --config config.example.yaml
```

`camera.backend: opencv` with a laptop webcam (or a deliberately-invalid
`device` to exercise the failure path) works without picamera2, which is
only importable on Raspberry Pi OS.
