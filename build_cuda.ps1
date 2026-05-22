param(
    [string]$PythonVersion = "3.11",
    [string]$TorchRequirements = "requirements-torch-cu128.txt",
    [switch]$SkipCudaCheck,
    [switch]$RecreateVenv
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "Building YouDubPlusPlus CUDA desktop package..."
Write-Host "PyTorch does not currently publish a cu131 pip wheel; this script uses cu128 by default."
$PythonExe = Join-Path $Root ".venv\Scripts\python.exe"
if ($RecreateVenv -and (Test-Path ".venv")) {
    Write-Host "Removing existing .venv"
    Remove-Item -Recurse -Force ".venv"
}
if (Test-Path $PythonExe) {
    $CurrentPython = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($CurrentPython -ne $PythonVersion) {
        throw ".venv uses Python $CurrentPython, but this build needs Python $PythonVersion because IndexTTS depends on numba<3.12 support. Run .\build_cuda.ps1 -RecreateVenv or delete .venv."
    }
    Write-Host "Using existing .venv with Python $CurrentPython"
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
