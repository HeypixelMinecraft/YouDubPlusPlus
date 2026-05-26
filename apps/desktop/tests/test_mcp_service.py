from __future__ import annotations

import os

from apps.desktop.youdub_desktop import mcp_service


class FakeServer:
    def __init__(self, config):
        self.config = config
        self.should_exit = False

    def run(self) -> None:
        return None


def reset_service_state() -> None:
    mcp_service._server = None
    mcp_service._thread = None
    mcp_service._info = None


def test_start_mcp_service_returns_desktop_url(monkeypatch):
    reset_service_state()
    monkeypatch.setenv("YOUDUB_MCP_ENABLED", "true")
    monkeypatch.setenv("YOUDUB_MCP_HOST", "127.0.0.2")
    monkeypatch.setenv("YOUDUB_MCP_PORT", "9876")
    monkeypatch.setattr(mcp_service.uvicorn, "Server", FakeServer)

    info = mcp_service.start_mcp_service()

    assert info is not None
    assert info.sse_url == "http://127.0.0.2:9876/mcp/sse"
    assert mcp_service._server is not None
    assert mcp_service._server.config.host == "127.0.0.2"
    assert mcp_service._server.config.port == 9876
    mcp_service.stop_mcp_service()


def test_start_mcp_service_respects_disabled_setting(monkeypatch):
    reset_service_state()
    monkeypatch.setenv("YOUDUB_MCP_ENABLED", "false")

    assert mcp_service.start_mcp_service() is None


def test_stop_mcp_service_marks_server_for_shutdown(monkeypatch):
    reset_service_state()
    monkeypatch.setenv("YOUDUB_MCP_ENABLED", "true")
    monkeypatch.setattr(mcp_service.uvicorn, "Server", FakeServer)
    mcp_service.start_mcp_service()
    server = mcp_service._server

    mcp_service.stop_mcp_service()

    assert server is not None
    assert server.should_exit is True
    assert "YOUDUB_DESKTOP_MCP_SERVER" not in os.environ
