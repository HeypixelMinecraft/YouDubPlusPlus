from __future__ import annotations

import sys
from importlib import import_module
from io import StringIO
from pathlib import Path
from typing import Any, Callable

from ..config import REPO_ROOT, device


def _device() -> str:
    value = device()
    if value != "auto":
        return value
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _disable_demucs_tqdm() -> None:
    try:
        demucs_apply = import_module("demucs.apply")
    except Exception:
        return

    tqdm_module = getattr(demucs_apply, "tqdm", None)
    tqdm_fn: Callable[..., Any] | None = getattr(tqdm_module, "tqdm", None)
    if tqdm_fn is None or getattr(tqdm_fn, "_youdub_disabled", False):
        return

    def quiet_tqdm(*args: Any, **kwargs: Any) -> Any:
        kwargs["disable"] = True
        kwargs.setdefault("file", sys.stderr or StringIO())
        return tqdm_fn(*args, **kwargs)

    quiet_tqdm._youdub_disabled = True  # type: ignore[attr-defined]
    tqdm_module.tqdm = quiet_tqdm


def separate_audio(video_file: Path, session: Path) -> tuple[Path, Path]:
    if sys.stdout is None:
        sys.stdout = StringIO()
    if sys.stderr is None:
        sys.stderr = StringIO()

    demucs_path = REPO_ROOT / "submodule" / "demucs"
    if not demucs_path.exists():
        raise RuntimeError("Demucs submodule is missing. Run: git submodule update --init --recursive")
    sys.path.insert(0, str(demucs_path))

    try:
        demucs_api = import_module("demucs.api")
    except ModuleNotFoundError as exc:
        if exc.name == "torch":
            raise RuntimeError(
                "Demucs requires PyTorch, but torch is not installed in this runtime. "
                "For CUDA 12.6 install it with: "
                "uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126. "
                "For a bundled desktop app, rebuild with YOUDUB_BUNDLE_GPU_DEPS=1 after installing GPU dependencies."
            ) from exc
        raise
    _disable_demucs_tqdm()
    Separator = demucs_api.Separator
    save_audio = demucs_api.save_audio

    media_dir = session / "media"
    vocals_file = media_dir / "audio_vocals.wav"
    bgm_file = media_dir / "audio_bgm.wav"
    if vocals_file.exists() and bgm_file.exists():
        return vocals_file, bgm_file

    separator = Separator(model="htdemucs_ft", device=_device(), progress=False, shifts=3)
    _, separated = separator.separate_audio_file(str(video_file))

    vocals = separated["vocals"]
    bgm = None
    for stem, source in separated.items():
        if stem == "vocals":
            continue
        bgm = source if bgm is None else bgm + source

    save_audio(vocals, str(vocals_file), samplerate=separator.samplerate)
    save_audio(bgm, str(bgm_file), samplerate=separator.samplerate)
    return vocals_file, bgm_file
