from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


def _resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)).resolve()
    return Path(__file__).resolve().parents[2]


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return REPO_ROOT


REPO_ROOT = _resource_root()
RUNTIME_ROOT = _runtime_root()

load_dotenv(RUNTIME_ROOT / ".env")
load_dotenv()

DATA_DIR = Path(os.getenv("YOUDUB_DATA_DIR", str(RUNTIME_ROOT / "data"))).expanduser()
COOKIE_DIR = DATA_DIR / "cookies"
DB_PATH = DATA_DIR / "youdub.sqlite"
YOUTUBE_COOKIE_PATH = COOKIE_DIR / "youtube.txt"
WORKFOLDER = Path(os.getenv("WORKFOLDER", str(RUNTIME_ROOT / "workfolder"))).expanduser()
LOG_DIR = DATA_DIR / "logs"
MODEL_CACHE_DIR = Path(os.getenv("MODEL_CACHE_DIR", str(DATA_DIR / "modelscope"))).expanduser()


def ensure_runtime_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    COOKIE_DIR.mkdir(parents=True, exist_ok=True)
    WORKFOLDER.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def device() -> str:
    configured = os.getenv("DEVICE") or os.getenv("CUDA_DEVICE")
    if configured:
        return configured
    return "cuda"


def openai_defaults() -> dict[str, str]:
    return {
        "base_url": os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1",
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "model": os.getenv("OPENAI_MODEL") or os.getenv("OPENAI_MODEL_NAME") or "gpt-4o-mini",
        "translate_concurrency": os.getenv("OPENAI_TRANSLATE_CONCURRENCY", "50"),
    }


def translate_defaults() -> dict[str, str]:
    mode = os.getenv("TRANSLATE_MODE", "openai").strip().lower() or "openai"
    if mode not in {"openai", "google", "youdao"}:
        mode = "openai"
    return {
        "mode": mode,
    }


def tts_defaults() -> dict[str, str]:
    backend = os.getenv("TTS_BACKEND", "auto").strip().lower().replace("-", "_") or "auto"
    if backend not in {"auto", "index_tts", "voxcpm"}:
        backend = "auto"
    return {
        "backend": backend,
    }


def ffmpeg_binary() -> str:
    return os.getenv("FFMPEG_PATH", "").strip() or "ffmpeg"


def ffprobe_binary() -> str:
    return os.getenv("FFPROBE_PATH", "").strip() or "ffprobe"


def media_subprocess_creationflags() -> int:
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def ytdlp_defaults() -> dict[str, str]:
    return {
        "proxy_port": os.getenv("YTDLP_PROXY_PORT", ""),
    }
