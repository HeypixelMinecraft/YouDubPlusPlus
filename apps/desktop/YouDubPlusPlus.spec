# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT = Path(SPECPATH).parents[1]


a = Analysis(
    [str(ROOT / "apps" / "desktop" / "main.py")],
    pathex=[str(ROOT), str(ROOT / "apps" / "desktop")],
    binaries=[],
    datas=[
        (str(ROOT / "apps" / "web" / "public" / "youdub-icon.svg"), "assets"),
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
        "voxcpm",
        "modelscope",
        "requests",
        "yt_dlp",
        "qfluentwidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
