# CPU temperature, read from the Pi's thermal zone. Returns None off-Pi
# (e.g. during development on a laptop) so the dashboard can show "n/a"
# instead of crashing.
from __future__ import annotations

from pathlib import Path

_THERMAL_ZONE = Path("/sys/class/thermal/thermal_zone0/temp")


def cpu_temperature_celsius() -> float | None:
    try:
        raw = _THERMAL_ZONE.read_text().strip()
    except OSError:
        return None
    try:
        return int(raw) / 1000.0
    except ValueError:
        return None
