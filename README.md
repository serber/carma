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
- [x] Install carma — one command on a bare Pi with nothing on it yet:
      ```sh
      curl -fsSL https://raw.githubusercontent.com/serber/carma/development/scripts/bootstrap.sh | bash
      ```
      (clones to `~/carma-app` and runs `sudo scripts/install.sh`; swap
      `development` for whatever branch/tag you want to deploy). Already
      have a checkout? Just run `sudo scripts/install.sh` from inside it —
      that's all `bootstrap.sh` does under the hood. Either way it: creates
      the `carma-svc` service user (deliberately not `carma`: that collides
      with a Pi login username someone might pick, especially since it's
      the project name — see the script's comment), a venv at
      `/opt/carma-app/.venv` (with `--system-site-packages` for picamera2),
      seeds `config.yaml`, pre-downloads the plate-detector and OCR models
      (needs internet once — see `scripts/fetch_models.py`), installs +
      enables the `carma-app` systemd unit, and sets up the `carma-ap`
      hotspot profile with a default SSID/password (`carma-ap` /
      `carmapwd` — override via `CARMA_AP_SSID`/`CARMA_AP_PASSWORD` env
      vars before running, or change it later from the dashboard's Settings
      page / `nmcli`)
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
- [x] `journalctl -u carma-app -f` to watch structured logs — every module logs
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

**1. The AP profile is created automatically.** `scripts/install.sh` sets
up a `carma-ap` connection profile (`autoconnect no` on purpose — this
keeps it from fighting your regular Wi-Fi profile for activation on every
boot while you're still developing) with SSID `carma-ap` and password
`carmapwd` by default. Override either before installing:

```sh
sudo CARMA_AP_SSID=my-ssid CARMA_AP_PASSWORD='a-real-password' scripts/install.sh
```

or change them later (dashboard's Settings page, or by hand):

```sh
sudo nmcli con modify carma-ap 802-11-wireless.ssid my-ssid
sudo nmcli con modify carma-ap wifi-sec.psk "a-real-password"
```

If you're setting this up manually instead (no `install.sh`), the
equivalent one-time commands are:

```sh
sudo nmcli con add type wifi ifname wlan0 con-name carma-ap autoconnect no ssid carma-ap
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

Verify with `nmcli con show --active` and by joining the `carma-ap`
network from a phone/laptop and opening `http://192.168.4.1:8000`.

**3. Switch back to your regular Wi-Fi** for maintenance (e.g. re-running
`scripts/fetch_models.py` after changing a model, or just to get back to
normal development):

```sh
sudo nmcli con down carma-ap && sudo nmcli con up <your-home-wifi-profile>
```

**4. Automatic fallback for field deployment.** `scripts/install.sh`
installs and enables `carma-ap-fallback.service`, which runs once at every
boot: it waits up to 45s (`CARMA_WIFI_TIMEOUT`, see the unit file) for
`wlan0` to reach a normal client connection, and only if that doesn't
happen does it bring up `carma-ap`. This means the device keeps using your
regular Wi-Fi whenever it's in range, and only serves its own hotspot when
it can't reach a known network -- no need to flip `autoconnect` by hand,
and no risk of the AP profile fighting your home Wi-Fi profile for
activation on every boot. If `carma-ap` was still active from a previous
boot (e.g. no known network was in range last time), the script drops it
before checking, so a network that's become reachable since then always
gets a fair shot instead of the device staying stuck on the hotspot.

Leave `carma-ap` at `autoconnect no` (the default from step 1) -- the
fallback service is what brings it up, not NetworkManager's own
autoconnect logic. Check it with:

```sh
systemctl status carma-ap-fallback
journalctl -u carma-ap-fallback -b
```

**5. Joining a network from the dashboard.** Once you're on `carma-ap`
(or already on a normal network reaching the device), open **Settings**
in the dashboard to scan for and join a network without SSH -- handy
after moving the device to a new location. It's backed by
`scripts/carma-wifi.sh`, a small root-only helper `install.sh` wires up
via a sudoers rule scoped to that one script (`carma-svc`, the service
user, otherwise has no elevated access at all). The manual `nmcli`
commands above still work too, e.g. for scripting a fleet rollout.

## Settings page

The dashboard's **Settings** tab (`/settings`) is the one place for
everything that isn't a build-time config: Wi-Fi (above), camera color
mode, and restarting.

- **Camera color mode** toggles between color and black & white. It
  applies to the live preview, detection/OCR, and stored hit images alike
  (see `carma/capture_loop.py`'s `_apply_color_mode`), takes effect on the
  next captured frame, and survives a restart the same way
  `storage.min_confidence` does (`camera.color_mode` in `config.yaml` is
  just the starting value).
- **Restart carma-app service** / **Reboot device** run
  `scripts/carma-restart.sh` as root via another narrow sudoers rule
  (`systemd/carma-restart.sudoers`). The helper schedules the actual
  `systemctl restart`/`systemctl reboot` a second out with `systemd-run`
  in a transient unit of its own, rather than running it inline -- inline
  would kill the very process handling the dashboard's HTTP request (and
  everything else in `carma-app.service`'s cgroup) before the browser ever
  saw a response.

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
