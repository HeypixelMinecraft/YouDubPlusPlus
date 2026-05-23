from __future__ import annotations

import os
from pathlib import Path
from typing import Callable


GenerateTts = Callable[[Path, Path, Path], Path]
LogFn = Callable[[str], None]
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


def generate_tts(
    translation_file: Path,
    vocals_dir: Path,
    session: Path,
    log: LogFn | None = None,
) -> tuple[Path, str]:
    """
    Generate TTS clips and return the output directory plus backend name.

    `TTS_BACKEND=auto` tries IndexTTS first and falls back to VoxCPM2 if IndexTTS
    is unavailable or misconfigured. Use `index_tts` or `voxcpm` to force a
    specific backend and surface its error directly.
    """
    backend = _backend()
    if log:
        log(f"TTS backend setting: {backend}")
    if backend == "index_tts":
        if log:
            log("Generating TTS with IndexTTS")
        return _index_tts()(translation_file, vocals_dir, session), "IndexTTS"
    if backend == "voxcpm":
        if log:
            log("Generating TTS with VoxCPM2")
        return _voxcpm()(translation_file, vocals_dir, session), "VoxCPM2"

    try:
        if log:
            log("Trying IndexTTS first")
        return _index_tts()(translation_file, vocals_dir, session), "IndexTTS"
    except Exception as index_error:  # noqa: BLE001 - preserve fallback behavior for local model setup failures.
        if log:
            log(f"IndexTTS failed: {index_error}")
            log("Falling back to VoxCPM2")
        try:
            return _voxcpm()(translation_file, vocals_dir, session), "VoxCPM2"
        except Exception as voxcpm_error:  # noqa: BLE001
            raise RuntimeError(
                "Both TTS backends failed.\n"
                f"IndexTTS error: {index_error}\n"
                f"VoxCPM2 error: {voxcpm_error}"
            ) from voxcpm_error
