#!/bin/sh
# Root-only helper for the dashboard's Wi-Fi settings page. Invoked by the
# unprivileged carma-svc user via the narrow sudoers rule in
# systemd/carma-wifi.sudoers (see scripts/install.sh) -- carma-svc can run
# *this script* as root, nothing else, so the web app never gets general
# nmcli/root access. Not meant to be run by hand.
set -eu

ACTION="${1:?usage: carma-wifi.sh connect|forget <ssid>}"
SSID="${2:?usage: carma-wifi.sh connect|forget <ssid>}"

case "$ACTION" in
    connect)
        # Password (if any) comes from stdin, not argv, so it never shows
        # up in `ps` output.
        PASSWORD="$(cat)"
        nmcli con down carma-ap >/dev/null 2>&1 || true
        if [ -n "$PASSWORD" ]; then
            nmcli device wifi connect "$SSID" password "$PASSWORD"
        else
            nmcli device wifi connect "$SSID"
        fi
        ;;
    forget)
        nmcli con delete "$SSID"
        ;;
    *)
        echo "carma-wifi.sh: unknown action '$ACTION' (want connect|forget)" >&2
        exit 1
        ;;
esac
