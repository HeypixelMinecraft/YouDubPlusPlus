from __future__ import annotations

from pathlib import Path
import sys


def run_backend(port: int) -> None:
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
    )


def main() -> int:
    package_root = Path(__file__).resolve().parents[1]
    repo_root = package_root.parents[1]
    for path in (package_root, repo_root):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    if len(sys.argv) >= 3 and sys.argv[1] == "--backend":
        run_backend(int(sys.argv[2]))
        return 0

    from PyQt5.QtWidgets import QApplication

    from youdub_desktop.ui.app_window import AppWindow

    app = QApplication(sys.argv)
    window = AppWindow(repo_root)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())

