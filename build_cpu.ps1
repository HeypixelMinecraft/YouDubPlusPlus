param(
    [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "Building YouDubPlusPlus CPU desktop package..."
if (Test-Path ".venv") {
    Write-Host "Using existing .venv"
} else {
    Write-Host "Creating .venv with Python $PythonVersion"
    uv venv --python $PythonVersion .venv
}
uv pip install -r requirements-desktop-gpu.txt
uv pip install torch torchaudio
uv pip install --upgrade pyinstaller

$env:YOUDUB_BUNDLE_GPU_DEPS = "1"
uv run python -m compileall apps/desktop/youdub_desktop apps/desktop/main.py backend/app
uv run python -c "import torch; print(f'torch={torch.__version__}; cuda_available={torch.cuda.is_available()}')"
uv run pyinstaller --clean --noconfirm apps/desktop/YouDubPlusPlus.spec

Write-Host "Done: dist/YouDubPlusPlus"
