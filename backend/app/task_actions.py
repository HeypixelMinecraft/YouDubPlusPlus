from __future__ import annotations

import shutil
from pathlib import Path

from . import config, database, worker


def is_inside_workfolder(path: Path) -> bool:
    try:
        path.resolve().relative_to(config.WORKFOLDER.resolve())
        return True
    except ValueError:
        return False


def purge_task(task: dict) -> None:
    session_path = task.get("session_path")
    if session_path:
        session_dir = Path(session_path)
        if session_dir.exists() and is_inside_workfolder(session_dir):
            shutil.rmtree(session_dir)
    log_file = database.log_path(task["id"])
    if log_file.exists():
        log_file.unlink()
    database.delete_task(task["id"])


def rerun_task(task_id: str) -> dict:
    task = database.get_task(task_id)
    if not task:
        raise ValueError("Task not found.")
    if task["status"] == "running":
        raise RuntimeError("Cannot rerun a running task.")

    url = task["url"]
    purge_task(task)
    new_id = database.create_task(url, task_id=task_id)
    worker.enqueue(new_id)
    task = database.get_task(new_id)
    if not task:
        raise RuntimeError("Task was not created.")
    return task


def resume_task(task_id: str) -> dict:
    task = database.get_task(task_id)
    if not task:
        raise ValueError("Task not found.")
    if task["status"] != "failed":
        raise RuntimeError("Only failed tasks can be resumed.")
    database.reset_failed_for_resume(task_id)
    worker.enqueue(task_id)
    task = database.get_task(task_id)
    if not task:
        raise RuntimeError("Task not found.")
    return task


def continue_after_review(task_id: str) -> dict:
    task = database.get_task(task_id)
    if not task:
        raise ValueError("Task not found.")
    if task["status"] != "awaiting_review":
        raise RuntimeError("Task is not awaiting translation review.")
    session_path = task.get("session_path")
    if not session_path:
        raise RuntimeError("Task session is missing.")

    from .translation_io import mark_translation_reviewed

    mark_translation_reviewed(Path(session_path))
    database.update_task(
        task_id,
        status="queued",
        error_message=None,
        completed_at=None,
    )
    worker.enqueue(task_id)
    task = database.get_task(task_id)
    if not task:
        raise RuntimeError("Task not found.")
    return task
