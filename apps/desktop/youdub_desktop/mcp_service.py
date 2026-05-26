from __future__ import annotations

import threading
from dataclasses import dataclass
import os

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


def is_mcp_service_running() -> bool:
    return bool(_thread and _thread.is_alive())


def current_mcp_service() -> McpServiceInfo | None:
    return _info if is_mcp_service_running() else None


def start_mcp_service(host: str | None = None, port: int | None = None) -> McpServiceInfo | None:
    global _info, _server, _thread
    if not app_config.mcp_enabled():
        return None

    with _lock:
        if _thread and _thread.is_alive():
            return _info

        info = McpServiceInfo(host or app_config.mcp_host(), port or app_config.mcp_port())
        os.environ["YOUDUB_DESKTOP_MCP_SERVER"] = "1"
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
        _info = info
        return info


def stop_mcp_service() -> None:
    global _server, _thread, _info
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
        os.environ.pop("YOUDUB_DESKTOP_MCP_SERVER", None)
