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
