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
$PythonExe = Join-Path $Root ".venv\Scripts\python.exe"
if (Test-Path $PythonExe) {
    Write-Host "Using existing .venv"
} else {
    Write-Host "Creating .venv with Python $PythonVersion"
    uv venv --python $PythonVersion .venv
}
uv pip install --python $PythonExe -r requirements-desktop-gpu.txt
uv pip install --python $PythonExe -r $TorchRequirements
uv pip install --python $PythonExe --upgrade pyinstaller

if (-not $SkipCudaCheck) {
    & $PythonExe -c "import sys, torch; print(f'torch={torch.__version__}; torch_cuda={torch.version.cuda}; cuda_available={torch.cuda.is_available()}'); sys.exit(0 if torch.cuda.is_available() else 1)"
}

$env:YOUDUB_BUNDLE_GPU_DEPS = "1"
& $PythonExe -m compileall apps/desktop/youdub_desktop apps/desktop/main.py backend/app
& $PythonExe -c "import PyQt5, qfluentwidgets; print('PyQt5 desktop dependencies ok')"
& $PythonExe -m PyInstaller --clean --noconfirm apps/desktop/YouDubPlusPlus.spec

Write-Host "Done: dist/YouDubPlusPlus"
