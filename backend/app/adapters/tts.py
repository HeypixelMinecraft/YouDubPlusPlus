from __future__ import annotations

from pathlib import Path
from typing import Callable


GenerateTts = Callable[[Path, Path, Path], Path]
LogFn = Callable[[str], None]


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

    YouDub currently uses VoxCPM2 for all TTS generation.
    """
    if log:
        log("Generating TTS with VoxCPM2")
    return _voxcpm()(translation_file, vocals_dir, session), "VoxCPM2"
