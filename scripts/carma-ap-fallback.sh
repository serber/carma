#!/bin/sh
# Brings up the carma-ap Wi-Fi hotspot if wlan0 hasn't reached a regular
# client connection within CARMA_WIFI_TIMEOUT seconds of this running (run
# at boot by carma-ap-fallback.service). See README.md "Wi-Fi access
# point" for one-time carma-ap profile setup -- this script only activates
# a profile that already exists, it never creates one.
set -eu

TIMEOUT="${CARMA_WIFI_TIMEOUT:-45}"
AP_PROFILE="carma-ap"
IFACE="wlan0"

if ! nmcli -t -f NAME con show | grep -qx "$AP_PROFILE"; then
    echo "carma-ap-fallback: no '$AP_PROFILE' connection profile found, skipping" >&2
    exit 0
fi

i=0
while [ "$i" -lt "$TIMEOUT" ]; do
    state="$(nmcli -t -g GENERAL.STATE device show "$IFACE" 2>/dev/null | cut -d' ' -f1)"
    if [ "$state" = "100" ]; then
        echo "carma-ap-fallback: $IFACE already connected, leaving it alone" >&2
        exit 0
    fi
    sleep 1
    i=$((i + 1))
done

echo "carma-ap-fallback: $IFACE not connected after ${TIMEOUT}s, starting $AP_PROFILE" >&2
nmcli con up "$AP_PROFILE"
