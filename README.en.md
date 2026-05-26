# YouDubPlusPlus

YouDubPlusPlus is a desktop video-localization tool. It turns a single YouTube or Bilibili video into a dubbed video in the target language: download, vocal/background separation, transcription, translation, voice generation, audio mixing, subtitle rendering, and final local mp4 output.

[Origial project](https://github.com/liuzhao1225/YouDub-webui) Next.js Web frontend has been removed. The main app is now a PyQt + PyQt-Fluent-Widgets desktop app. It calls the backend tasks, database, and pipeline directly in process, so you do not need to run `localhost:3000` or a separate frontend server.

Chinese README: [README.md](README.md)

## Features

- Fluent-style desktop UI for tasks, settings, logs, progress, and final videos.
- Desktop and backend are integrated in one process by default.
- Supports YouTube / Bilibili URLs and local video input.
- Uses Demucs for source separation, Whisper for transcription, and an OpenAI-compatible Chat Completions API for translation.
- TTS uses VoxCPM2.
- GitHub Actions runs lightweight checks on every push and can build Windows, macOS, and Linux artifacts on manual dispatch or `v*` tags.

## Demo Assets (From [Youtube](https://www.youtube.com/shorts/U9jxeRd87EQ))
https://github.com/user-attachments/assets/bfd5a20d-4932-4f87-8d54-d2bc54a3b373

https://github.com/user-attachments/assets/2b92b64f-e6a0-41c0-8f08-6389a95cce1d

## Requirements

- Python 3.12
- Git and Git submodules
- FFmpeg / ffprobe available on `PATH`
- A proxy and Netscape-format cookies are recommended for YouTube videos
- An OpenAI-compatible API base URL, API key, and model name
- CUDA GPU is recommended for complete video processing. ASR, separation, and TTS will be slow in non-CUDA environments.

System dependency examples:

```powershell
# Windows PowerShell
winget install Gyan.FFmpeg
```

```bash
# Ubuntu / Debian / WSL2
sudo apt update
sudo apt install -y ffmpeg
```

```bash
# macOS
brew install ffmpeg
```

## Install

```powershell
git clone https://github.com/HeypixelMinecraft/YouDubPlusPlus.git
cd YouDubPlusPlus
git submodule update --init --recursive
uv venv --python 3.12 .venv
uv pip install -r requirements.txt
```

## Configure

Copy the environment file:

```powershell
Copy-Item env.txt.example .env
```

macOS / Linux:

```bash
cp env.txt.example .env
```

Common variables:

| Variable | Purpose |
| --- | --- |
| `WORKFOLDER` | Per-task media, intermediate artifacts, and final videos |
| `MODEL_CACHE_DIR` | Model cache directory |
| `DEVICE` | `cuda`, `cuda:0`, or `cpu` |
| `OPENAI_BASE_URL` | OpenAI-compatible API endpoint |
| `OPENAI_API_KEY` | API key for translation |
| `OPENAI_MODEL` | Translation model |
| `YTDLP_PROXY_PORT` | Local proxy port for yt-dlp |
| `VOXCPM_MODEL` / `VOXCPM_MODEL_DIR` | VoxCPM2 fallback model configuration |
| `YOUDUB_MCP_ENABLED` | Enable the backend MCP SSE server, defaults to `true` |
| `YOUDUB_MCP_HOST` / `YOUDUB_MCP_PORT` | Host and port used when the desktop app starts the MCP SSE server, defaults to `127.0.0.1:8765` |

## Run Desktop

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe apps/desktop/main.py
```

macOS / Linux:

```bash
.venv/bin/python apps/desktop/main.py
```

## MCP SSE Server

The desktop app provides an MCP page where you can start or stop the local MCP SSE server. The default client URL is:

```text
http://127.0.0.1:8765/mcp/sse
```

When running the FastAPI backend separately with uvicorn, YouDub also exposes an MCP server at `/mcp` using SSE transport:

```powershell
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

MCP clients should connect to:

```text
http://127.0.0.1:8000/mcp/sse
```

The first MCP version exposes task-management tools for listing tasks, reading task details and logs, creating URL tasks, rerunning tasks, and resuming failed tasks. Local video upload, deletion, cookies, and settings writes are intentionally not exposed as MCP tools.

## Package

The repository includes a PyInstaller spec:

```powershell
uv pip install -r requirements-ci.txt
pyinstaller --noconfirm apps/desktop/YouDubPlusPlus.spec
```

You can also use the `Build YouDubPlusPlus` GitHub Actions workflow to produce Windows, macOS, and Linux artifacts. To keep normal CI fast, full packaging runs only on manual dispatch or `v*` tags; regular push/PR runs lightweight smoke tests.

## Pipeline

```text
YouTube / Bilibili URL or local video
  -> yt-dlp / local import
  -> Demucs separates vocals and background audio
  -> Whisper transcribes speech and timestamps
  -> OpenAI-compatible API translates text
  -> Source vocals are split into per-sentence reference clips
  -> VoxCPM2 generates target-language voiceover
  -> Voiceover is aligned and mixed with background audio
  -> FFmpeg burns subtitles and renders the final mp4
```

## Development and Tests

```powershell
pytest backend/tests
python -m compileall apps/desktop/youdub_desktop apps/desktop/main.py backend/app
```

Main directories:

```text
apps/desktop/      PyQt + PyQt-Fluent-Widgets desktop app
backend/app/       Tasks, database, pipeline, and model adapters
backend/tests/     Backend unit tests
scripts/           Helper scripts
submodule/demucs/  Demucs source submodule
```

## License

GPL3. See [LICENSE](LICENSE).
