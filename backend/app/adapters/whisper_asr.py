from __future__ import annotations

import json
import os
from importlib import import_module
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from pydub import AudioSegment

from ..config import device

_MODEL = None
LogFn = Callable[[str], None]


def _whisper_cache_file(whisper, name: str, download_root: str | None) -> Path | None:
    if not download_root:
        return None
    model_url = getattr(whisper, "_MODELS", {}).get(name)
    if not model_url:
        return None
    filename = Path(urlparse(model_url).path).name
    if not filename:
        return None
    return Path(download_root).expanduser() / filename


def _is_checksum_error(exc: RuntimeError) -> bool:
    return "sha256 checksum" in str(exc).lower()


def _remove_corrupt_whisper_cache(whisper, name: str, download_root: str | None) -> bool:
    cache_file = _whisper_cache_file(whisper, name, download_root)
    if not cache_file or not cache_file.exists():
        return False
    cache_file.unlink()
    return True


def _load_model(log: LogFn | None = None):
    global _MODEL
    if _MODEL is not None:
        if log:
            log("Whisper model already loaded; reusing cached model")
        return _MODEL

    whisper = import_module("whisper")

    name = os.getenv("WHISPER_MODEL", "large-v3-turbo")
    download_root = os.getenv("WHISPER_DOWNLOAD_ROOT") or None
    if log:
        log(f"Loading Whisper model '{name}' on {device()}")
    try:
        _MODEL = whisper.load_model(name, device=device(), download_root=download_root)
    except RuntimeError as exc:
        if not _is_checksum_error(exc):
            raise
        if not _remove_corrupt_whisper_cache(whisper, name, download_root):
            raise
        if log:
            log("Removed corrupt Whisper model cache; retrying download/load")
        _MODEL = whisper.load_model(name, device=device(), download_root=download_root)

    return _MODEL


def _to_ms(seconds: float) -> int:
    return int(round(float(seconds) * 1000))


def _convert_words(words: list) -> list:
    return [
        {
            "text": w.get("word", ""),
            "start_time": _to_ms(w.get("start", 0.0)),
            "end_time": _to_ms(w.get("end", 0.0)),
        }
        for w in words or []
    ]


def _convert_segments(segments: list) -> list:
    return [
        {
            "text": seg.get("text", "").strip(),
            "start_time": _to_ms(seg.get("start", 0.0)),
            "end_time": _to_ms(seg.get("end", 0.0)),
            "words": _convert_words(seg.get("words", [])),
        }
        for seg in segments
    ]


def recognize_speech(vocals_file: Path, session: Path, language: str, log: LogFn | None = None) -> Path:
    metadata_dir = session / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    output_file = metadata_dir / "asr.json"
    if output_file.exists():
        if log:
            log(f"Whisper output already exists: {output_file}")
        return output_file

    if log:
        duration_ms = len(AudioSegment.from_file(vocals_file))
        size_mb = vocals_file.stat().st_size / (1024 * 1024)
        log(f"Whisper input: {vocals_file} ({duration_ms / 1000:.1f}s, {size_mb:.1f} MB), language={language}")
    model = _load_model(log)
    if log:
        log("Whisper transcription started")
    result = model.transcribe(
        str(vocals_file),
        language=language,
        word_timestamps=True,
        verbose=False,
    )
    if log:
        log("Whisper transcription finished; converting segments")

    utterances = _convert_segments(result.get("segments", []))
    if not utterances:
        raise RuntimeError("Whisper did not return any segments.")

    duration_ms = len(AudioSegment.from_file(vocals_file))
    payload = {
        "audio_info": {"duration": duration_ms},
        "result": {
            "text": (result.get("text") or "").strip(),
            "utterances": utterances,
        },
    }
    output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if log:
        word_count = sum(len(u.get("words") or []) for u in utterances)
        log(f"Whisper wrote {len(utterances)} segments / {word_count} words -> {output_file}")
    return output_file
