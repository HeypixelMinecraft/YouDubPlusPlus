from __future__ import annotations

import sys


def main() -> int:
    # Import Qt lazily so packaging tools can hook it.
    from PyQt5.QtWidgets import QApplication

    from .ui.app_window import AppWindow

    app = QApplication(sys.argv)
    window = AppWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())

