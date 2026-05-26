from __future__ import annotations

import subprocess

from apps.desktop.youdub_desktop import environment_check


def _result(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def test_detect_os_name_identifies_windows_10():
    assert environment_check.detect_os_name("Windows", "10", "10.0.19045") == "Windows 10"


def test_detect_os_name_identifies_windows_11():
    assert environment_check.detect_os_name("Windows", "10", "10.0.22631") == "Windows 11"


def test_supported_os_accepts_linux_and_ubuntu():
    assert environment_check.is_supported_os("Ubuntu 24.04 LTS")
    assert environment_check.is_supported_os("Fedora Linux 40")
    assert not environment_check.is_supported_os("Darwin")


def test_has_nvidia_gpu_uses_nvidia_smi():
    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        assert command[0] == "nvidia-smi"
        return _result(stdout="NVIDIA GeForce RTX 4090")

    assert environment_check.has_nvidia_gpu(runner)


def test_has_nvidia_gpu_uses_fallback_commands():
    calls: list[list[str]] = []

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[0] == "lspci":
            return _result(stdout="01:00.0 VGA compatible controller: NVIDIA Corporation")
        raise OSError("not found")

    assert environment_check.has_nvidia_gpu(runner)
    assert [command[0] for command in calls] == ["nvidia-smi", "powershell", "lspci"]


def test_has_nvidia_gpu_returns_false_when_not_detected():
    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        return _result(stdout="Intel UHD Graphics")

    assert not environment_check.has_nvidia_gpu(runner)
