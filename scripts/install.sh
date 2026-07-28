#!/usr/bin/env bash
# Installs carma to /opt/carma and enables the systemd service. Run as root
# on Raspberry Pi OS Lite (64-bit, Trixie) after cloning this repo.
# See README.md for the full bring-up checklist.
set -euo pipefail

INSTALL_DIR="/opt/carma"
# Deliberately not "carma" -- that collides with a common choice of Pi
# login username (especially likely here, it's the project name), which
# silently skips useradd below and runs the service as your own login
# account (no isolation, wrong $HOME, breaks the offline model cache).
SERVICE_USER="carma-svc"
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

# HOME must match what the systemd unit's User=carma resolves to
# (/opt/carma), so the model ends up cached where the service actually
# looks for it at runtime -- otherwise it'd cache under root's home here
# and the device would try (and fail) to download again offline on first
# boot.
echo "==> pre-downloading the plate detector model (needs internet once)"
HOME="$INSTALL_DIR" "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/scripts/fetch_models.py" \
    --config "$INSTALL_DIR/config.yaml"

mkdir -p "$INSTALL_DIR/data/images" "$INSTALL_DIR/models"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

echo "==> installing systemd unit"
cp "$INSTALL_DIR/systemd/carma.service" /etc/systemd/system/carma.service
systemctl daemon-reload
systemctl enable carma

cat <<MSG
==> done.
    - review $INSTALL_DIR/config.yaml (camera backend/resolution, dashboard port)
    - the plate detector model was pre-downloaded and cached; re-run
      scripts/fetch_models.py after changing detection.model_name
    - start it:   systemctl start carma
    - watch it:   journalctl -u carma -f
MSG
