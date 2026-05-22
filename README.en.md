# YouDubPlusPlus

YouDubPlusPlus is a desktop video-localization tool. It turns a single YouTube or Bilibili video into a dubbed video in the target language: download, vocal/background separation, transcription, translation, voice generation, audio mixing, subtitle rendering, and final local mp4 output.

[Origial project](https://github.com/liuzhao1225/YouDub-webui) Next.js Web frontend has been removed. The main app is now a PyQt + PyQt-Fluent-Widgets desktop app. It calls the backend tasks, database, and pipeline directly in process, so you do not need to run `localhost:3000` or a separate frontend server.

Chinese README: [README.md](README.md)

## Features

- Fluent-style desktop UI for tasks, settings, logs, progress, and final videos.
- Desktop and backend are integrated in one process by default.
- Supports YouTube / Bilibili URLs and local video input.
- Uses Demucs for source separation, Whisper for transcription, and an OpenAI-compatible Chat Completions API for translation.
- TTS defaults to `TTS_BACKEND=auto`: try IndexTTS first, then fall back to VoxCPM2. You can force `index_tts` or `voxcpm`.
- GitHub Actions runs lightweight checks on every push and can build Windows, macOS, and Linux artifacts on manual dispatch or `v*` tags.

## Requirements

- Python 3.12
- Git and Git submodules
- FFmpeg / ffprobe available on `PATH`
- A proxy and Netscape-format cookies are recommended for YouTube videos
- An OpenAI-compatible API base URL, API key, and model name
- CUDA GPU is recommended for complete video processing. CPU can run parts of the flow, but ASR, separation, and TTS will be slow.

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

IndexTTS is installed from GitHub through `requirements.txt`. If that install fails, follow the upstream setup notes: [index-tts/index-tts](https://github.com/index-tts/index-tts). Download IndexTTS2 checkpoints from HuggingFace or ModelScope, for example `IndexTeam/IndexTTS-2`, then set `INDEXTTS_MODEL_DIR` to the directory that contains `config.yaml`.

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
| `TTS_BACKEND` | `auto`, `index_tts`, or `voxcpm` |
| `INDEXTTS_MODEL_DIR` / `INDEXTTS_CFG_PATH` | IndexTTS checkpoint directory and config path |
| `VOXCPM_MODEL` / `VOXCPM_MODEL_DIR` | VoxCPM2 fallback model configuration |

## Run Desktop

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe apps/desktop/main.py
```

macOS / Linux:

```bash
.venv/bin/python apps/desktop/main.py
```

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
  -> IndexTTS or VoxCPM2 generates target-language voiceover
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
