from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class EnvironmentCheckResult:
    os_name: str
    supported_os: bool
    has_nvidia_gpu: bool


def unsupported_os_message(os_name: str) -> str:
    return (
        f"Unsupported system detected: {os_name}.\n"
        "YouDubPlusPlus desktop requires Windows 10/11, Linux, or Ubuntu."
    )


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=True,
        timeout=3,
    )


def _linux_pretty_name(os_release_path: Path = Path("/etc/os-release")) -> str:
    if not os_release_path.exists():
        return "Linux"
    values: dict[str, str] = {}
    for line in os_release_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        values[key] = value.strip().strip('"')
    return values.get("PRETTY_NAME") or values.get("NAME") or "Linux"


def detect_os_name(system: str | None = None, release: str | None = None, version: str | None = None) -> str:
    current_system = system or platform.system()
    current_release = release or platform.release()
    current_version = version or platform.version()

    if current_system == "Windows":
        build = 0
        try:
            build = int(current_version.split(".")[-1])
        except (TypeError, ValueError):
            pass
        if current_release == "10" and build >= 22000:
            return "Windows 11"
        if current_release == "10":
            return "Windows 10"
        return f"Windows {current_release}".strip()
    if current_system == "Linux":
        return _linux_pretty_name()
    return current_system or "Unknown"


def is_supported_os(os_name: str) -> bool:
    lowered = os_name.lower()
    return lowered in {"windows 10", "windows 11"} or "linux" in lowered or "ubuntu" in lowered


def has_nvidia_gpu(command_runner: CommandRunner = _run_command) -> bool:
    for command in (
        ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
        ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
        ["lspci"],
    ):
        try:
            result = command_runner(command)
        except (OSError, subprocess.SubprocessError):
            continue
        output = f"{result.stdout}\n{result.stderr}".lower()
        if result.returncode == 0 and "nvidia" in output:
            return True
    return False


def check_desktop_environment(command_runner: CommandRunner = _run_command) -> EnvironmentCheckResult:
    os_name = detect_os_name()
    return EnvironmentCheckResult(
        os_name=os_name,
        supported_os=is_supported_os(os_name),
        has_nvidia_gpu=has_nvidia_gpu(command_runner),
    )
