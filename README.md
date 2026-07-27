# carma
Raspberry Pi ANPR box: spots and reads passing plates, live Wi-Fi dashboard

See [SPEC.md](SPEC.md) for the full build spec.

See [PLAN.md](PLAN.md) for the atomic build-order steps and current progress.

## Bring-up checklist

_Filled in as each piece lands — see build order in SPEC.md._

- [ ] Flash Raspberry Pi OS Lite (64-bit, Trixie)
- [ ] Wire the CSI camera ribbon cable
- [ ] `hostapd` + `dnsmasq` access-point setup (fixed IP `192.168.4.1`)
- [x] Install carma (`sudo scripts/install.sh`) — creates the `carma` user,
      a venv at `/opt/carma/.venv` (with `--system-site-packages` for
      picamera2), seeds `config.yaml`, installs + enables the systemd unit
- [ ] Power on, join the Pi's Wi-Fi, open `http://192.168.4.1:8000`
- [x] Confirm the live MJPEG preview and aim the camera — dashboard serves
      `/stream.mjpg`; if the camera fails to open you'll see a red
      "camera unavailable" placeholder instead of a crash, and
      `frames_captured` stays at 0 on `/api/status`
- [x] `journalctl -u carma -f` to watch structured logs — every module logs
      via its own name (`carma.capture.picamera2_source`, `carma.web.app`,
      ...) so the log line tells you which stage is talking

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
