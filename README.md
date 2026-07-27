# carma
Raspberry Pi ANPR box: spots and reads passing plates, live Wi-Fi dashboard

See [SPEC.md](SPEC.md) for the full build spec.

## Bring-up checklist

_Filled in as each piece lands — see build order in SPEC.md._

- [ ] Flash Raspberry Pi OS Lite (64-bit, Trixie)
- [ ] Wire the CSI camera ribbon cable
- [ ] `hostapd` + `dnsmasq` access-point setup (fixed IP `192.168.4.1`)
- [ ] Install carma (`scripts/install.sh`), enable the systemd service
- [ ] Power on, join the Pi's Wi-Fi, open `http://192.168.4.1:8000`
- [ ] Confirm the live MJPEG preview and aim the camera
- [ ] `journalctl -u carma -f` to watch structured logs
