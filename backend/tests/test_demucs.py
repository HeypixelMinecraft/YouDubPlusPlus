from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.adapters import demucs


def _prepare_demucs_submodule(tmp_path: Path) -> None:
    (tmp_path / "submodule" / "demucs").mkdir(parents=True)


def test_separate_audio_wraps_torch_dll_load_failure(monkeypatch, tmp_path):
    _prepare_demucs_submodule(tmp_path)
    monkeypatch.setattr(demucs, "REPO_ROOT", tmp_path)

    def fail_import(name: str):
        if name == "demucs.api":
            raise OSError('Error loading "torch/lib/c10.dll" or one of its dependencies.')
        raise AssertionError(f"Unexpected import: {name}")

    monkeypatch.setattr(demucs, "import_module", fail_import)

    with pytest.raises(RuntimeError, match="Demucs could not load PyTorch") as error:
        demucs.separate_audio(tmp_path / "video.mp4", tmp_path / "session")

    assert "requirements-torch-cu128.txt" in str(error.value)
    assert "c10.dll" in str(error.value)


def test_separate_audio_wraps_missing_torch(monkeypatch, tmp_path):
    _prepare_demucs_submodule(tmp_path)
    monkeypatch.setattr(demucs, "REPO_ROOT", tmp_path)

    def fail_import(name: str):
        if name == "demucs.api":
            error = ModuleNotFoundError("No module named 'torch'")
            error.name = "torch"
            raise error
        raise AssertionError(f"Unexpected import: {name}")

    monkeypatch.setattr(demucs, "import_module", fail_import)

    with pytest.raises(RuntimeError, match="Demucs could not load PyTorch") as error:
        demucs.separate_audio(tmp_path / "video.mp4", tmp_path / "session")

    assert "Restart the desktop app" in str(error.value)


def test_separate_audio_creates_media_dir_before_save(monkeypatch, tmp_path):
    _prepare_demucs_submodule(tmp_path)
    monkeypatch.setattr(demucs, "REPO_ROOT", tmp_path)
    session = tmp_path / "session"
    saved: list[str] = []

    class FakeSeparator:
        samplerate = 44100

        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def separate_audio_file(self, path: str):
            return None, {"vocals": object(), "drums": object()}

    class FakeApi:
        Separator = FakeSeparator

        @staticmethod
        def save_audio(source, path: str, samplerate: int) -> None:
            saved.append(path)
            Path(path).write_bytes(b"wav")

    monkeypatch.setattr(demucs, "import_module", lambda name: FakeApi if name == "demucs.api" else __import__(name))

    vocals, bgm = demucs.separate_audio(tmp_path / "input.mp4", session)

    assert (session / "media").is_dir()
    assert vocals == session / "media" / "audio_vocals.wav"
    assert bgm == session / "media" / "audio_bgm.wav"
    assert len(saved) == 2
