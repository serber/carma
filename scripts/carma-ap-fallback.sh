#!/bin/sh
# Brings up the carma-ap Wi-Fi hotspot if wlan0 hasn't reached a *real*
# client connection within CARMA_WIFI_TIMEOUT seconds of this running (run
# at boot by carma-ap-fallback.service). See README.md "Wi-Fi access
# point" for one-time carma-ap profile setup, and the dashboard's Wi-Fi
# settings page (or `nmcli device wifi connect`) for adding a network to
# actually connect to -- this script only activates carma-ap, it never
# creates or picks a client profile itself.
set -eu

TIMEOUT="${CARMA_WIFI_TIMEOUT:-45}"
AP_PROFILE="carma-ap"
IFACE="wlan0"

if ! nmcli -t -f NAME con show | grep -qx "$AP_PROFILE"; then
    echo "carma-ap-fallback: no '$AP_PROFILE' connection profile found, skipping" >&2
    exit 0
fi

# wlan0's GENERAL.STATE reads 100 ("fully activated") whether it's holding
# a real client connection OR hosting carma-ap itself -- a bare state
# check can't tell "already on real Wi-Fi" apart from "still on the
# hotspot left active from a previous boot", which used to make this
# script permanently defer to a stale AP session instead of ever giving a
# newly-reachable network a chance. Drop carma-ap up front so the loop
# below only ever sees state=100 for a real connection.
active="$(nmcli -t -g GENERAL.CONNECTION device show "$IFACE" 2>/dev/null || true)"
if [ "$active" = "$AP_PROFILE" ]; then
    echo "carma-ap-fallback: $AP_PROFILE was left active, dropping it to retry real Wi-Fi" >&2
    nmcli con down "$AP_PROFILE" || true
fi

i=0
while [ "$i" -lt "$TIMEOUT" ]; do
    state="$(nmcli -t -g GENERAL.STATE device show "$IFACE" 2>/dev/null | cut -d' ' -f1)"
    active="$(nmcli -t -g GENERAL.CONNECTION device show "$IFACE" 2>/dev/null || true)"
    if [ "$state" = "100" ] && [ "$active" != "$AP_PROFILE" ]; then
        echo "carma-ap-fallback: $IFACE already connected to '$active', leaving it alone" >&2
        exit 0
    fi
    sleep 1
    i=$((i + 1))
done

echo "carma-ap-fallback: $IFACE not connected after ${TIMEOUT}s, starting $AP_PROFILE" >&2
nmcli con up "$AP_PROFILE"
