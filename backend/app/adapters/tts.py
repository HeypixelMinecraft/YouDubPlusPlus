from __future__ import annotations

import os
from pathlib import Path
from typing import Callable


GenerateTts = Callable[[Path, Path, Path], Path]
VALID_BACKENDS = {"auto", "index_tts", "voxcpm"}


def _backend() -> str:
    try:
        from .. import database

        value = database.get_tts_settings()["backend"]
    except Exception:
        value = os.getenv("TTS_BACKEND", "auto").strip().lower().replace("-", "_")
    if value not in VALID_BACKENDS:
        raise ValueError("TTS_BACKEND must be one of: auto, index_tts, voxcpm")
    return value


def _index_tts() -> GenerateTts:
    from .index_tts import generate_tts

    return generate_tts


def _voxcpm() -> GenerateTts:
    from .voxcpm import generate_tts

    return generate_tts


def generate_tts(translation_file: Path, vocals_dir: Path, session: Path) -> tuple[Path, str]:
    """
    Generate TTS clips and return the output directory plus backend name.

    `TTS_BACKEND=auto` tries IndexTTS first and falls back to VoxCPM2 if IndexTTS
    is unavailable or misconfigured. Use `index_tts` or `voxcpm` to force a
    specific backend and surface its error directly.
    """
    backend = _backend()
    if backend == "index_tts":
        return _index_tts()(translation_file, vocals_dir, session), "IndexTTS"
    if backend == "voxcpm":
        return _voxcpm()(translation_file, vocals_dir, session), "VoxCPM2"

    try:
        return _index_tts()(translation_file, vocals_dir, session), "IndexTTS"
    except Exception as index_error:  # noqa: BLE001 - preserve fallback behavior for local model setup failures.
        try:
            return _voxcpm()(translation_file, vocals_dir, session), "VoxCPM2"
        except Exception as voxcpm_error:  # noqa: BLE001
            raise RuntimeError(
                "Both TTS backends failed.\n"
                f"IndexTTS error: {index_error}\n"
                f"VoxCPM2 error: {voxcpm_error}"
            ) from voxcpm_error
