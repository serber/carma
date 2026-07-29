# Wi-Fi status/scan/connect via nmcli, shelled out to from the dashboard's
# Wi-Fi settings page. Status and scanning are read-only and run directly
# as carma-svc; connecting/forgetting a network mutates NetworkManager's
# system connection files, which needs root -- carma-svc doesn't have that
# (see systemd/carma-app.service), so those two go through
# scripts/carma-wifi.sh via the narrow sudoers rule installed by
# scripts/install.sh, instead of calling nmcli directly with elevated
# scope.
from __future__ import annotations

import dataclasses
import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)

# Must match scripts/install.sh's default AP setup / scripts/carma-ap-fallback.sh.
AP_CONNECTION_NAME = "carma-ap"
AP_SSID = "carma-ap"

_IFACE = "wlan0"
_WIFI_HELPER = "/opt/carma-app/scripts/carma-wifi.sh"
_STATUS_TIMEOUT = 15
_SCAN_TIMEOUT = 30
_CONNECT_TIMEOUT = 45


@dataclasses.dataclass(frozen=True)
class WifiStatus:
    mode: str  # "client" | "ap" | "disconnected" | "unavailable"
    ssid: str | None
    ip_address: str | None


@dataclasses.dataclass(frozen=True)
class VisibleNetwork:
    ssid: str
    signal: int
    secured: bool
    in_use: bool


@dataclasses.dataclass(frozen=True)
class SavedProfile:
    name: str
    autoconnect: bool


def available() -> bool:
    return shutil.which("nmcli") is not None


def _split_terse(line: str) -> list[str]:
    """nmcli -t escapes literal ':' and '\\' in field values as '\\:'/'\\\\'
    since ':' is the column separator -- undo that instead of a naive
    line.split(':'), which would mis-split an SSID containing a colon."""
    fields: list[str] = []
    current: list[str] = []
    escape = False
    for ch in line:
        if escape:
            current.append(ch)
            escape = False
        elif ch == "\\":
            escape = True
        elif ch == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(ch)
    fields.append("".join(current))
    return fields


def _run(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


def get_status(iface: str = _IFACE) -> WifiStatus:
    if not available():
        return WifiStatus(mode="unavailable", ssid=None, ip_address=None)
    try:
        result = _run(
            # -f only accepts the base field name -- nmcli rejects the
            # indexed "IP4.ADDRESS[1]" here even though that's the key it
            # prints for that field in the output below.
            ["nmcli", "-t", "-f", "GENERAL.CONNECTION,GENERAL.STATE,IP4.ADDRESS",
             "device", "show", iface],
            _STATUS_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning("nmcli device show %s failed: %s", iface, e)
        return WifiStatus(mode="unavailable", ssid=None, ip_address=None)
    if result.returncode != 0:
        return WifiStatus(mode="unavailable", ssid=None, ip_address=None)

    fields: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, _, value = line.partition(":")
        fields.setdefault(key, value)

    connection = fields.get("GENERAL.CONNECTION", "").strip()
    state = fields.get("GENERAL.STATE", "")
    ip_address = fields.get("IP4.ADDRESS[1]", "").split("/")[0] or None

    if not connection or connection == "--":
        return WifiStatus(mode="disconnected", ssid=None, ip_address=None)
    if connection == AP_CONNECTION_NAME:
        return WifiStatus(mode="ap", ssid=connection, ip_address=ip_address)
    if state.startswith("100"):
        return WifiStatus(mode="client", ssid=connection, ip_address=ip_address)
    return WifiStatus(mode="disconnected", ssid=None, ip_address=None)


def scan_networks() -> list[VisibleNetwork]:
    if not available():
        return []
    try:
        result = _run(
            ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE",
             "device", "wifi", "list", "--rescan", "yes"],
            _SCAN_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning("nmcli wifi scan failed: %s", e)
        return []
    if result.returncode != 0:
        logger.warning("nmcli wifi scan failed: %s", result.stderr.strip())
        return []

    best: dict[str, VisibleNetwork] = {}
    for line in result.stdout.splitlines():
        parts = _split_terse(line)
        if len(parts) < 4:
            continue
        ssid, signal_s, security, in_use = parts[0], parts[1], parts[2], parts[3]
        if not ssid or ssid == AP_SSID:
            continue
        try:
            signal = int(signal_s)
        except ValueError:
            signal = 0
        net = VisibleNetwork(
            ssid=ssid, signal=signal, secured=bool(security.strip()),
            in_use=in_use.strip() == "*",
        )
        # Same SSID can show up once per access point/channel; keep the
        # strongest.
        existing = best.get(ssid)
        if existing is None or net.signal > existing.signal:
            best[ssid] = net
    return sorted(best.values(), key=lambda n: n.signal, reverse=True)


def list_saved_profiles() -> list[SavedProfile]:
    if not available():
        return []
    try:
        result = _run(["nmcli", "-t", "-f", "NAME,TYPE,AUTOCONNECT", "connection", "show"],
                       _STATUS_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning("nmcli connection show failed: %s", e)
        return []
    if result.returncode != 0:
        return []

    profiles = []
    for line in result.stdout.splitlines():
        parts = _split_terse(line)
        if len(parts) < 3:
            continue
        name, conn_type, autoconnect = parts[0], parts[1], parts[2]
        if conn_type != "802-11-wireless" or name == AP_CONNECTION_NAME:
            continue
        profiles.append(SavedProfile(name=name, autoconnect=autoconnect.strip() == "yes"))
    return profiles


def connect(ssid: str, password: str) -> tuple[bool, str]:
    if not available():
        return False, "nmcli is not available on this system"
    ssid = ssid.strip()
    if not ssid:
        return False, "SSID is required"
    try:
        # Password goes over stdin, never argv, so it doesn't show up in
        # `ps` output for other local users while the helper runs.
        result = subprocess.run(
            ["sudo", "-n", _WIFI_HELPER, "connect", ssid],
            input=password, capture_output=True, text=True,
            timeout=_CONNECT_TIMEOUT, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning("wifi connect to %r failed to run helper: %s", ssid, e)
        return False, f"failed to run {_WIFI_HELPER}: {e}"
    ok = result.returncode == 0
    message = (result.stdout + result.stderr).strip() or ("connected" if ok else "connection failed")
    if not ok:
        logger.warning("wifi connect to %r failed: %s", ssid, message)
    return ok, message


def forget(ssid: str) -> tuple[bool, str]:
    if not available():
        return False, "nmcli is not available on this system"
    ssid = ssid.strip()
    if not ssid:
        return False, "SSID is required"
    if ssid == AP_CONNECTION_NAME:
        return False, "refusing to forget the carma-ap hotspot profile"
    try:
        result = subprocess.run(
            ["sudo", "-n", _WIFI_HELPER, "forget", ssid],
            capture_output=True, text=True, timeout=_STATUS_TIMEOUT, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning("wifi forget of %r failed to run helper: %s", ssid, e)
        return False, f"failed to run {_WIFI_HELPER}: {e}"
    ok = result.returncode == 0
    message = (result.stdout + result.stderr).strip() or ("forgotten" if ok else "failed to forget")
    return ok, message
