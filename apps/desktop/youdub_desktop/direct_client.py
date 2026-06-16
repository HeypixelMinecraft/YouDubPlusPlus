from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pydub import AudioSegment

from backend.app import database, worker
from backend.app.adapters.local_video import remove_upload, upload_dir
from backend.app.adapters.openai_translate import list_models as list_openai_models
from backend.app.config import WORKFOLDER, YOUTUBE_COOKIE_PATH, ensure_runtime_dirs
from backend.app.pipeline import run_task
from backend.app.sanitize import sanitize_text
from backend.app.task_actions import continue_after_review
from backend.app.translation_io import load_translation_segments, save_translation_segments
from backend.app.youtube import extract_video_id, is_local_upload_url


ALLOWED_VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".flv", ".wmv"}
LOCAL_UPLOAD_DIRECTIONS = {"en-zh", "zh-en"}
_STARTED = False


class DirectClient:
    def __init__(self) -> None:
        global _STARTED
        ensure_runtime_dirs()
        database.init_db()
        database.backfill_titles_from_metadata()
        if not _STARTED:
            database.fail_stale_active_tasks()
            worker.start(run_task)
            _STARTED = True

    def list_tasks(self, limit: int = 100) -> list[dict[str, Any]]:
        return database.list_tasks(limit=limit)

    def get_task(self, task_id: str) -> dict[str, Any]:
        task = database.get_task(task_id)
        if not task:
            raise RuntimeError("Task not found.")
        return task

    def get_log(self, task_id: str) -> str:
        path = database.log_path(task_id)
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def create_task(self, url: str) -> dict[str, Any]:
        video_id = extract_video_id(url)
        existing_id = database.find_task_by_video_id(video_id)
        if existing_id:
            return self.get_task(existing_id)
        task_id = database.create_task(url.strip(), task_id=video_id)
        worker.enqueue(task_id)
        return self.get_task(task_id)

    def upload_task(self, file_path: Path, direction: str) -> dict[str, Any]:
        if direction not in LOCAL_UPLOAD_DIRECTIONS:
            raise RuntimeError("Unsupported local video direction.")
        if not file_path.exists() or file_path.suffix.lower() not in ALLOWED_VIDEO_SUFFIXES:
            raise RuntimeError("Unsupported video file type.")

        task_id = str(uuid.uuid4())
        target_dir = upload_dir(WORKFOLDER, task_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_stem = sanitize_text(file_path.stem) or "video"
        target = target_dir / f"{safe_stem}{file_path.suffix.lower()}"
        shutil.copy2(file_path, target)

        url = f"local://upload/{task_id}?direction={direction}&filename={quote(file_path.name)}"
        database.create_task(url, task_id=task_id)
        database.update_task(task_id, title=file_path.stem)
        worker.enqueue(task_id)
        return self.get_task(task_id)

    def delete_task(self, task_id: str) -> None:
        task = self.get_task(task_id)
        if task["status"] == "running":
            raise RuntimeError("Cannot delete a running task.")
        session_path = task.get("session_path")
        if session_path:
            session_dir = Path(session_path)
            if session_dir.exists() and _is_inside_workfolder(session_dir):
                shutil.rmtree(session_dir)
        log_file = database.log_path(task_id)
        if log_file.exists():
            log_file.unlink()
        database.delete_task(task_id)
        if is_local_upload_url(task["url"]):
            remove_upload(WORKFOLDER, task_id)

    def rerun_task(self, task_id: str) -> dict[str, Any]:
        task = self.get_task(task_id)
        if task["status"] == "running":
            raise RuntimeError("Cannot rerun a running task.")
        url = task["url"]
        self.delete_task(task_id)
        new_id = database.create_task(url, task_id=task_id)
        worker.enqueue(new_id)
        return self.get_task(new_id)

    def resume_task(self, task_id: str) -> dict[str, Any]:
        task = self.get_task(task_id)
        if task["status"] != "failed":
            raise RuntimeError("Only failed tasks can be resumed.")
        database.reset_failed_for_resume(task_id)
        worker.enqueue(task_id)
        return self.get_task(task_id)

    def get_cookie_info(self) -> dict[str, Any]:
        exists = YOUTUBE_COOKIE_PATH.exists()
        return {
            "exists": exists,
            "size": YOUTUBE_COOKIE_PATH.stat().st_size if exists else 0,
            "updated_at": YOUTUBE_COOKIE_PATH.stat().st_mtime if exists else None,
            "content": "",
        }

    def save_cookie(self, content: str) -> dict[str, Any]:
        YOUTUBE_COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
        cleaned = content.strip()
        if cleaned:
            YOUTUBE_COOKIE_PATH.write_text(cleaned + "\n", encoding="utf-8")
        elif YOUTUBE_COOKIE_PATH.exists():
            YOUTUBE_COOKIE_PATH.unlink()
        return self.get_cookie_info()

    def get_openai_settings(self) -> dict[str, Any]:
        settings = database.get_openai_settings()
        return {
            "base_url": settings["base_url"],
            "api_key": "********" if settings["api_key"] else "",
            "has_api_key": bool(settings["api_key"]),
            "model": settings["model"],
            "translate_concurrency": settings["translate_concurrency"],
        }

    def save_openai_settings(self, settings: dict[str, str]) -> dict[str, Any]:
        database.save_openai_settings(
            settings.get("base_url", ""),
            settings.get("api_key", ""),
            settings.get("model", ""),
            settings.get("translate_concurrency", ""),
        )
        return self.get_openai_settings()

    def list_models(self, base_url: str, api_key: str) -> list[str]:
        settings = database.get_openai_settings()
        return list_openai_models(base_url=base_url or settings["base_url"], api_key=api_key or settings["api_key"])

    def get_translate_settings(self) -> dict[str, Any]:
        return database.get_translate_settings()

    def save_translate_settings(self, mode: str, review_enabled: str | None = None) -> dict[str, Any]:
        try:
            database.save_translate_settings(mode, review_enabled=review_enabled)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
        return self.get_translate_settings()

    def get_ytdlp_settings(self) -> dict[str, Any]:
        return database.get_ytdlp_settings()

    def save_ytdlp_settings(self, proxy_port: str) -> dict[str, Any]:
        cleaned = proxy_port.strip()
        if cleaned and (not cleaned.isdigit() or not 1 <= int(cleaned) <= 65535):
            raise RuntimeError("Proxy port must be between 1 and 65535.")
        database.save_ytdlp_settings(cleaned)
        return self.get_ytdlp_settings()

    def synthesize_tts(
        self,
        text: str,
        reference_path: Path,
        output_path: Path | None = None,
    ) -> dict[str, Any]:
        cleaned = text.strip()
        if not cleaned:
            raise RuntimeError("Text is required.")
        reference = reference_path.resolve()
        if not reference.exists():
            raise RuntimeError("Reference audio not found.")

        min_reference_ms = int(os.getenv("VOXCPM_MIN_REFERENCE_MS", "1200"))
        duration_ms = len(AudioSegment.from_file(reference))
        if duration_ms < min_reference_ms:
            raise RuntimeError(f"Reference audio must be at least {min_reference_ms} ms.")

        out_dir = WORKFOLDER / "tts_tool"
        out_dir.mkdir(parents=True, exist_ok=True)
        if output_path is None:
            stem = sanitize_text(cleaned[:40]) or "tts"
            target = out_dir / f"{stem}.wav"
            if target.exists():
                target = out_dir / f"{stem}_{uuid.uuid4().hex[:8]}.wav"
        else:
            target = output_path.resolve()
            target.parent.mkdir(parents=True, exist_ok=True)

        log_lines: list[str] = []

        def log(message: str) -> None:
            log_lines.append(message)

        from backend.app.adapters.tts import synthesize_speech

        backend = synthesize_speech(cleaned, reference, target, log=log)
        return {
            "output_path": str(target),
            "backend": backend,
            "log": "\n".join(log_lines),
        }

    def separate_vocals(self, media_path: Path) -> dict[str, Any]:
        media = media_path.resolve()
        if not media.exists():
            raise RuntimeError("Media file not found.")

        session = WORKFOLDER / "audio_tool" / "separate" / f"{sanitize_text(media.stem) or 'media'}_{uuid.uuid4().hex[:8]}"
        session.mkdir(parents=True, exist_ok=True)

        log_lines: list[str] = []

        def log(message: str) -> None:
            log_lines.append(message)

        from backend.app.adapters.demucs import separate_audio

        vocals_file, bgm_file = separate_audio(media, session, log=log)
        return {
            "session_path": str(session),
            "vocals_path": str(vocals_file),
            "bgm_path": str(bgm_file),
            "log": "\n".join(log_lines),
        }

    def split_audio_segments(self, audio_path: Path, segments_path: Path) -> dict[str, Any]:
        audio = audio_path.resolve()
        segments = segments_path.resolve()
        if not audio.exists():
            raise RuntimeError("Audio file not found.")
        if not segments.exists():
            raise RuntimeError("Segments JSON not found.")

        session = WORKFOLDER / "audio_tool" / "split" / f"{sanitize_text(audio.stem) or 'audio'}_{uuid.uuid4().hex[:8]}"
        session.mkdir(parents=True, exist_ok=True)

        log_lines: list[str] = []

        def log(message: str) -> None:
            log_lines.append(message)

        from backend.app.adapters.audio import split_audio_by_segments_file

        output_dir = split_audio_by_segments_file(audio, segments, session)
        segment_count = len(list(output_dir.glob("*.wav")))
        log(f"Created {segment_count} audio segments -> {output_dir}")
        return {
            "session_path": str(session),
            "output_dir": str(output_dir),
            "segment_count": segment_count,
            "log": "\n".join(log_lines),
        }

    def get_task_translation(self, task_id: str) -> dict[str, Any]:
        task = self.get_task(task_id)
        session_path = task.get("session_path")
        if not session_path:
            raise RuntimeError("Task session is missing.")
        path, segments = load_translation_segments(Path(session_path))
        return {"path": str(path), "segments": segments}

    def save_task_translation(self, task_id: str, segments: list[dict[str, Any]]) -> dict[str, Any]:
        task = self.get_task(task_id)
        if task["status"] != "awaiting_review":
            raise RuntimeError("Translation can only be edited while awaiting review.")
        session_path = task.get("session_path")
        if not session_path:
            raise RuntimeError("Task session is missing.")
        path, _ = load_translation_segments(Path(session_path))
        try:
            save_translation_segments(path, segments)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
        return self.get_task_translation(task_id)

    def continue_after_review(self, task_id: str) -> dict[str, Any]:
        try:
            return continue_after_review(task_id)
        except ValueError as exc:
            raise RuntimeError("Task not found.") from exc
        except RuntimeError:
            raise


def _is_inside_workfolder(path: Path) -> bool:
    try:
        path.resolve().relative_to(WORKFOLDER.resolve())
        return True
    except ValueError:
        return False
