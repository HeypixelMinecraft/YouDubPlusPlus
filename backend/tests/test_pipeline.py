from __future__ import annotations

from pathlib import Path

from backend.app import database
from backend.app.pipeline import PipelineRunner


def configure_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.sqlite")
    database.init_db()


def _noop_stage(self, task):
    return None


def test_pipeline_marks_all_stages_succeeded(monkeypatch, tmp_path):
    configure_db(monkeypatch, tmp_path)
    task_id = database.create_task("https://www.youtube.com/watch?v=abcdefghijk")
    final_path = tmp_path / "video_final.mp4"
    final_path.write_bytes(b"mp4")

    for name in ("_download", "_separate", "_asr", "_asr_fix", "_translate", "_split_audio", "_tts", "_merge_audio"):
        monkeypatch.setattr(PipelineRunner, name, _noop_stage)

    def merge_video(self, task):
        self.artifacts.final_video = final_path

    monkeypatch.setattr(PipelineRunner, "_merge_video", merge_video)

    PipelineRunner(task_id).run()
    task = database.get_task(task_id)

    assert task["status"] == "succeeded"
    assert task["final_video_path"] == str(final_path)
    assert [stage["status"] for stage in task["stages"]] == ["succeeded"] * 9


def test_pipeline_skips_already_succeeded_stages(monkeypatch, tmp_path):
    configure_db(monkeypatch, tmp_path)
    task_id = database.create_task("https://www.youtube.com/watch?v=resumevidxxx", task_id="resumevidxxx")
    final_path = tmp_path / "video_final.mp4"
    final_path.write_bytes(b"mp4")

    for name in ("download", "separate", "asr"):
        database.update_stage(task_id, name, status="succeeded", completed_at=database.now_iso())

    visited: list[str] = []
    for stage_name in ("_download", "_separate", "_asr", "_asr_fix", "_translate", "_split_audio", "_tts", "_merge_audio"):
        def make_handler(name=stage_name):
            def handler(self, task):
                visited.append(name)
            return handler
        monkeypatch.setattr(PipelineRunner, stage_name, make_handler())

    def merge_video(self, task):
        visited.append("_merge_video")
        self.artifacts.final_video = final_path

    monkeypatch.setattr(PipelineRunner, "_merge_video", merge_video)

    PipelineRunner(task_id).run()

    assert visited == [
        "_download", "_separate", "_asr",
        "_asr_fix", "_translate", "_split_audio", "_tts", "_merge_audio", "_merge_video",
    ]
    task = database.get_task(task_id)
    assert task["status"] == "succeeded"


def test_pipeline_failure_stops_following_stages(monkeypatch, tmp_path):
    configure_db(monkeypatch, tmp_path)
    task_id = database.create_task("https://www.youtube.com/watch?v=abcdefghijk")

    monkeypatch.setattr(PipelineRunner, "_download", _noop_stage)
    monkeypatch.setattr(PipelineRunner, "_separate", _noop_stage)

    def fail_asr(self, task):
        raise RuntimeError("asr exploded")

    monkeypatch.setattr(PipelineRunner, "_asr", fail_asr)

    PipelineRunner(task_id).run()
    task = database.get_task(task_id)
    stages = {stage["name"]: stage for stage in task["stages"]}

    assert task["status"] == "failed"
    assert stages["asr"]["status"] == "failed"
    assert stages["translate"]["status"] == "pending"
    assert task["error_message"] == "asr exploded"


def test_tts_stage_uses_configured_tts_adapter(monkeypatch, tmp_path):
    from backend.app.adapters import tts

    configure_db(monkeypatch, tmp_path)
    task_id = database.create_task("https://www.youtube.com/watch?v=abcdefghijk")
    runner = PipelineRunner(task_id)
    runner.artifacts.session = tmp_path
    runner.artifacts.translation_file = tmp_path / "metadata" / "translation.json"
    runner.artifacts.vocals_dir = tmp_path / "segments" / "vocals"
    output_dir = tmp_path / "segments" / "tts"
    called = {}

    def fake_generate_tts(translation_file, vocals_dir, session):
        called["args"] = (translation_file, vocals_dir, session)
        output_dir.mkdir(parents=True)
        (output_dir / "0001.wav").write_bytes(b"wav")
        return output_dir, "FakeTTS"

    monkeypatch.setattr(tts, "generate_tts", fake_generate_tts)

    runner._tts(database.get_task(task_id))

    assert called["args"] == (
        runner.artifacts.translation_file,
        runner.artifacts.vocals_dir,
        runner.artifacts.session,
    )
    assert runner.artifacts.tts_dir == output_dir

