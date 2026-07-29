#!/usr/bin/env bash
# Installs carma to /opt/carma-app and enables the systemd service. Run as
# root on Raspberry Pi OS Lite (64-bit, Trixie) after cloning this repo --
# or via scripts/bootstrap.sh for a one-command clone+install.
# See README.md for the full bring-up checklist.
set -euo pipefail

SERVICE_NAME="carma-app"
INSTALL_DIR="/opt/$SERVICE_NAME"
# Deliberately not "carma" -- that collides with a common choice of Pi
# login username (especially likely here, it's the project name), which
# silently skips useradd below and runs the service as your own login
# account (no isolation, wrong $HOME, breaks the offline model cache).
SERVICE_USER="carma-svc"
# Fixed defaults for the carma-ap hotspot, overridable via env vars, so a
# fresh install never needs interactive input. See README.md "Wi-Fi access
# point" for what these mean and how to change them post-install.
AP_CON_NAME="carma-ap"
AP_SSID="${CARMA_AP_SSID:-carma-ap}"
AP_PASSWORD="${CARMA_AP_PASSWORD:-carmapwd}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
    echo "run as root (sudo $0)" >&2
    exit 1
fi

echo "==> installing system packages (picamera2, venv, camera libs)"
apt-get update
apt-get install -y --no-install-recommends \
    python3-venv python3-picamera2 python3-opencv libcap-dev

if id -u "$SERVICE_USER" >/dev/null 2>&1; then
    existing_home="$(getent passwd "$SERVICE_USER" | cut -d: -f6)"
    if [[ "$existing_home" != "$INSTALL_DIR" ]]; then
        echo "error: user '$SERVICE_USER' already exists with home '$existing_home', expected '$INSTALL_DIR'." >&2
        echo "Running the service as this account would use the wrong \$HOME (breaks the offline model cache) and skip the isolation this script is meant to set up. Pick a different SERVICE_USER, or remove/rename the conflicting account." >&2
        exit 1
    fi
else
    echo "==> creating service user $SERVICE_USER"
    useradd --system --home "$INSTALL_DIR" --groups video --shell /usr/sbin/nologin "$SERVICE_USER"
fi

echo "==> copying repo to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
rsync -a --exclude .venv --exclude .git --exclude data "$REPO_DIR"/ "$INSTALL_DIR"/

echo "==> creating venv (system site packages, needed for picamera2)"
python3 -m venv --system-site-packages "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install "$INSTALL_DIR"

if [[ ! -f "$INSTALL_DIR/config.yaml" ]]; then
    echo "==> seeding config.yaml from config.example.yaml"
    cp "$INSTALL_DIR/config.example.yaml" "$INSTALL_DIR/config.yaml"
fi

# HOME must match what the systemd unit's User=carma-svc resolves to
# ($INSTALL_DIR), so the model ends up cached where the service actually
# looks for it at runtime -- otherwise it'd cache under root's home here
# and the device would try (and fail) to download again offline on first
# boot.
echo "==> pre-downloading the plate detector model (needs internet once)"
HOME="$INSTALL_DIR" "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/scripts/fetch_models.py" \
    --config "$INSTALL_DIR/config.yaml"

mkdir -p "$INSTALL_DIR/data/images" "$INSTALL_DIR/models"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

echo "==> installing systemd units"
chmod +x "$INSTALL_DIR/scripts/carma-ap-fallback.sh"
cp "$INSTALL_DIR/systemd/$SERVICE_NAME.service" "/etc/systemd/system/$SERVICE_NAME.service"
cp "$INSTALL_DIR/systemd/carma-ap-fallback.service" /etc/systemd/system/carma-ap-fallback.service
systemctl daemon-reload
systemctl enable "$SERVICE_NAME" carma-ap-fallback

echo "==> installing Wi-Fi settings helper (lets the dashboard join a new network)"
chmod +x "$INSTALL_DIR/scripts/carma-wifi.sh"
install -m 0440 "$INSTALL_DIR/systemd/carma-wifi.sudoers" /etc/sudoers.d/carma-wifi
if ! visudo -c -f /etc/sudoers.d/carma-wifi >/dev/null; then
    echo "error: generated /etc/sudoers.d/carma-wifi failed validation, removing it" >&2
    rm -f /etc/sudoers.d/carma-wifi
    exit 1
fi

echo "==> installing restart/reboot helper (lets the dashboard restart the service or the device)"
chmod +x "$INSTALL_DIR/scripts/carma-restart.sh"
install -m 0440 "$INSTALL_DIR/systemd/carma-restart.sudoers" /etc/sudoers.d/carma-restart
if ! visudo -c -f /etc/sudoers.d/carma-restart >/dev/null; then
    echo "error: generated /etc/sudoers.d/carma-restart failed validation, removing it" >&2
    rm -f /etc/sudoers.d/carma-restart
    exit 1
fi

if ! command -v nmcli >/dev/null 2>&1; then
    echo "==> nmcli not found, skipping $AP_CON_NAME hotspot setup (set it up manually later, see README.md)"
elif nmcli -t -f NAME con show | grep -qx "$AP_CON_NAME"; then
    echo "==> $AP_CON_NAME Wi-Fi profile already exists, leaving it alone"
else
    echo "==> creating the $AP_CON_NAME hotspot profile (ssid=$AP_SSID, autoconnect no)"
    nmcli con add type wifi ifname wlan0 con-name "$AP_CON_NAME" autoconnect no ssid "$AP_SSID"
    nmcli con modify "$AP_CON_NAME" 802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 7
    nmcli con modify "$AP_CON_NAME" wifi-sec.key-mgmt wpa-psk
    nmcli con modify "$AP_CON_NAME" wifi-sec.psk "$AP_PASSWORD"
    nmcli con modify "$AP_CON_NAME" ipv4.method shared
    nmcli con modify "$AP_CON_NAME" ipv4.address 192.168.4.1/24
fi

cat <<MSG
==> done.
    - review $INSTALL_DIR/config.yaml (camera backend/resolution, dashboard port)
    - the plate detector model was pre-downloaded and cached; re-run
      scripts/fetch_models.py after changing detection.model_name
    - start it:   systemctl start $SERVICE_NAME
    - watch it:   journalctl -u $SERVICE_NAME -f
    - hotspot:    $AP_SSID / $AP_PASSWORD at 192.168.4.1:8000 (only comes up
                  automatically if no known Wi-Fi is reachable at boot --
                  see carma-ap-fallback.service)
MSG
