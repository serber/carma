# CPU temperature + disk usage. Both return None on failure (missing
# thermal zone off-Pi, a storage path that doesn't exist yet) so the
# dashboard can show "n/a" instead of crashing.
from __future__ import annotations

import dataclasses
import shutil
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


@dataclasses.dataclass(frozen=True)
class DiskUsage:
    total_bytes: int
    used_bytes: int
    free_bytes: int


def disk_usage(path: str) -> DiskUsage | None:
    """Usage of the filesystem holding `path` (typically storage.images_dir
    -- the dominant space consumer, and usually on the same partition as
    the SQLite db on a single-SD-card Pi)."""
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    return DiskUsage(total_bytes=usage.total, used_bytes=usage.used, free_bytes=usage.free)
