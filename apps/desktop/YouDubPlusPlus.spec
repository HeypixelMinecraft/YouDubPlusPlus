# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

ROOT = Path(SPECPATH).parents[1]
BUNDLE_GPU_DEPS = os.getenv("YOUDUB_BUNDLE_GPU_DEPS", "").lower() in {"1", "true", "yes", "on"}

heavy_hiddenimports = []
heavy_excludes = [
    "torch",
    "torchaudio",
    "torchvision",
    "demucs",
    "openunmix",
    "diffq",
    "dora",
    "julius",
    "lameenc",
    "whisper",
    "spacy",
    "indextts",
    "voxcpm",
    "modelscope",
    "huggingface_hub",
]

if BUNDLE_GPU_DEPS:
    heavy_hiddenimports = [
        "torch",
        "torchaudio",
        "whisper",
        "indextts",
        "voxcpm",
        "modelscope",
        "huggingface_hub",
    ]
    heavy_excludes = []


a = Analysis(
    [str(ROOT / "apps" / "desktop" / "main.py")],
    pathex=[str(ROOT), str(ROOT / "apps" / "desktop")],
    binaries=[],
    datas=[
        (str(ROOT / "apps" / "desktop" / "assets" / "youdub-icon.svg"), "assets"),
        (str(ROOT / "apps" / "desktop" / "assets" / "youdub-icon.ico"), "assets"),
        (str(ROOT / "apps" / "desktop" / "assets" / "youdub-icon.png"), "assets"),
        (str(ROOT / "submodule" / "demucs" / "demucs"), "submodule/demucs/demucs"),
        (str(ROOT / "submodule" / "demucs" / "conf"), "submodule/demucs/conf"),
        (str(ROOT / "submodule" / "demucs" / "README.md"), "submodule/demucs"),
    ],
    hiddenimports=[
        "backend.app.main",
        "backend.app.pipeline",
        "backend.app.adapters.demucs",
        "backend.app.adapters.tts",
        "backend.app.adapters.voxcpm",
        "backend.app.adapters.ytdlp",
        "youdub_desktop.main",
        "youdub_desktop.direct_client",
        "youdub_desktop.ui.app_window",
        "youdub_desktop.ui.fluent_compat",
        "youdub_desktop.ui.i18n",
        "PyQt5",
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "PyQt5.QtWidgets",
        "PyQt5.sip",
        "requests",
        "yt_dlp",
        "qfluentwidgets",
    ]
    + heavy_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=heavy_excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="YouDubPlusPlus",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon=str(ROOT / "apps" / "desktop" / "assets" / "youdub-icon.ico"),
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="YouDubPlusPlus",
)
