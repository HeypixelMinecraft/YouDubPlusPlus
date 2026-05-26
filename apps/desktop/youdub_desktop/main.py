from __future__ import annotations

from pathlib import Path
import sys


def _asset_path(repo_root: Path, name: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)) / "assets" / name
    return repo_root / "apps" / "desktop" / "assets" / name


def main() -> int:
    package_root = Path(__file__).resolve().parents[1]
    repo_root = package_root.parents[1]
    for path in (package_root, repo_root):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("YouDubPlusPlus.Desktop")
        except Exception:
            pass

    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import QApplication

    from youdub_desktop.mcp_service import stop_mcp_service
    from youdub_desktop.ui.app_window import AppWindow

    app = QApplication(sys.argv)
    app.aboutToQuit.connect(stop_mcp_service)
    icon_path = _asset_path(repo_root, "youdub-icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = AppWindow(repo_root)
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
