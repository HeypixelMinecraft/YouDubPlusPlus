# YouDub Desktop

PyQt5 desktop UI built with PyQt-Fluent-Widgets.

The app runs the YouDub backend modules in the same desktop process. It does not start a localhost HTTP server.

## Run

From the repository root:

```bash
uv venv --python 3.12 .venv
uv pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
uv pip install -r requirements-torch-cu126.txt
python apps/desktop/main.py
```

The first screen supports URL tasks, local video upload, task history, task detail, logs, final-video opening, and runtime settings.

## Build

GitHub Actions runs fast smoke tests on every push and PR. Full Windows, macOS, and Linux PyInstaller builds run on manual workflow dispatch or `v*` release tags.
To build locally:

```bash
uv venv --python 3.12 .venv
uv pip install -r requirements-ci.txt
uv run pyinstaller --noconfirm apps/desktop/YouDubPlusPlus.spec
```

The default package is intentionally lightweight and does not bundle PyTorch or large model runtimes. For a GPU package that can run Demucs from the bundled app, install the CUDA PyTorch wheels and enable the heavy dependency bundle:

```bash
uv pip install -r requirements-desktop-gpu.txt
uv pip install -r requirements-torch-cu126.txt
YOUDUB_BUNDLE_GPU_DEPS=1 uv run pyinstaller --clean --noconfirm apps/desktop/YouDubPlusPlus.spec
```

Linux systems may need Qt runtime packages such as `libgl1`, `libegl1`, `libxkbcommon-x11-0`, and the common `libxcb-*` helpers. The GitHub Actions workflow installs these automatically.

