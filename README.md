# YouDubPlusPlus

YouDubPlusPlus 是一个桌面端视频本地化工具。它把单个 YouTube 或 Bilibili 视频转换成目标语言配音版：下载视频、分离人声与背景音、识别字幕、翻译、生成配音、混音、压制字幕，最后输出本地 mp4。

当前项目已移除原 Next.js Web 前端，主界面改为 PyQt + PyQt-Fluent-Widgets 桌面应用。桌面端直接调用后端任务、数据库和流水线，不需要启动 `localhost:3000` 或前后端分离服务。

English README: [README.en.md](README.en.md)

## 功能

- 桌面端 Fluent 风格界面，管理任务、设置、日志、进度和最终视频。
- 后端与桌面端进程内集成，默认不暴露本地 Web UI。
- 支持 YouTube / Bilibili URL，也支持本地视频上传。
- 使用 Demucs 分离人声与背景音，Whisper 识别字幕，OpenAI 兼容 Chat Completions API 翻译。
- TTS 默认 `TTS_BACKEND=auto`：优先 IndexTTS，失败后回退 VoxCPM2；也可以强制 `index_tts` 或 `voxcpm`。
- GitHub Actions 每次提交运行轻量校验，并可在手动触发或 `v*` tag 时构建 Windows、macOS、Linux 桌面产物。

## 环境要求

- Python 3.12
- Git 和 Git submodule
- FFmpeg / ffprobe，并确保在 `PATH` 中可用
- 处理 YouTube 时建议准备可用代理和 Netscape 格式 Cookie
- OpenAI 兼容 API 的 `base URL`、API key 和模型名
- 完整处理视频建议使用 CUDA GPU；CPU 可以跑部分流程，但 ASR、分离和 TTS 会很慢

系统依赖示例：

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

## 安装

```powershell
git clone https://github.com/HeypixelMinecraft/YouDubPlusPlus.git
cd YouDubPlusPlus
git submodule update --init --recursive
uv venv --python 3.12 .venv
uv pip install -r requirements.txt
```

如果要在本机用 CUDA 跑 Demucs/Whisper/TTS，请额外安装 GPU 版 PyTorch。默认提供 CUDA 12.6 的安装文件：

```powershell
uv pip install -r requirements-torch-cu126.txt
```

如果你的显卡驱动或 CUDA 版本不同，请按 [PyTorch 官方安装页](https://pytorch.org/get-started/locally/) 选择对应命令。

国内网络可以使用镜像：

```powershell
uv pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
```

IndexTTS 通过 `requirements.txt` 从 GitHub 安装。如果安装失败，请按上游说明排查：[index-tts/index-tts](https://github.com/index-tts/index-tts)。IndexTTS2 checkpoints 可从 HuggingFace 或 ModelScope 下载，例如 `IndexTeam/IndexTTS-2`，然后把 `INDEXTTS_MODEL_DIR` 指向包含 `config.yaml` 的目录。

## 配置

复制环境文件：

```powershell
Copy-Item env.txt.example .env
```

macOS / Linux：

```bash
cp env.txt.example .env
```

常用环境变量：

| 变量 | 说明 |
| --- | --- |
| `WORKFOLDER` | 每个任务的媒体、中间产物和最终视频目录 |
| `YOUDUB_DATA_DIR` | 数据库、日志、cookies 和模型缓存的运行数据目录 |
| `MODEL_CACHE_DIR` | 模型缓存目录 |
| `DEVICE` | `cuda`、`cuda:0` 或 `cpu` |
| `OPENAI_BASE_URL` | OpenAI 兼容 API 地址 |
| `OPENAI_API_KEY` | 翻译使用的 API key |
| `OPENAI_MODEL` | 翻译使用的模型 |
| `YTDLP_PROXY_PORT` | yt-dlp 使用的本地代理端口 |
| `TTS_BACKEND` | `auto`、`index_tts` 或 `voxcpm` |
| `INDEXTTS_MODEL_DIR` / `INDEXTTS_CFG_PATH` | IndexTTS checkpoints 目录和配置路径 |
| `VOXCPM_MODEL` / `VOXCPM_MODEL_DIR` | VoxCPM2 回退模型配置 |

源码运行时，`workfolder` 和 `data` 默认在仓库根目录；桌面打包后，它们默认在 `YouDubPlusPlus.exe` 同级目录，不会写进 PyInstaller 的 `_internal` 资源目录。

## 运行桌面端

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe apps/desktop/main.py
```

macOS / Linux：

```bash
.venv/bin/python apps/desktop/main.py
```

## 打包

本项目包含 PyInstaller spec：

```powershell
uv pip install -r requirements-ci.txt
pyinstaller --noconfirm apps/desktop/YouDubPlusPlus.spec
```

上面的命令生成轻量桌面包，适合 CI 验证界面和基础流程；它不会把 Torch、Demucs、IndexTTS、VoxCPM2 等大模型依赖打进包里。要生成可直接运行 Demucs 的 GPU 完整包，请先安装 GPU 依赖并开启打包开关：

```powershell
uv pip install -r requirements-desktop-gpu.txt
uv pip install -r requirements-torch-cu126.txt
$env:YOUDUB_BUNDLE_GPU_DEPS = "1"
pyinstaller --clean --noconfirm apps/desktop/YouDubPlusPlus.spec
```

也可以使用 GitHub Actions 的 `Build YouDubPlusPlus` 工作流生成 Windows、macOS、Linux artifacts。为避免日常构建耗时过长，完整打包只在手动触发或 `v*` tag 时运行；普通 push/PR 只跑轻量 smoke tests。

## 流程

```text
YouTube / Bilibili URL 或本地视频
  -> yt-dlp / 本地导入
  -> Demucs 分离人声与背景音
  -> Whisper 识别语音和时间戳
  -> OpenAI 兼容 API 翻译
  -> 按句切分原人声作为参考音频
  -> IndexTTS 或 VoxCPM2 生成目标语言配音
  -> 对齐并混合背景音
  -> FFmpeg 压制字幕并输出 mp4
```

## 开发与测试

```powershell
pytest backend/tests
python -m compileall apps/desktop/youdub_desktop apps/desktop/main.py backend/app
```

主要目录：

```text
apps/desktop/      PyQt + PyQt-Fluent-Widgets 桌面端
backend/app/       任务、数据库、流水线和模型适配器
backend/tests/     后端单元测试
scripts/           辅助脚本
submodule/demucs/  Demucs 源码子模块
```

## License

Apache License 2.0. See [LICENSE](LICENSE).
