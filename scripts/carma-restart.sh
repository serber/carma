#!/bin/sh
# Root-only helper for the dashboard's Settings page: restart the carma-app
# service, or reboot the whole device. Invoked by carma-svc via the narrow
# sudoers rule in systemd/carma-restart.sudoers (see scripts/install.sh).
# Not meant to be run by hand.
#
# The actual restart/reboot is scheduled a second out via systemd-run in a
# transient unit of its own, instead of running inline here -- this script
# runs as a child of carma-app.service, and "systemctl restart/reboot"
# would otherwise kill its own calling process (and everything else in
# that service's cgroup) before the dashboard's HTTP response ever makes
# it back to the browser.
set -eu

ACTION="${1:?usage: carma-restart.sh service|reboot}"

case "$ACTION" in
    service)
        systemd-run --on-active=1 --unit="carma-app-restart-$$" --description="carma-app restart requested from dashboard" \
            systemctl restart carma-app
        ;;
    reboot)
        systemd-run --on-active=1 --unit="carma-device-reboot-$$" --description="device reboot requested from dashboard" \
            systemctl reboot
        ;;
    *)
        echo "carma-restart.sh: unknown action '$ACTION' (want service|reboot)" >&2
        exit 1
        ;;
esac
