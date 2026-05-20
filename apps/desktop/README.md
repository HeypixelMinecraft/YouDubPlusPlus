# YouDub Desktop

PyQt5 desktop UI built with PyQt-Fluent-Widgets.

The app starts the FastAPI backend as a local subprocess, waits for `/api/health`, then talks to it through `http://127.0.0.1:<port>/api/...`.

## Run

From the repository root:

```powershell
uv venv --python 3.12 .venv
uv pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
python apps/desktop/main.py
```

The first screen supports URL tasks, local video upload, task history, task detail, logs, final-video opening, and runtime settings.

