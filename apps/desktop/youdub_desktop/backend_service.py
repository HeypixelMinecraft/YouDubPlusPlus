from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


class BackendService:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.port = self._find_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.process: subprocess.Popen | None = None

    def start(self) -> None:
        if self.process and self.process.poll() is None:
            return
        command = self._command()
        self.process = subprocess.Popen(
            command,
            cwd=str(self.repo_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._wait_until_ready()

    def stop(self) -> None:
        if not self.process or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()

    def _wait_until_ready(self) -> None:
        deadline = time.time() + 30
        last_error: Exception | None = None
        with httpx.Client(timeout=1.5) as client:
            while time.time() < deadline:
                if self.process and self.process.poll() is not None:
                    raise RuntimeError("Backend exited before it became ready.")
                try:
                    response = client.get(f"{self.base_url}/api/health")
                    if response.status_code == 200:
                        return
                except Exception as exc:  # noqa: BLE001 - surface the final startup error.
                    last_error = exc
                time.sleep(0.4)
        raise RuntimeError(f"Backend did not become ready: {last_error}")

    @staticmethod
    def _find_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _command(self) -> list[str]:
        if getattr(sys, "frozen", False):
            return [sys.executable, "--backend", str(self.port)]
        return [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
        ]
