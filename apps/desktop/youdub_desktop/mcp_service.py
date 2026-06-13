from __future__ import annotations

import threading
from dataclasses import dataclass
import os
import time

import uvicorn

from backend.app import config as app_config


@dataclass(frozen=True)
class McpServiceInfo:
    host: str
    port: int

    @property
    def sse_url(self) -> str:
        return f"http://{self.host}:{self.port}/mcp/sse"


_server: uvicorn.Server | None = None
_thread: threading.Thread | None = None
_lock = threading.Lock()
_info: McpServiceInfo | None = None
_previous_env: dict[str, str | None] | None = None
_STARTUP_TIMEOUT_SECONDS = 5.0


def is_mcp_service_running() -> bool:
    return bool(_thread and _thread.is_alive())


def current_mcp_service() -> McpServiceInfo | None:
    return _info if is_mcp_service_running() else None


def start_mcp_service(host: str | None = None, port: int | None = None) -> McpServiceInfo | None:
    global _info, _previous_env, _server, _thread
    if not app_config.mcp_enabled():
        return None

    with _lock:
        if _thread and _thread.is_alive():
            return _info

        info = McpServiceInfo(host or app_config.mcp_host(), port or app_config.mcp_port())
        _previous_env = {
            "YOUDUB_DESKTOP_MCP_SERVER": os.environ.get("YOUDUB_DESKTOP_MCP_SERVER"),
            "YOUDUB_MCP_HOST": os.environ.get("YOUDUB_MCP_HOST"),
            "YOUDUB_MCP_PORT": os.environ.get("YOUDUB_MCP_PORT"),
        }
        os.environ["YOUDUB_DESKTOP_MCP_SERVER"] = "1"
        os.environ["YOUDUB_MCP_HOST"] = info.host
        os.environ["YOUDUB_MCP_PORT"] = str(info.port)
        uvicorn_config = uvicorn.Config(
            "backend.app.main:app",
            host=info.host,
            port=info.port,
            log_level="warning",
            access_log=False,
        )
        _server = uvicorn.Server(uvicorn_config)
        _thread = threading.Thread(target=_server.run, name="YouDubMcpServer", daemon=True)
        _thread.start()

    deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        with _lock:
            server = _server
            thread = _thread
        if server is not None and getattr(server, "started", False):
            with _lock:
                _info = info
            return info
        if thread is None or not thread.is_alive():
            break
        time.sleep(0.05)

    stop_mcp_service()
    raise RuntimeError("MCP server failed to start. Check whether the host and port are available.")


def stop_mcp_service() -> None:
    global _previous_env, _server, _thread, _info
    with _lock:
        if _server is not None:
            _server.should_exit = True
        thread = _thread

    if thread and thread.is_alive():
        thread.join(timeout=3.0)

    with _lock:
        _server = None
        _thread = None
        _info = None
        if _previous_env is not None:
            for key, value in _previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        _previous_env = None
