from __future__ import annotations

import json
import sys
import types
import wave
from pathlib import Path

import pytest
from pydub import AudioSegment

from backend.app.adapters import index_tts


def _write_wav(path: Path, duration_ms: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    AudioSegment.silent(duration=duration_ms).export(path, format="wav")


def _write_translation(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"translation": items}, ensure_ascii=False), encoding="utf-8")


def _reset_adapter() -> None:
    index_tts._TTS = None
    index_tts._TTS_API = ""


@pytest.fixture(autouse=True)
def reset_index_tts(monkeypatch):
    _reset_adapter()
    for name in ["indextts", "indextts.infer", "indextts.infer_v2"]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    yield
    _reset_adapter()


def test_generate_tts_uses_indextts2_with_reference_fallback_and_silence(monkeypatch, tmp_path):
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    (checkpoints / "config.yaml").write_text("dummy: true\n", encoding="utf-8")

    monkeypatch.setenv("INDEXTTS_MODEL_DIR", str(checkpoints))
    monkeypatch.delenv("INDEXTTS_CFG_PATH", raising=False)
    monkeypatch.setenv("INDEXTTS_MIN_REFERENCE_MS", "1200")
    monkeypatch.setenv("INDEXTTS_USE_FP16", "true")
    monkeypatch.setenv("INDEXTTS_USE_CUDA_KERNEL", "yes")
    monkeypatch.setenv("INDEXTTS_USE_DEEPSPEED", "1")
    monkeypatch.setenv("INDEXTTS_EMO_AUDIO_PROMPT", str(tmp_path / "emotion.wav"))
    monkeypatch.setenv("INDEXTTS_EMO_ALPHA", "0.35")
    monkeypatch.setenv("INDEXTTS_USE_EMO_TEXT", "true")
    monkeypatch.setenv("INDEXTTS_EMO_TEXT", "calm")

    calls: list[dict] = []
    init_kwargs: dict = {}

    class FakeIndexTTS2:
        def __init__(self, **kwargs):
            init_kwargs.update(kwargs)

        def infer(self, **kwargs):
            calls.append(kwargs)
            _write_wav(Path(kwargs["output_path"]), 100)

    package = types.ModuleType("indextts")
    infer_v2 = types.ModuleType("indextts.infer_v2")
    infer_v2.IndexTTS2 = FakeIndexTTS2
    monkeypatch.setitem(sys.modules, "indextts", package)
    monkeypatch.setitem(sys.modules, "indextts.infer_v2", infer_v2)

    vocals_dir = tmp_path / "segments" / "vocals"
    _write_wav(vocals_dir / "0001.wav", 300)
    _write_wav(vocals_dir / "0002.wav", 1500)

    translation_file = tmp_path / "metadata" / "translation.json"
    _write_translation(
        translation_file,
        [
            {"dst": "Hello", "start_time": 0, "end_time": 1000},
            {"dst": "", "start_time": 1000, "end_time": 1200},
            {"dst": "Goodbye", "start_time": 1200, "end_time": 2200},
        ],
    )

    output_dir = index_tts.generate_tts(translation_file, vocals_dir, tmp_path)

    assert output_dir == tmp_path / "segments" / "tts"
    assert sorted(path.name for path in output_dir.glob("*.wav")) == ["0001.wav", "0002.wav", "0003.wav"]
    assert len(calls) == 2
    assert calls[0]["spk_audio_prompt"] == str(vocals_dir / "0002.wav")
    assert calls[0]["text"] == "Hello"
    assert calls[1]["spk_audio_prompt"] == str(vocals_dir / "0002.wav")
    assert calls[1]["text"] == "Goodbye"
    assert calls[0]["emo_audio_prompt"] == str(tmp_path / "emotion.wav")
    assert calls[0]["emo_alpha"] == 0.35
    assert calls[0]["use_emo_text"] is True
    assert calls[0]["emo_text"] == "calm"
    assert init_kwargs == {
        "cfg_path": str(checkpoints / "config.yaml"),
        "model_dir": str(checkpoints),
        "use_fp16": True,
        "use_cuda_kernel": True,
        "use_deepspeed": True,
    }
    with wave.open(str(output_dir / "0002.wav"), "rb") as wav:
        assert wav.getnframes() > 0


def test_load_tts_falls_back_to_v1_when_v2_is_unavailable(monkeypatch, tmp_path):
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    (checkpoints / "config.yaml").write_text("dummy: true\n", encoding="utf-8")
    monkeypatch.setenv("INDEXTTS_MODEL_DIR", str(checkpoints))

    class BrokenIndexTTS2:
        def __init__(self, **kwargs):
            raise RuntimeError("v2 unavailable")

    class FakeIndexTTS:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    package = types.ModuleType("indextts")
    infer_v2 = types.ModuleType("indextts.infer_v2")
    infer_v2.IndexTTS2 = BrokenIndexTTS2
    infer = types.ModuleType("indextts.infer")
    infer.IndexTTS = FakeIndexTTS
    monkeypatch.setitem(sys.modules, "indextts", package)
    monkeypatch.setitem(sys.modules, "indextts.infer_v2", infer_v2)
    monkeypatch.setitem(sys.modules, "indextts.infer", infer)

    tts = index_tts._load_tts()

    assert isinstance(tts, FakeIndexTTS)
    assert tts.kwargs == {
        "model_dir": str(checkpoints),
        "cfg_path": str(checkpoints / "config.yaml"),
    }
    assert index_tts._TTS_API == "v1"


def test_generate_tts_uses_v1_positional_infer(monkeypatch, tmp_path):
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    (checkpoints / "config.yaml").write_text("dummy: true\n", encoding="utf-8")
    monkeypatch.setenv("INDEXTTS_MODEL_DIR", str(checkpoints))
    monkeypatch.setenv("INDEXTTS_CFG_PATH", "")

    calls: list[tuple[str, str, str]] = []

    class FakeIndexTTS:
        def __init__(self, **kwargs):
            pass

        def infer(self, audio_prompt, text, output_path):
            calls.append((audio_prompt, text, output_path))
            _write_wav(Path(output_path), 100)

    package = types.ModuleType("indextts")
    infer = types.ModuleType("indextts.infer")
    infer.IndexTTS = FakeIndexTTS
    monkeypatch.setitem(sys.modules, "indextts", package)
    monkeypatch.setitem(sys.modules, "indextts.infer", infer)

    vocals_dir = tmp_path / "segments" / "vocals"
    _write_wav(vocals_dir / "0001.wav", 1500)
    translation_file = tmp_path / "metadata" / "translation.json"
    _write_translation(translation_file, [{"dst": "Hello", "start_time": 0, "end_time": 1000}])

    output_dir = index_tts.generate_tts(translation_file, vocals_dir, tmp_path)

    assert calls == [(str(vocals_dir / "0001.wav"), "Hello", str(output_dir / "0001.wav"))]
    assert (output_dir / "0001.wav").exists()


def test_load_tts_reports_missing_checkpoints(monkeypatch, tmp_path):
    monkeypatch.setenv("INDEXTTS_MODEL_DIR", str(tmp_path / "missing"))
    monkeypatch.setenv("INDEXTTS_AUTO_DOWNLOAD", "false")

    with pytest.raises(FileNotFoundError, match="INDEXTTS_MODEL_DIR"):
        index_tts._load_tts()
