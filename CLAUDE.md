# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

### Environment setup

```powershell
git submodule update --init --recursive
uv venv --python 3.12 .venv
uv pip install -r requirements.txt
Copy-Item env.txt.example .env
```

FFmpeg/ffprobe must be available on `PATH`. Full video processing is designed for CUDA; CPU-only runs are useful for tests and lightweight UI/backend work but ASR, separation, and TTS will be slow.

For local CUDA development install a matching PyTorch requirements file after the base requirements, for example:

```powershell
uv pip install -r requirements-torch-cu126.txt
```

### Run the app and backend

```powershell
.\.venv\Scripts\python.exe apps/desktop/main.py
```

The desktop app is the primary UI. It runs backend modules in the same process and does not require a separate localhost web frontend.

To run the FastAPI backend separately, including the MCP SSE endpoint at `/mcp/sse`:

```powershell
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

To run one pipeline task synchronously from the CLI:

```powershell
.\.venv\Scripts\python.exe scripts/run_pipeline.py <youtube-or-bilibili-url>
```

### Tests and checks

```powershell
pytest backend/tests
pytest backend/tests/test_pipeline.py
pytest backend/tests/test_pipeline.py::test_name
python -m compileall apps/desktop/youdub_desktop apps/desktop/main.py backend/app
```

CI's lightweight dependency set is `requirements-ci-lite.txt`; full packaging dependencies are in `requirements-ci.txt` plus `requirements-desktop-gpu.txt`.

### Packaging

Basic PyInstaller build:

```powershell
uv pip install -r requirements-ci.txt
pyinstaller --noconfirm apps/desktop/YouDubPlusPlus.spec
```

Local full desktop build scripts use Python 3.11 and validate the existing `.venv` version:

```powershell
.\build_cpu.ps1
.\build_cuda.ps1
.\build_cpu.ps1 -RecreateVenv
.\build_cuda.ps1 -RecreateVenv
.\build_cuda.ps1 -TorchRequirements requirements-torch-cu126.txt
```

`build_cuda.ps1` defaults to `requirements-torch-cu128.txt` and checks `torch.cuda.is_available()` unless `-SkipCudaCheck` is passed. The PyInstaller spec bundles heavy GPU/model dependencies only when `YOUDUB_BUNDLE_GPU_DEPS` is truthy.

## Architecture overview

YouDubPlusPlus is a PyQt5 + PyQt-Fluent-Widgets desktop application for localizing videos. The old Next.js frontend has been removed; there is no `localhost:3000` frontend to run.

Main areas:

- `apps/desktop/` contains the desktop app, assets, and PyInstaller spec.
- `apps/desktop/youdub_desktop/main.py` creates the Qt application, checks OS support, sets the app icon, and opens `AppWindow`.
- `apps/desktop/youdub_desktop/direct_client.py` is the in-process bridge used by the desktop UI. It initializes runtime directories and the SQLite database, starts the single worker, exposes task/settings/cookie operations, and enqueues tasks.
- `backend/app/main.py` is the optional FastAPI API. It mirrors most desktop task/settings operations over HTTP and mounts the MCP SSE app at `/mcp` when enabled.
- `backend/app/database.py` owns SQLite schema and task/settings persistence under `YOUDUB_DATA_DIR` or `data/` by default.
- `backend/app/worker.py` is a single-thread FIFO queue. Both the desktop direct client and FastAPI startup call `worker.start(run_task)`.
- `backend/app/pipeline.py` implements `PipelineRunner`, which executes each task stage and records stage status/logs.
- `backend/app/stages.py` defines the ordered pipeline stages: `download`, `separate`, `asr`, `asr_fix`, `translate`, `split_audio`, `tts`, `merge_audio`, `merge_video`.
- `backend/app/adapters/` contains integrations for yt-dlp/local video, Demucs, Whisper ASR, translation providers, TTS/VoxCPM, audio operations, and FFmpeg.
- `backend/app/mcp_server.py` exposes a limited task-management MCP server. Local upload, task deletion, cookie writes, and settings writes are intentionally not MCP tools.
- `scripts/` contains helper scripts such as `run_pipeline.py` for synchronous pipeline execution.
- `submodule/demucs/` is a required git submodule and is included by the PyInstaller spec.

## Runtime data and configuration

`backend/app/config.py` loads `.env` from the runtime root and defines the main paths/settings:

- `WORKFOLDER`: per-task media, intermediate files, and final videos; defaults to `workfolder/` in source runs.
- `YOUDUB_DATA_DIR`: SQLite database, logs, cookies, and model cache base; defaults to `data/`.
- `MODEL_CACHE_DIR`: model cache directory; defaults under `data/modelscope`.
- `DEVICE`: defaults to `cuda` if unset.
- `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_TRANSLATE_CONCURRENCY`: OpenAI-compatible translation settings.
- `TRANSLATE_MODE`: `openai`, `google`, or `youdao`.
- `YTDLP_PROXY_PORT`: optional local proxy port for yt-dlp.
- `YOUDUB_MCP_ENABLED`, `YOUDUB_MCP_HOST`, `YOUDUB_MCP_PORT`: MCP SSE service configuration.

When packaged with PyInstaller, runtime data is kept next to the executable rather than inside the `_internal` resource directory.
