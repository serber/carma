import subprocess

from carma import device


def _fake_result(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_restart_service_calls_helper_with_service_action(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return _fake_result(stdout="ok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok, message = device.restart_service()

    assert ok is True
    assert message == "ok"
    assert captured["args"] == ["sudo", "-n", device._HELPER, "service"]


def test_reboot_device_calls_helper_with_reboot_action(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return _fake_result(stdout="ok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok, message = device.reboot_device()

    assert ok is True
    assert captured["args"] == ["sudo", "-n", device._HELPER, "reboot"]


def test_reports_failure_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: _fake_result(stderr="sudo: a password is required", returncode=1),
    )
    ok, message = device.restart_service()

    assert ok is False
    assert "password is required" in message


def test_reports_failure_when_helper_cannot_be_run(monkeypatch):
    def fake_run(*a, **k):
        raise OSError("no such file or directory")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok, message = device.reboot_device()

    assert ok is False
    assert "failed to run" in message


def test_reports_failure_on_timeout(monkeypatch):
    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired(cmd="carma-restart.sh", timeout=10)

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok, message = device.restart_service()

    assert ok is False
