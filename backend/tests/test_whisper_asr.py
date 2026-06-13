from __future__ import annotations

import json
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


def test_recognize_speech_omits_language_for_auto(monkeypatch, tmp_path):
    vocals = tmp_path / "vocals.wav"
    vocals.write_bytes(b"fake wav")
    session = tmp_path / "session"
    seen = {}

    class FakeModel:
        def transcribe(self, audio_path, **kwargs):
            seen["audio_path"] = audio_path
            seen["kwargs"] = kwargs
            return {
                "language": "vi",
                "text": "Xin chao",
                "segments": [
                    {"text": "Xin chao", "start": 0.0, "end": 1.0, "words": []},
                ],
            }

    monkeypatch.setattr(whisper_asr, "_load_model", lambda log=None: FakeModel())
    monkeypatch.setattr(whisper_asr.AudioSegment, "from_file", lambda path: b"0" * 1000)

    out = whisper_asr.recognize_speech(vocals, session, "auto")
    data = json.loads(out.read_text(encoding="utf-8"))

    assert "language" not in seen["kwargs"]
    assert seen["kwargs"]["word_timestamps"] is True
    assert data["result"]["language"] == "vi"


def test_recognize_speech_passes_fixed_language(monkeypatch, tmp_path):
    vocals = tmp_path / "vocals.wav"
    vocals.write_bytes(b"fake wav")
    session = tmp_path / "session"
    seen = {}

    class FakeModel:
        def transcribe(self, audio_path, **kwargs):
            seen["kwargs"] = kwargs
            return {
                "language": "zh",
                "text": "你好",
                "segments": [
                    {"text": "你好", "start": 0.0, "end": 1.0, "words": []},
                ],
            }

    monkeypatch.setattr(whisper_asr, "_load_model", lambda log=None: FakeModel())
    monkeypatch.setattr(whisper_asr.AudioSegment, "from_file", lambda path: b"0" * 1000)

    whisper_asr.recognize_speech(vocals, session, "zh")

    assert seen["kwargs"]["language"] == "zh"
