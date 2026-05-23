from __future__ import annotations

import json
import os
from importlib import import_module
from pathlib import Path
from typing import Callable

import soundfile as sf
from pydub import AudioSegment

from ..config import MODEL_CACHE_DIR

_MODEL = None
LogFn = Callable[[str], None]


def _model_path(log: LogFn | None = None) -> Path:
    configured_dir = os.getenv("VOXCPM_MODEL_DIR")
    if configured_dir:
        path = Path(configured_dir).expanduser()
        if log:
            log(f"VoxCPM2 using configured model dir: {path}")
        return path

    model_id = os.getenv("VOXCPM_MODEL", "OpenBMB/VoxCPM2")
    local_dir = MODEL_CACHE_DIR / model_id.replace("/", "__")
    if log:
        log(f"VoxCPM2 downloading/loading model {model_id} -> {local_dir}")
    snapshot_download = import_module("modelscope").snapshot_download

    downloaded = snapshot_download(model_id, local_dir=str(local_dir))
    return Path(downloaded)


def _load_model(log: LogFn | None = None):
    global _MODEL
    if _MODEL is None:
        VoxCPM = import_module("voxcpm").VoxCPM
        load_denoiser = os.getenv("VOXCPM_LOAD_DENOISER", "false").lower() == "true"
        if log:
            log(f"Loading VoxCPM2 (load_denoiser={load_denoiser})")

        _MODEL = VoxCPM.from_pretrained(
            str(_model_path(log)),
            load_denoiser=load_denoiser,
        )
        if log:
            log("VoxCPM2 model loaded")
    elif log:
        log("VoxCPM2 model already loaded; reusing cached model")
    return _MODEL


def _fallback_reference(vocals_dir: Path, min_ms: int) -> Path:
    files = sorted(vocals_dir.glob("*.wav"))
    if not files:
        raise FileNotFoundError("No vocal segments were generated for VoxCPM references.")
    for path in files:
        if len(AudioSegment.from_file(path)) >= min_ms:
            return path
    return files[0]


def generate_tts(translation_file: Path, vocals_dir: Path, session: Path, log: LogFn | None = None) -> Path:
    output_dir = session / "segments" / "tts"
    output_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(translation_file.read_text(encoding="utf-8"))
    model = _load_model(log)
    min_reference_ms = int(os.getenv("VOXCPM_MIN_REFERENCE_MS", "1200"))
    fallback = _fallback_reference(vocals_dir, min_reference_ms)
    cfg_value = float(os.getenv("VOXCPM_CFG_VALUE", "2.0"))
    inference_timesteps = int(os.getenv("VOXCPM_INFERENCE_TIMESTEPS", "10"))
    total = len(data["translation"])
    if log:
        log(
            f"VoxCPM2 segments={total}, min_reference_ms={min_reference_ms}, "
            f"cfg_value={cfg_value}, inference_timesteps={inference_timesteps}, "
            f"fallback_reference={fallback.name}"
        )

    for index, item in enumerate(data["translation"], start=1):
        output_file = output_dir / f"{index:04d}.wav"
        if output_file.exists():
            if log and (index == 1 or index == total or index % 25 == 0):
                log(f"VoxCPM2 [{index}/{total}] reused {output_file.name}")
            continue
        reference = vocals_dir / f"{index:04d}.wav"
        if not reference.exists() or len(AudioSegment.from_file(reference)) < min_reference_ms:
            reference = fallback
        wav = model.generate(
            text=item.get("dst") or item.get("zh", ""),
            reference_wav_path=str(reference),
            cfg_value=cfg_value,
            inference_timesteps=inference_timesteps,
        )
        sf.write(output_file, wav, model.tts_model.sample_rate)
        if log and (index == 1 or index == total or index % 10 == 0):
            log(f"VoxCPM2 [{index}/{total}] wrote {output_file.name} using {reference.name}")

    return output_dir
