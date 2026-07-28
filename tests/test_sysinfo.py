from carma.sysinfo import cpu_temperature_celsius, disk_usage


def test_returns_none_when_thermal_zone_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("carma.sysinfo._THERMAL_ZONE", tmp_path / "does-not-exist")
    assert cpu_temperature_celsius() is None


def test_parses_millidegrees(monkeypatch, tmp_path):
    thermal_zone = tmp_path / "temp"
    thermal_zone.write_text("45123\n")
    monkeypatch.setattr("carma.sysinfo._THERMAL_ZONE", thermal_zone)
    assert cpu_temperature_celsius() == 45.123


def test_returns_none_on_garbage_content(monkeypatch, tmp_path):
    thermal_zone = tmp_path / "temp"
    thermal_zone.write_text("not-a-number")
    monkeypatch.setattr("carma.sysinfo._THERMAL_ZONE", thermal_zone)
    assert cpu_temperature_celsius() is None


def test_disk_usage_on_real_path(tmp_path):
    usage = disk_usage(str(tmp_path))
    assert usage is not None
    assert usage.total_bytes > 0
    assert usage.free_bytes >= 0
    assert usage.used_bytes + usage.free_bytes <= usage.total_bytes


def test_disk_usage_returns_none_for_missing_path(tmp_path):
    assert disk_usage(str(tmp_path / "does" / "not" / "exist")) is None
