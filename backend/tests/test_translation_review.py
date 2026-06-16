from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app import database
from backend.app.pipeline import PipelineRunner
from backend.app.task_actions import continue_after_review
from backend.app.translation_io import (
    is_translation_reviewed,
    load_translation_segments,
    save_translation_segments,
)


def configure_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.sqlite")
    database.init_db()


def _noop_stage(self, task):
    return None


def test_pipeline_pauses_after_translate_when_review_enabled(monkeypatch, tmp_path):
    configure_db(monkeypatch, tmp_path)
    database.save_translate_settings("openai", review_enabled="true")
    task_id = database.create_task("https://www.youtube.com/watch?v=reviewpause1")
    session = tmp_path / "session"
    metadata = session / "metadata"
    metadata.mkdir(parents=True)
    translation = metadata / "translation.zh.json"

    runner = PipelineRunner(task_id)
    runner.artifacts.session = session
    runner.artifacts.asr_fixed_file = metadata / "asr.fixed.json"
    runner.artifacts.asr_fixed_file.write_text('{"result":{"utterances":[]}}', encoding="utf-8")

    def fake_translate(self, task):
        translation.write_text(
            json.dumps({"translation": [{"src": "hi", "dst": "你好", "start_time": 0, "end_time": 1000}]}),
            encoding="utf-8",
        )
        self.artifacts.translation_file = translation

    for name in ("_download", "_separate", "_asr", "_asr_fix"):
        monkeypatch.setattr(PipelineRunner, name, _noop_stage)
    monkeypatch.setattr(PipelineRunner, "_translate", fake_translate)

    database.update_task(task_id, session_path=str(session), status="running")
    for stage in ("download", "separate", "asr", "asr_fix"):
        database.update_stage(task_id, stage, status="succeeded", completed_at=database.now_iso())

    runner._stage_handlers["translate"] = lambda task: fake_translate(runner, task)
    assert runner._run_stage("translate") is True
    task = database.get_task(task_id)
    assert task["status"] == "awaiting_review"
    assert task["current_stage"] == "translate"


def test_pipeline_resumes_after_translation_review(monkeypatch, tmp_path):
    configure_db(monkeypatch, tmp_path)
    database.save_translate_settings("openai", review_enabled="true")
    task_id = database.create_task("https://www.youtube.com/watch?v=reviewresume1")
    session = tmp_path / "session"
    metadata = session / "metadata"
    metadata.mkdir(parents=True)
    translation = metadata / "translation.zh.json"
    translation.write_text(
        json.dumps({"translation": [{"src": "hi", "dst": "你好", "start_time": 0, "end_time": 1000}]}),
        encoding="utf-8",
    )
    database.update_task(
        task_id,
        session_path=str(session),
        status="awaiting_review",
        current_stage="translate",
    )
    for stage in ("download", "separate", "asr", "asr_fix", "translate"):
        database.update_stage(task_id, stage, status="succeeded", completed_at=database.now_iso())

    final_path = tmp_path / "video_final.mp4"
    visited: list[str] = []

    def prepare_artifacts(self, task):
        self.artifacts.session = session
        self.artifacts.video_file = session / "media" / "video_source.mp4"
        self.artifacts.vocals_file = session / "media" / "audio_vocals.wav"
        self.artifacts.asr_file = metadata / "asr.json"
        self.artifacts.asr_fixed_file = metadata / "asr.fixed.json"
        self.artifacts.translation_file = translation

    for stage_name in ("_download", "_separate", "_asr", "_asr_fix", "_translate"):
        monkeypatch.setattr(PipelineRunner, stage_name, prepare_artifacts)

    for stage_name in ("_split_audio", "_tts", "_merge_audio"):
        def make_handler(name=stage_name):
            def handler(self, task):
                visited.append(name)
            return handler

        monkeypatch.setattr(PipelineRunner, stage_name, make_handler())

    def merge_video(self, task):
        visited.append("_merge_video")
        self.artifacts.final_video = final_path

    monkeypatch.setattr(PipelineRunner, "_merge_video", merge_video)

    continue_after_review(task_id)
    PipelineRunner(task_id).run()

    assert visited == ["_split_audio", "_tts", "_merge_audio", "_merge_video"]
    task = database.get_task(task_id)
    assert task["status"] == "succeeded"
    assert is_translation_reviewed(session)


def test_save_translation_segments_rejects_empty_dst(tmp_path):
    session = tmp_path / "session"
    metadata = session / "metadata"
    metadata.mkdir(parents=True)
    path = metadata / "translation.zh.json"
    path.write_text(json.dumps({"translation": [{"src": "hi", "dst": "你好"}]}), encoding="utf-8")

    with pytest.raises(ValueError, match="cannot be empty"):
        save_translation_segments(path, [{"src": "hi", "dst": "   "}])

    save_translation_segments(path, [{"src": "hi", "dst": "您好"}])
    _, segments = load_translation_segments(session)
    assert segments[0]["dst"] == "您好"
