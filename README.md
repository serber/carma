# carma
Raspberry Pi ANPR box: spots and reads passing plates, live Wi-Fi dashboard

See [SPEC.md](SPEC.md) for the full build spec.

See [PLAN.md](PLAN.md) for the atomic build-order steps and current progress.

## Bring-up checklist

_Filled in as each piece lands — see build order in SPEC.md._

- [ ] Flash Raspberry Pi OS Lite (64-bit, Trixie)
- [ ] Wire the CSI camera ribbon cable
- [x] Wi-Fi access-point setup (fixed IP `192.168.4.1`) — see
      [Wi-Fi access point](#wi-fi-access-point) below
- [x] Install carma (`sudo scripts/install.sh`) — creates the `carma` user,
      a venv at `/opt/carma/.venv` (with `--system-site-packages` for
      picamera2), seeds `config.yaml`, pre-downloads the plate-detector and
      OCR models (needs internet once — see `scripts/fetch_models.py`),
      installs + enables the systemd unit
- [ ] Power on, join the Pi's Wi-Fi, open `http://192.168.4.1:8000`
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

## Wi-Fi access point

Raspberry Pi OS switched to **NetworkManager** as the default network stack
starting with Bookworm (Trixie too) — it can run the AP itself, so there's
no need for separate `hostapd`/`dnsmasq` services fighting NetworkManager
for control of `wlan0`. Fewer moving parts matters here: this device won't
have anyone around to fix a broken network stack.

Do this **after** `scripts/install.sh` (which needs internet — run it while
the Pi is still joined to your regular Wi-Fi or on Ethernet). Once the AP
profile is up, the Pi no longer needs a route to the internet.

```sh
sudo nmcli con add type wifi ifname wlan0 con-name carma-ap autoconnect yes ssid carma
sudo nmcli con modify carma-ap 802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 7
sudo nmcli con modify carma-ap wifi-sec.key-mgmt wpa-psk
sudo nmcli con modify carma-ap wifi-sec.psk "<choose-a-real-password>"
sudo nmcli con modify carma-ap ipv4.method shared
sudo nmcli con modify carma-ap ipv4.address 192.168.4.1/24
sudo nmcli con up carma-ap
```

- `autoconnect yes` makes this come up on every boot without a monitor/
  keyboard attached.
- `ipv4.method shared` gives NetworkManager's own internal DHCP to
  connecting clients (dashboard viewers) — no separate dnsmasq needed.
- Verify with `nmcli con show --active` and by joining the `carma` network
  from a phone/laptop and opening `http://192.168.4.1:8000`.
- To go back to a normal Wi-Fi client for maintenance (e.g. re-running
  `scripts/fetch_models.py` after changing the model):
  `sudo nmcli con down carma-ap && sudo nmcli con up <your-home-wifi-profile>`.

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
