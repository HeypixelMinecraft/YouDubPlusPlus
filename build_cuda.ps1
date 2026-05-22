param(
    [string]$PythonVersion = "3.12",
    [string]$TorchRequirements = "requirements-torch-cu128.txt",
    [switch]$SkipCudaCheck
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "Building YouDubPlusPlus CUDA desktop package..."
Write-Host "PyTorch does not currently publish a cu131 pip wheel; this script uses cu128 by default."
if (Test-Path ".venv") {
    Write-Host "Using existing .venv"
} else {
    Write-Host "Creating .venv with Python $PythonVersion"
    uv venv --python $PythonVersion .venv
}
uv pip install -r requirements-desktop-gpu.txt
uv pip install -r $TorchRequirements
uv pip install --upgrade pyinstaller

if (-not $SkipCudaCheck) {
    uv run python -c "import sys, torch; print(f'torch={torch.__version__}; torch_cuda={torch.version.cuda}; cuda_available={torch.cuda.is_available()}'); sys.exit(0 if torch.cuda.is_available() else 1)"
}

$env:YOUDUB_BUNDLE_GPU_DEPS = "1"
uv run python -m compileall apps/desktop/youdub_desktop apps/desktop/main.py backend/app
uv run python -c "import PyQt5, qfluentwidgets; print('PyQt5 desktop dependencies ok')"
uv run pyinstaller --clean --noconfirm apps/desktop/YouDubPlusPlus.spec

Write-Host "Done: dist/YouDubPlusPlus"
