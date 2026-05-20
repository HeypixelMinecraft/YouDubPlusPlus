# YouDub Desktop

PyQt5 desktop UI built with PyQt-Fluent-Widgets.

The app runs the YouDub backend modules in the same desktop process. It does not start a localhost HTTP server.

## Run

From the repository root:

```bash
uv venv --python 3.12 .venv
uv pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
python apps/desktop/main.py
```

The first screen supports URL tasks, local video upload, task history, task detail, logs, final-video opening, and runtime settings.

## Build

GitHub Actions builds Windows, macOS, and Linux artifacts on every push to `master`.
To build locally:

```bash
uv venv --python 3.12 .venv
uv pip install -r requirements-ci.txt
uv run pyinstaller --noconfirm apps/desktop/YouDubPlusPlus.spec
```

Linux systems may need Qt runtime packages such as `libgl1`, `libegl1`, `libxkbcommon-x11-0`, and the common `libxcb-*` helpers. The GitHub Actions workflow installs these automatically.

