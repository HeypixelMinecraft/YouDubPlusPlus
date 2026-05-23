from __future__ import annotations

import sys
from types import SimpleNamespace

from backend.app.adapters import whisper_asr


def test_load_model_removes_corrupt_cache_and_retries(monkeypatch, tmp_path):
    calls = {"count": 0}
    model = object()
    cache_file = tmp_path / "tiny.pt"
    cache_file.write_bytes(b"bad")

    def load_model(name, device, download_root=None):
        calls["count"] += 1
        assert name == "tiny"
        assert device == "cpu"
        assert download_root == str(tmp_path)
        if calls["count"] == 1:
            raise RuntimeError("SHA256 checksum does not match")
        return model

    fake_whisper = SimpleNamespace(_MODELS={"tiny": "https://example.com/tiny.pt"}, load_model=load_model)
    monkeypatch.setitem(sys.modules, "whisper", fake_whisper)
    monkeypatch.setenv("WHISPER_MODEL", "tiny")
    monkeypatch.setenv("WHISPER_DOWNLOAD_ROOT", str(tmp_path))
    monkeypatch.setattr(whisper_asr, "_MODEL", None)
    monkeypatch.setattr(whisper_asr, "device", lambda: "cpu")

    assert whisper_asr._load_model() is model
    assert calls["count"] == 2
    assert not cache_file.exists()


def test_whisper_progress_logger_replaces_and_restores_tqdm(monkeypatch):
    class OriginalTqdm:
        pass

    fake_tqdm = SimpleNamespace(tqdm=OriginalTqdm)
    fake_transcribe = SimpleNamespace(tqdm=fake_tqdm)
    monkeypatch.setitem(sys.modules, "whisper.transcribe", fake_transcribe)
    messages: list[str] = []

    with whisper_asr._whisper_progress_logger(messages.append):
        assert fake_tqdm.tqdm is not OriginalTqdm
        with fake_tqdm.tqdm(total=100) as progress:
            progress.update(5)
            progress.update(5)
            progress.update(90)

    assert fake_tqdm.tqdm is OriginalTqdm
    assert messages == [
        "Whisper transcription progress: 0%",
        "Whisper transcription progress: 5%",
        "Whisper transcription progress: 10%",
        "Whisper transcription progress: 100%",
    ]
