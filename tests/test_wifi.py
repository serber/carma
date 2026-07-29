import subprocess

from carma import wifi


def _fake_result(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def test_split_terse_unescapes_colons_and_backslashes():
    assert wifi._split_terse(r"My\:Network:80:WPA2:*") == ["My:Network", "80", "WPA2", "*"]
    assert wifi._split_terse(r"back\\slash:1") == ["back\\slash", "1"]


def test_get_status_reports_unavailable_when_nmcli_missing(monkeypatch):
    monkeypatch.setattr(wifi, "available", lambda: False)
    status = wifi.get_status()
    assert status.mode == "unavailable"
    assert status.ssid is None


def test_scan_networks_returns_empty_when_nmcli_missing(monkeypatch):
    monkeypatch.setattr(wifi, "available", lambda: False)
    assert wifi.scan_networks() == []


def test_list_saved_profiles_returns_empty_when_nmcli_missing(monkeypatch):
    monkeypatch.setattr(wifi, "available", lambda: False)
    assert wifi.list_saved_profiles() == []


def test_connect_fails_fast_when_nmcli_missing(monkeypatch):
    monkeypatch.setattr(wifi, "available", lambda: False)
    ok, message = wifi.connect("home", "hunter2")
    assert ok is False
    assert "not available" in message


def test_connect_rejects_blank_ssid(monkeypatch):
    monkeypatch.setattr(wifi, "available", lambda: True)
    ok, message = wifi.connect("   ", "hunter2")
    assert ok is False
    assert "SSID" in message


def test_forget_refuses_the_ap_profile(monkeypatch):
    monkeypatch.setattr(wifi, "available", lambda: True)
    ok, message = wifi.forget(wifi.AP_CONNECTION_NAME)
    assert ok is False
    assert "carma-ap" in message


def test_get_status_parses_client_connection(monkeypatch):
    monkeypatch.setattr(wifi, "available", lambda: True)
    stdout = "GENERAL.CONNECTION:MyHomeWifi\nGENERAL.STATE:100 (connected)\nIP4.ADDRESS[1]:192.168.1.42/24\n"
    monkeypatch.setattr(wifi, "_run", lambda args, timeout: _fake_result(stdout))
    status = wifi.get_status()
    assert status.mode == "client"
    assert status.ssid == "MyHomeWifi"
    assert status.ip_address == "192.168.1.42"


def test_get_status_recognizes_ap_mode(monkeypatch):
    monkeypatch.setattr(wifi, "available", lambda: True)
    stdout = "GENERAL.CONNECTION:carma-ap\nGENERAL.STATE:100 (connected)\nIP4.ADDRESS[1]:192.168.4.1/24\n"
    monkeypatch.setattr(wifi, "_run", lambda args, timeout: _fake_result(stdout))
    status = wifi.get_status()
    assert status.mode == "ap"


def test_get_status_disconnected_when_no_active_connection(monkeypatch):
    monkeypatch.setattr(wifi, "available", lambda: True)
    stdout = "GENERAL.CONNECTION:--\nGENERAL.STATE:20 (unavailable)\nIP4.ADDRESS[1]:\n"
    monkeypatch.setattr(wifi, "_run", lambda args, timeout: _fake_result(stdout))
    status = wifi.get_status()
    assert status.mode == "disconnected"


def test_scan_networks_dedupes_by_strongest_signal_and_excludes_own_ap(monkeypatch):
    monkeypatch.setattr(wifi, "available", lambda: True)
    stdout = "\n".join([
        "HomeWifi:40:WPA2:",
        "HomeWifi:70:WPA2:",
        "carma-ap:90:WPA2:",
        "OpenNet:55::",
    ])
    monkeypatch.setattr(wifi, "_run", lambda args, timeout: _fake_result(stdout))
    networks = wifi.scan_networks()
    assert [n.ssid for n in networks] == ["HomeWifi", "OpenNet"]
    home = next(n for n in networks if n.ssid == "HomeWifi")
    assert home.signal == 70
    assert home.secured is True
    open_net = next(n for n in networks if n.ssid == "OpenNet")
    assert open_net.secured is False


def test_list_saved_profiles_excludes_ap_and_non_wifi(monkeypatch):
    monkeypatch.setattr(wifi, "available", lambda: True)
    stdout = "\n".join([
        "carma-ap:802-11-wireless:no",
        "HomeWifi:802-11-wireless:yes",
        "eth0:802-3-ethernet:yes",
    ])
    monkeypatch.setattr(wifi, "_run", lambda args, timeout: _fake_result(stdout))
    profiles = wifi.list_saved_profiles()
    assert [p.name for p in profiles] == ["HomeWifi"]
    assert profiles[0].autoconnect is True
