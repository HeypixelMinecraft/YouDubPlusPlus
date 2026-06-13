"""Register PyTorch and CUDA DLL search paths before torch is imported."""

from __future__ import annotations

import os
import sys


def _add_dll_dir(path: str) -> None:
    if not os.path.isdir(path):
        return
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(path)


if sys.platform == "win32" and getattr(sys, "frozen", False):
    base = getattr(sys, "_MEIPASS", "")
    if base:
        _add_dll_dir(base)
        _add_dll_dir(os.path.join(base, "torch", "lib"))
        nvidia_root = os.path.join(base, "nvidia")
        if os.path.isdir(nvidia_root):
            for entry in os.listdir(nvidia_root):
                for sub in ("bin", "lib"):
                    _add_dll_dir(os.path.join(nvidia_root, entry, sub))
