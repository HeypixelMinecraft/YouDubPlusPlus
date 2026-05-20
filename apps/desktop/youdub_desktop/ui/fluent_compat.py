from __future__ import annotations

from PyQt5.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTextEdit,
)

try:
    from qfluentwidgets import (  # type: ignore
        BodyLabel,
        ComboBox,
        LineEdit,
        PlainTextEdit,
        PrimaryPushButton,
        ProgressBar,
        PushButton,
        SubtitleLabel,
        TextEdit,
        Theme,
        setTheme,
    )
except Exception:  # noqa: BLE001 - keep the desktop usable without optional widgets.
    BodyLabel = QLabel
    ComboBox = QComboBox
    LineEdit = QLineEdit
    PlainTextEdit = QPlainTextEdit
    PrimaryPushButton = QPushButton
    ProgressBar = QProgressBar
    PushButton = QPushButton
    SubtitleLabel = QLabel
    TextEdit = QTextEdit

    class Theme:
        AUTO = "auto"

    def setTheme(_: str) -> None:
        return None
