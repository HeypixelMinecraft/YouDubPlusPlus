from __future__ import annotations

from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel


class AppWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("YouDub Desktop")
        self.resize(1100, 720)

        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.addWidget(QLabel("YouDub Desktop (PyQt-Fluent-Widgets) – scaffold"))
        self.setCentralWidget(root)

