from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import database, main
from backend.app import mcp_server
from backend.tests.test_settings_and_api import configure_tmp_runtime


def test_mcp_list_tasks_returns_newest_first(monkeypatch, tmp_path):
    configure_tmp_runtime(monkeypatch, tmp_path)
    older = database.create_task("https://www.youtube.com/watch?v=oldvideoidx")
    newer = database.create_task("https://www.youtube.com/watch?v=newvideoidx")

    result = mcp_server.list_tasks()

    assert [task["id"] for task in result["tasks"]] == [newer, older]


def test_mcp_get_task_includes_stages(monkeypatch, tmp_path):
    configure_tmp_runtime(monkeypatch, tmp_path)
    task_id = database.create_task("https://www.youtube.com/watch?v=stagevideo1")

    task = mcp_server.get_task(task_id)

    assert task["id"] == task_id
    assert [stage["name"] for stage in task["stages"]]


def test_mcp_get_task_log_returns_log_text(monkeypatch, tmp_path):
    configure_tmp_runtime(monkeypatch, tmp_path)
    task_id = database.create_task("https://www.youtube.com/watch?v=logvideoidx")
    database.log_path(task_id).write_text("hello from task", encoding="utf-8")

    assert mcp_server.get_task_log(task_id) == "hello from task"


def test_mcp_create_url_task_enqueues_and_dedupes(monkeypatch, tmp_path):
    configure_tmp_runtime(monkeypatch, tmp_path)
    enqueued: list[str] = []
    monkeypatch.setattr(mcp_server.worker, "enqueue", lambda task_id: enqueued.append(task_id))

    first = mcp_server.create_url_task("https://www.youtube.com/watch?v=abcdefghijk")
    second = mcp_server.create_url_task("https://youtu.be/abcdefghijk")

    assert first["id"] == "abcdefghijk"
    assert second["id"] == "abcdefghijk"
    assert enqueued == ["abcdefghijk"]


def test_mcp_create_url_task_rejects_local_upload(monkeypatch, tmp_path):
    configure_tmp_runtime(monkeypatch, tmp_path)

    with pytest.raises(mcp_server.ToolError, match="Only YouTube or Bilibili"):
        mcp_server.create_url_task("local://upload/fake?direction=en-zh")


def test_mcp_rerun_rejects_running_task(monkeypatch, tmp_path):
    configure_tmp_runtime(monkeypatch, tmp_path)
    task_id = database.create_task("https://www.youtube.com/watch?v=runmcpvideo", task_id="runmcpvideo")
    database.update_task(task_id, status="running")

    with pytest.raises(mcp_server.ToolError, match="Cannot rerun a running task"):
        mcp_server.rerun_task(task_id)


def test_mcp_resume_requeues_failed_task(monkeypatch, tmp_path):
    configure_tmp_runtime(monkeypatch, tmp_path)
    enqueued: list[str] = []
    monkeypatch.setattr(mcp_server.worker, "enqueue", lambda task_id: enqueued.append(task_id))
    task_id = database.create_task("https://www.youtube.com/watch?v=resumemcpid", task_id="resumemcpid")
    database.update_task(task_id, status="failed", error_message="boom", completed_at=database.now_iso())
    database.update_stage(task_id, "asr", status="failed", error_message="boom")

    task = mcp_server.resume_task(task_id)

    assert task["status"] == "queued"
    assert enqueued == [task_id]


def test_mcp_server_can_be_disabled(monkeypatch, tmp_path):
    configure_tmp_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("YOUDUB_MCP_ENABLED", "false")
    client = TestClient(main.app)

    response = client.get("/mcp/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "MCP server is disabled."


def test_mcp_allows_requests_without_token(monkeypatch, tmp_path):
    if mcp_server.FastMCP is None:
        pytest.skip("MCP SDK is not installed in this environment.")
    configure_tmp_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("YOUDUB_MCP_ENABLED", "true")
    client = TestClient(main.app)

    response = client.get("/mcp/does-not-exist")

    assert response.status_code != 401
    assert response.status_code != 503
