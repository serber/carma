# Service/device restart, shelled out to from the dashboard's Settings
# page. Both need root (systemctl restart/reboot), which the dashboard's
# carma-svc user doesn't have (see systemd/carma-app.service) -- goes
# through scripts/carma-restart.sh via the narrow sudoers rule installed by
# scripts/install.sh, same pattern as carma/wifi.py.
from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)

_HELPER = "/opt/carma-app/scripts/carma-restart.sh"
_TIMEOUT = 10


def _run(action: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["sudo", "-n", _HELPER, action],
            capture_output=True, text=True, timeout=_TIMEOUT, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning("%s failed to run helper: %s", action, e)
        return False, f"failed to run {_HELPER}: {e}"
    ok = result.returncode == 0
    message = (result.stdout + result.stderr).strip() or ("scheduled" if ok else "failed")
    if not ok:
        logger.warning("%s failed: %s", action, message)
    return ok, message


def restart_service() -> tuple[bool, str]:
    return _run("service")


def reboot_device() -> tuple[bool, str]:
    return _run("reboot")
