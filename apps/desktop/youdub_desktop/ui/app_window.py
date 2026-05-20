from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PyQt5.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QFileDialog, QFrame, QGridLayout, QHBoxLayout, QMessageBox, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    ComboBox,
    FluentIcon as FIF,
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PlainTextEdit,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
    TableWidget,
    TextEdit,
    Theme,
    setTheme,
)

from ..direct_client import DirectClient


class WorkerSignals(QObject):
    done = pyqtSignal(object)
    error = pyqtSignal(str)


class Job(QRunnable):
    def __init__(self, fn: Callable[[], Any], done: Callable[[Any], None], error: Callable[[str], None]):
        super().__init__()
        self.fn = fn
        self.signals = WorkerSignals()
        self.signals.done.connect(done)
        self.signals.error.connect(error)

    def run(self) -> None:
        try:
            self.signals.done.emit(self.fn())
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit(str(exc))


def _active(status: str | None) -> bool:
    return status in {"queued", "running"}


class AppWindow(FluentWindow):
    def __init__(self, repo_root: Path) -> None:
        super().__init__()
        setTheme(Theme.AUTO)
        self.repo_root = repo_root
        self.client: DirectClient | None = None
        self.pool = QThreadPool.globalInstance()
        self.tasks: list[dict[str, Any]] = []
        self.current_task_id: str | None = None
        self.current_task: dict[str, Any] | None = None
        self.upload_file: Path | None = None
        self._refresh_busy = False

        self.setWindowTitle("YouDubPlusPlus")
        self.resize(1220, 820)
        self.setMinimumSize(980, 680)
        if hasattr(self, "setMicaEffectEnabled"):
            self.setMicaEffectEnabled(True)

        self.tasks_page = self._build_tasks_page()
        self.detail_page = self._build_detail_page()
        self.settings_page = self._build_settings_page()
        self.addSubInterface(self.tasks_page, FIF.HOME, "Tasks")
        self.addSubInterface(self.detail_page, FIF.VIDEO, "Detail")
        self.addSubInterface(self.settings_page, FIF.SETTING, "Settings")

        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh_tasks)
        self._job(self._init_client, self._ready)

    def _init_client(self) -> DirectClient:
        return DirectClient()

    def _ready(self, client: DirectClient) -> None:
        self.client = client
        self._toast("YouDub backend is running inside the desktop app.")
        self.refresh_tasks()
        self.load_settings()
        self.timer.start()

    def _build_tasks_page(self) -> QWidget:
        page = _page("tasksPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(18)

        title = SubtitleLabel("Create localization task")
        layout.addWidget(title)

        card = CardWidget()
        form = QGridLayout(card)
        form.setContentsMargins(22, 18, 22, 18)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)

        self.youtube_input = LineEdit()
        self.youtube_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.bilibili_input = LineEdit()
        self.bilibili_input.setPlaceholderText("https://www.bilibili.com/video/BV...")
        self.direction_combo = ComboBox()
        self.direction_combo.addItems(["en-zh", "zh-en"])
        self.file_label = BodyLabel("No file selected")
        choose_file = PushButton("Choose video")
        choose_file.setIcon(FIF.FOLDER)
        choose_file.clicked.connect(self.choose_upload_file)
        create_button = PrimaryPushButton("Create task")
        create_button.setIcon(FIF.PLAY)
        create_button.clicked.connect(self.create_task)

        form.addWidget(StrongBodyLabel("YouTube URL"), 0, 0)
        form.addWidget(self.youtube_input, 0, 1, 1, 3)
        form.addWidget(StrongBodyLabel("Bilibili URL"), 1, 0)
        form.addWidget(self.bilibili_input, 1, 1, 1, 3)
        form.addWidget(StrongBodyLabel("Local video"), 2, 0)
        form.addWidget(self.file_label, 2, 1)
        form.addWidget(choose_file, 2, 2)
        form.addWidget(self.direction_combo, 2, 3)
        form.addWidget(create_button, 3, 3)
        layout.addWidget(card)

        layout.addWidget(SubtitleLabel("Task history"))
        self.tasks_table = TableWidget()
        self.tasks_table.setColumnCount(5)
        self.tasks_table.setHorizontalHeaderLabels(["Title", "Status", "Stage", "Created", "ID"])
        self.tasks_table.verticalHeader().hide()
        self.tasks_table.setSelectionBehavior(TableWidget.SelectRows)
        self.tasks_table.setEditTriggers(TableWidget.NoEditTriggers)
        self.tasks_table.itemSelectionChanged.connect(self._select_task)
        layout.addWidget(self.tasks_table, 1)
        return page

    def _build_detail_page(self) -> QWidget:
        page = _page("detailPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(14)

        overview = CardWidget()
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(22, 18, 22, 18)
        self.detail_title = SubtitleLabel("No task selected")
        self.detail_status = BodyLabel("Choose a task from the task history.")
        self.progress = ProgressBar()
        overview_layout.addWidget(self.detail_title)
        overview_layout.addWidget(self.detail_status)
        overview_layout.addWidget(self.progress)
        actions = QHBoxLayout()
        self.resume_button = PushButton("Resume")
        self.resume_button.setIcon(FIF.PLAY)
        self.resume_button.clicked.connect(lambda: self._task_action("resume"))
        self.rerun_button = PushButton("Rerun")
        self.rerun_button.setIcon(FIF.SYNC)
        self.rerun_button.clicked.connect(lambda: self._task_action("rerun"))
        self.delete_button = PushButton("Delete")
        self.delete_button.setIcon(FIF.DELETE)
        self.delete_button.clicked.connect(lambda: self._task_action("delete"))
        self.open_video_button = PrimaryPushButton("Open final video")
        self.open_video_button.setIcon(FIF.VIDEO)
        self.open_video_button.clicked.connect(self.open_final_video)
        for button in (self.resume_button, self.rerun_button, self.delete_button, self.open_video_button):
            actions.addWidget(button)
        actions.addStretch(1)
        overview_layout.addLayout(actions)
        layout.addWidget(overview)

        self.stages_table = TableWidget()
        self.stages_table.setColumnCount(4)
        self.stages_table.setHorizontalHeaderLabels(["Stage", "Status", "Duration", "Message"])
        self.stages_table.verticalHeader().hide()
        self.stages_table.setEditTriggers(TableWidget.NoEditTriggers)
        layout.addWidget(self.stages_table, 1)

        self.log_box = PlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Logs will appear when a task starts.")
        layout.addWidget(self.log_box, 1)
        return page

    def _build_settings_page(self) -> QWidget:
        page = _page("settingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(18)
        layout.addWidget(SubtitleLabel("Runtime settings"))

        card = CardWidget()
        grid = QGridLayout(card)
        grid.setContentsMargins(22, 18, 22, 18)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        self.cookie_text = TextEdit()
        self.cookie_text.setPlaceholderText("Paste Netscape YouTube cookie content")
        self.proxy_input = LineEdit()
        self.proxy_input.setPlaceholderText("7890")
        self.base_url_input = LineEdit()
        self.api_key_input = LineEdit()
        self.api_key_input.setEchoMode(LineEdit.Password)
        self.model_input = LineEdit()
        self.concurrency_input = LineEdit()
        self.models_combo = ComboBox()
        load_button = PushButton("Get models")
        load_button.setIcon(FIF.CLOUD_DOWNLOAD)
        load_button.clicked.connect(self.load_models)
        save_button = PrimaryPushButton("Save settings")
        save_button.setIcon(FIF.SAVE)
        save_button.clicked.connect(self.save_settings)

        grid.addWidget(StrongBodyLabel("YouTube cookie"), 0, 0)
        grid.addWidget(self.cookie_text, 0, 1, 1, 3)
        grid.addWidget(StrongBodyLabel("yt-dlp proxy port"), 1, 0)
        grid.addWidget(self.proxy_input, 1, 1)
        grid.addWidget(StrongBodyLabel("OpenAI base URL"), 2, 0)
        grid.addWidget(self.base_url_input, 2, 1, 1, 3)
        grid.addWidget(StrongBodyLabel("OpenAI API key"), 3, 0)
        grid.addWidget(self.api_key_input, 3, 1, 1, 3)
        grid.addWidget(StrongBodyLabel("Model"), 4, 0)
        grid.addWidget(self.model_input, 4, 1)
        grid.addWidget(self.models_combo, 4, 2)
        grid.addWidget(load_button, 4, 3)
        grid.addWidget(StrongBodyLabel("Translate concurrency"), 5, 0)
        grid.addWidget(self.concurrency_input, 5, 1)
        grid.addWidget(save_button, 6, 3)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _job(self, fn: Callable[[], Any], done: Callable[[Any], None], error: Callable[[str], None] | None = None) -> None:
        self.pool.start(Job(fn, done, error or self._error))

    def refresh_tasks(self) -> None:
        if not self.client or self._refresh_busy:
            return
        self._refresh_busy = True
        self._job(lambda: self.client.list_tasks(), self._tasks_loaded, self._refresh_error)

    def _refresh_error(self, message: str) -> None:
        self._refresh_busy = False
        self._error(message)

    def _tasks_loaded(self, tasks: list[dict[str, Any]]) -> None:
        self._refresh_busy = False
        self.tasks = tasks
        self.tasks_table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            values = [
                task.get("title") or task.get("url") or "",
                task.get("status") or "",
                task.get("current_stage") or "",
                task.get("created_at") or "",
                task.get("id") or "",
            ]
            for col, value in enumerate(values):
                self.tasks_table.setItem(row, col, _item(value))
        self.tasks_table.resizeColumnsToContents()
        if self.current_task_id:
            self.load_task_detail(self.current_task_id)

    def _select_task(self) -> None:
        selected = self.tasks_table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        if row >= len(self.tasks):
            return
        self.current_task_id = self.tasks[row]["id"]
        self.switchTo(self.detail_page)
        self.load_task_detail(self.current_task_id)

    def load_task_detail(self, task_id: str) -> None:
        if self.client:
            self._job(lambda: (self.client.get_task(task_id), self.client.get_log(task_id)), self._detail_loaded)

    def _detail_loaded(self, payload: tuple[dict[str, Any], str]) -> None:
        task, log = payload
        self.current_task = task
        stages = task.get("stages") or []
        completed = len([stage for stage in stages if stage.get("status") == "succeeded"])
        self.detail_title.setText(task.get("title") or task.get("url") or task.get("id"))
        self.detail_status.setText(f"{task.get('status')} / {task.get('current_stage') or 'done'} / {task.get('id')}")
        self.progress.setValue(round(completed / len(stages) * 100) if stages else 0)
        self.stages_table.setRowCount(len(stages))
        for row, stage in enumerate(stages):
            values = [
                stage.get("label") or stage.get("name") or "",
                stage.get("status") or "",
                _duration(stage.get("started_at"), stage.get("completed_at")),
                stage.get("error_message") or stage.get("last_message") or "",
            ]
            for col, value in enumerate(values):
                self.stages_table.setItem(row, col, _item(value))
        self.stages_table.resizeColumnsToContents()
        self.log_box.setPlainText(log)
        self.resume_button.setEnabled(task.get("status") == "failed")
        self.rerun_button.setEnabled(not _active(task.get("status")))
        self.delete_button.setEnabled(not _active(task.get("status")))
        self.open_video_button.setEnabled(bool(task.get("final_video_path")))

    def choose_upload_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose local video",
            str(self.repo_root),
            "Video Files (*.mp4 *.mov *.m4v *.mkv *.webm *.avi *.flv *.wmv);;All Files (*)",
        )
        if path:
            self.upload_file = Path(path)
            self.file_label.setText(self.upload_file.name)

    def create_task(self) -> None:
        if not self.client:
            return
        if self.upload_file:
            direction = self.direction_combo.currentText()
            self._job(lambda: self.client.upload_task(self.upload_file, direction), self._created_task)
            return
        url = self.youtube_input.text().strip() or self.bilibili_input.text().strip()
        if not url:
            self._error("Enter a URL or choose a local video.")
            return
        self._job(lambda: self.client.create_task(url), self._created_task)

    def _created_task(self, task: dict[str, Any]) -> None:
        self.youtube_input.clear()
        self.bilibili_input.clear()
        self.upload_file = None
        self.file_label.setText("No file selected")
        self.current_task_id = task["id"]
        self.refresh_tasks()
        self.load_task_detail(task["id"])
        self.switchTo(self.detail_page)

    def _task_action(self, action: str) -> None:
        if not self.client or not self.current_task_id:
            return
        task_id = self.current_task_id
        if action == "delete":
            if QMessageBox.question(self, "Delete task", "Delete this task and its files?") != QMessageBox.Yes:
                return
            self._job(lambda: self.client.delete_task(task_id), lambda _: self._after_delete())
        elif action == "rerun":
            self._job(lambda: self.client.rerun_task(task_id), self._created_task)
        elif action == "resume":
            self._job(lambda: self.client.resume_task(task_id), self._created_task)

    def _after_delete(self) -> None:
        self.current_task_id = None
        self.current_task = None
        self.detail_title.setText("No task selected")
        self.log_box.clear()
        self.refresh_tasks()
        self.switchTo(self.tasks_page)

    def open_final_video(self) -> None:
        task = self.current_task
        path = Path(task["final_video_path"]) if task and task.get("final_video_path") else None
        if path and path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            self._error("Final video is not available yet.")

    def load_settings(self) -> None:
        if not self.client:
            return

        def load() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
            assert self.client
            return self.client.get_cookie_info(), self.client.get_openai_settings(), self.client.get_ytdlp_settings()

        self._job(load, self._settings_loaded)

    def _settings_loaded(self, payload: tuple[dict[str, Any], dict[str, Any], dict[str, Any]]) -> None:
        cookie, openai, ytdlp = payload
        self.cookie_text.setPlaceholderText("Saved cookie exists" if cookie.get("exists") else "Paste cookie content")
        self.base_url_input.setText(openai.get("base_url", ""))
        self.api_key_input.setText(openai.get("api_key", "") if openai.get("has_api_key") else "")
        self.model_input.setText(openai.get("model", ""))
        self.concurrency_input.setText(openai.get("translate_concurrency", "50"))
        self.proxy_input.setText(ytdlp.get("proxy_port", ""))

    def load_models(self) -> None:
        if self.client:
            self._job(
                lambda: self.client.list_models(self.base_url_input.text().strip(), self.api_key_input.text().strip()),
                self._models_loaded,
            )

    def _models_loaded(self, models: list[str]) -> None:
        self.models_combo.clear()
        self.models_combo.addItems(models)
        if models:
            self.model_input.setText(models[0])

    def save_settings(self) -> None:
        if not self.client:
            return
        settings = {
            "base_url": self.base_url_input.text().strip(),
            "api_key": self.api_key_input.text().strip(),
            "model": self.model_input.text().strip(),
            "translate_concurrency": self.concurrency_input.text().strip(),
        }
        cookie = self.cookie_text.toPlainText().strip()
        proxy_port = self.proxy_input.text().strip()

        def save() -> None:
            assert self.client
            if cookie:
                self.client.save_cookie(cookie)
            self.client.save_openai_settings(settings)
            self.client.save_ytdlp_settings(proxy_port)

        self._job(save, lambda _: self._toast("Settings saved."))

    def _toast(self, message: str) -> None:
        InfoBar.success("YouDubPlusPlus", message, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=2200)

    def _error(self, message: str) -> None:
        InfoBar.error("YouDubPlusPlus", message, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=4500)


def _page(name: str) -> QWidget:
    page = QFrame()
    page.setObjectName(name)
    page.setAttribute(Qt.WA_StyledBackground, True)
    return page


def _item(value: Any):
    from PyQt5.QtWidgets import QTableWidgetItem

    item = QTableWidgetItem(str(value or ""))
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    return item


def _duration(start: str | None, end: str | None) -> str:
    if not start:
        return "-"
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00")) if end else datetime.now(start_dt.tzinfo)
    except ValueError:
        return end or "-"
    seconds = max(0, round((end_dt - start_dt).total_seconds()))
    return f"{seconds}s" if seconds < 60 else f"{seconds // 60}m{seconds % 60:02d}s"
