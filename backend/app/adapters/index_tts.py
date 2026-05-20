from __future__ import annotations

import json
import os
from pathlib import Path

from pydub import AudioSegment


_TTS = None
_TTS_API = ""


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _download_checkpoints(model_dir: Path) -> None:
    """
    Best-effort checkpoint downloader.

    IndexTTS upstream recommends using `uv` + CLI tools, but for YouDub we provide an optional
    automatic download path for convenience.
    """
    model_id = os.getenv("INDEXTTS_MODEL_ID", "").strip()
    source = os.getenv("INDEXTTS_MODEL_SOURCE", "").strip().lower()
    if not model_id or not source:
        return

    model_dir.mkdir(parents=True, exist_ok=True)

    if source in {"modelscope", "ms"}:
        from modelscope import snapshot_download  # type: ignore

        snapshot_download(model_id, local_dir=str(model_dir))
        return

    if source in {"huggingface", "hf"}:
        from huggingface_hub import snapshot_download  # type: ignore

        snapshot_download(
            repo_id=model_id,
            local_dir=str(model_dir),
            local_dir_use_symlinks=False,
        )
        return

    raise ValueError("INDEXTTS_MODEL_SOURCE must be one of: modelscope|huggingface")


def _load_tts():
    global _TTS, _TTS_API
    if _TTS is not None:
        return _TTS

    model_dir_raw = os.getenv("INDEXTTS_MODEL_DIR", "").strip() or "checkpoints"
    model_dir = Path(model_dir_raw).expanduser()
    cfg_path_raw = os.getenv("INDEXTTS_CFG_PATH", "").strip()
    cfg_path = Path(cfg_path_raw).expanduser() if cfg_path_raw else model_dir / "config.yaml"

    if not model_dir.exists():
        if _truthy(os.getenv("INDEXTTS_AUTO_DOWNLOAD", "true")):
            _download_checkpoints(model_dir)

    if not model_dir.exists():
        raise FileNotFoundError(
            "IndexTTS checkpoints are missing.\n"
            "- Option A: set INDEXTTS_MODEL_DIR to an existing checkpoints folder.\n"
            "- Option B: set INDEXTTS_MODEL_SOURCE + INDEXTTS_MODEL_ID to auto-download.\n"
            f"INDEXTTS_MODEL_DIR={model_dir}\n"
            f"INDEXTTS_MODEL_SOURCE={os.getenv('INDEXTTS_MODEL_SOURCE','')}\n"
            f"INDEXTTS_MODEL_ID={os.getenv('INDEXTTS_MODEL_ID','')}"
        )

    if not cfg_path.exists():
        raise FileNotFoundError(
            "IndexTTS config.yaml not found. Set INDEXTTS_CFG_PATH, or put it under INDEXTTS_MODEL_DIR.\n"
            f"INDEXTTS_MODEL_DIR={model_dir}\n"
            f"INDEXTTS_CFG_PATH={cfg_path}"
        )

    try:
        from indextts.infer_v2 import IndexTTS2  # type: ignore

        _TTS = IndexTTS2(
            cfg_path=str(cfg_path),
            model_dir=str(model_dir),
            use_fp16=_truthy(os.getenv("INDEXTTS_USE_FP16", "false")),
            use_cuda_kernel=_truthy(os.getenv("INDEXTTS_USE_CUDA_KERNEL", "false")),
            use_deepspeed=_truthy(os.getenv("INDEXTTS_USE_DEEPSPEED", "false")),
        )
        _TTS_API = "v2"
        return _TTS
    except ModuleNotFoundError:
        pass
    except Exception:
        # Some installs ship only v1; fall through.
        pass

    try:
        # Fallback to IndexTTS v1 API (no extra flags).
        from indextts.infer import IndexTTS  # type: ignore

        _TTS = IndexTTS(model_dir=str(model_dir), cfg_path=str(cfg_path))
        _TTS_API = "v1"
        return _TTS
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "IndexTTS is not installed (missing Python module 'indextts'). "
            "Install it from https://github.com/index-tts/index-tts (this project pins a git dependency in requirements.txt)."
        ) from exc


def _fallback_reference(vocals_dir: Path, min_ms: int) -> Path:
    files = sorted(vocals_dir.glob("*.wav"))
    if not files:
        raise FileNotFoundError("No vocal segments were generated for IndexTTS references.")
    for path in files:
        if len(AudioSegment.from_file(path)) >= min_ms:
            return path
    return files[0]


def generate_tts(translation_file: Path, vocals_dir: Path, session: Path) -> Path:
    """
    Generate one wav per translated sentence.

    IndexTTS is zero-shot and expects a reference speaker audio prompt.
    We reuse the per-sentence vocal reference clips when possible, and fall back to a longer clip.
    """
    output_dir = session / "segments" / "tts"
    output_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(translation_file.read_text(encoding="utf-8"))
    tts = _load_tts()

    min_reference_ms = int(os.getenv("INDEXTTS_MIN_REFERENCE_MS", "1200"))
    fallback = _fallback_reference(vocals_dir, min_reference_ms)

    emo_audio_prompt = os.getenv("INDEXTTS_EMO_AUDIO_PROMPT", "").strip()
    emo_alpha_raw = os.getenv("INDEXTTS_EMO_ALPHA", "").strip()
    emo_alpha = float(emo_alpha_raw) if emo_alpha_raw else None
    use_emo_text = _truthy(os.getenv("INDEXTTS_USE_EMO_TEXT", "false"))
    emo_text = os.getenv("INDEXTTS_EMO_TEXT", "").strip()

    for index, item in enumerate(data["translation"], start=1):
        output_file = output_dir / f"{index:04d}.wav"
        if output_file.exists():
            continue

        reference = vocals_dir / f"{index:04d}.wav"
        if not reference.exists() or len(AudioSegment.from_file(reference)) < min_reference_ms:
            reference = fallback

        text = (item.get("dst") or item.get("zh") or "").strip()
        if not text:
            # Keep indexing stable for downstream merger; write a tiny silence wav.
            AudioSegment.silent(duration=50).export(output_file, format="wav")
            continue

        kwargs = {
            "spk_audio_prompt": str(reference),
            "text": text,
            "output_path": str(output_file),
            "verbose": _truthy(os.getenv("INDEXTTS_VERBOSE", "false")),
        }

        if emo_audio_prompt:
            kwargs["emo_audio_prompt"] = emo_audio_prompt
        if emo_alpha is not None:
            kwargs["emo_alpha"] = emo_alpha
        if use_emo_text:
            kwargs["use_emo_text"] = True
        if emo_text:
            kwargs["emo_text"] = emo_text

        if _TTS_API == "v1":
            tts.infer(str(reference), text, str(output_file))
        else:
            tts.infer(**kwargs)

    return output_dir

