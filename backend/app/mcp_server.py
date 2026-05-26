from __future__ import annotations

from typing import Any

from starlette.responses import JSONResponse

from . import database, worker
from .task_actions import rerun_task as rerun_existing_task
from .task_actions import resume_task as resume_failed_task
from .youtube import extract_video_id

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.server.fastmcp.exceptions import ToolError
except ImportError:  # pragma: no cover - exercised only when optional runtime dependency is absent.
    FastMCP = None  # type: ignore[assignment]

    class ToolError(RuntimeError):
        pass


def list_tasks(limit: int = 20) -> dict[str, Any]:
    cleaned_limit = max(1, min(int(limit), 100))
    return {"tasks": database.list_tasks(limit=cleaned_limit)}


def get_task(task_id: str) -> dict[str, Any]:
    task = database.get_task(task_id)
    if not task:
        raise ToolError("Task not found.")
    return task


def get_current_task() -> dict[str, Any] | None:
    return database.get_current_task()


def get_task_log(task_id: str) -> str:
    if not database.get_task(task_id):
        raise ToolError("Task not found.")
    path = database.log_path(task_id)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def create_url_task(url: str) -> dict[str, Any]:
    try:
        video_id = extract_video_id(url)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc

    existing_id = database.find_task_by_video_id(video_id)
    if existing_id:
        return get_task(existing_id)

    task_id = database.create_task(url.strip(), task_id=video_id)
    worker.enqueue(task_id)
    return get_task(task_id)


def rerun_task(task_id: str) -> dict[str, Any]:
    try:
        return rerun_existing_task(task_id)
    except (RuntimeError, ValueError) as exc:
        raise ToolError(str(exc)) from exc


def resume_task(task_id: str) -> dict[str, Any]:
    try:
        return resume_failed_task(task_id)
    except (RuntimeError, ValueError) as exc:
        raise ToolError(str(exc)) from exc


async def unavailable_mcp_app(scope, receive, send) -> None:
    response = JSONResponse(
        {"detail": "MCP SDK is not installed. Install the 'mcp' package to enable /mcp."},
        status_code=503,
    )
    await response(scope, receive, send)


def create_mcp_server():
    if FastMCP is None:
        return None

    mcp = FastMCP("YouDubPlusPlus")
    mcp.tool()(list_tasks)
    mcp.tool()(get_task)
    mcp.tool()(get_current_task)
    mcp.tool()(get_task_log)
    mcp.tool()(create_url_task)
    mcp.tool()(rerun_task)
    mcp.tool()(resume_task)
    return mcp


def create_mcp_asgi_app():
    mcp = create_mcp_server()
    if mcp is None:
        return unavailable_mcp_app
    return mcp.sse_app("/mcp")
