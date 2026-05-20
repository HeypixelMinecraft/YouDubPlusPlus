from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PyQt5.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..api_client import ApiClient
from ..backend_service import BackendService
from .fluent_compat import (
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


class WorkerSignals(QObject):
    done = pyqtSignal(object)
    error = pyqtSignal(str)


class ApiJob(QRunnable):
    def __init__(self, fn: Callable[[], Any], on_done: Callable[[Any], None], on_error: Callable[[str], None]):
        super().__init__()
        self.fn = fn
        self.on_done = on_done
        self.on_error = on_error
        self.signals = WorkerSignals()
        self.signals.done.connect(on_done)
        self.signals.error.connect(on_error)

    def run(self) -> None:
        try:
            self.signals.done.emit(self.fn())
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit(str(exc))


def _fmt(value: str | None) -> str:
    return value or "-"


def _is_active(status: str | None) -> bool:
    return status in {"queued", "running"}


class AppWindow(QMainWindow):
    def __init__(self, repo_root: Path) -> None:
        super().__init__()
        setTheme(Theme.AUTO)
        self.repo_root = repo_root
        self.backend = BackendService(repo_root)
        self.api: ApiClient | None = None
        self.pool = QThreadPool.globalInstance()
        self.tasks: list[dict[str, Any]] = []
        self.current_task_id: str | None = None
        self.current_task: dict[str, Any] | None = None
        self.upload_file: Path | None = None
        self._refresh_busy = False

        self.setWindowTitle("YouDub Desktop")
        self.resize(1180, 780)

        self.status_label = BodyLabel("Starting backend...")
        self.tabs = QTabWidget()
        self.create_tab = self._build_create_tab()
        self.detail_tab = self._build_detail_tab()
        self.settings_tab = self._build_settings_tab()
        self.tabs.addTab(self.create_tab, "Tasks")
        self.tabs.addTab(self.detail_tab, "Task detail")
        self.tabs.addTab(self.settings_tab, "Settings")

        root = QWidget(self)
        layout = QVBoxLayout(root)
        header = QHBoxLayout()
        title = SubtitleLabel("YouDub Desktop")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.status_label)
        layout.addLayout(header)
        layout.addWidget(self.tabs)
        self.setCentralWidget(root)

        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh_tasks)

        self._run_backend_start()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.timer.stop()
        self.backend.stop()
        super().closeEvent(event)

    def _build_create_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        form = QGridLayout()
        self.youtube_input = LineEdit()
        self.youtube_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.bilibili_input = LineEdit()
        self.bilibili_input.setPlaceholderText("https://www.bilibili.com/video/BV...")
        self.direction_combo = ComboBox()
        self.direction_combo.addItems(["en-zh", "zh-en"])
        self.file_label = BodyLabel("No local file selected")
        choose_file = PushButton("Choose video")
        choose_file.clicked.connect(self.choose_upload_file)
        create_button = PrimaryPushButton("Create task")
        create_button.clicked.connect(self.create_task)

        form.addWidget(QLabel("YouTube URL"), 0, 0)
        form.addWidget(self.youtube_input, 0, 1, 1, 3)
        form.addWidget(QLabel("Bilibili URL"), 1, 0)
        form.addWidget(self.bilibili_input, 1, 1, 1, 3)
        form.addWidget(QLabel("Local video"), 2, 0)
        form.addWidget(self.file_label, 2, 1)
        form.addWidget(choose_file, 2, 2)
        form.addWidget(self.direction_combo, 2, 3)
        form.addWidget(create_button, 3, 3)
        layout.addLayout(form)

        self.tasks_table = QTableWidget(0, 5)
        self.tasks_table.setHorizontalHeaderLabels(["Title", "Status", "Stage", "Created", "ID"])
        self.tasks_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tasks_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.tasks_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.tasks_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tasks_table.itemSelectionChanged.connect(self._select_task_from_table)
        layout.addWidget(self.tasks_table)

        return page

    def _build_detail_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.detail_title = SubtitleLabel("No task selected")
        self.detail_status = BodyLabel("")
        self.progress = ProgressBar()
        layout.addWidget(self.detail_title)
        layout.addWidget(self.detail_status)
        layout.addWidget(self.progress)

        buttons = QHBoxLayout()
        self.resume_button = PushButton("Resume")
        self.resume_button.clicked.connect(lambda: self._task_action("resume"))
        self.rerun_button = PushButton("Rerun")
        self.rerun_button.clicked.connect(lambda: self._task_action("rerun"))
        self.delete_button = PushButton("Delete")
        self.delete_button.clicked.connect(lambda: self._task_action("delete"))
        self.open_video_button = PrimaryPushButton("Open final video")
        self.open_video_button.clicked.connect(self.open_final_video)
        for button in (self.resume_button, self.rerun_button, self.delete_button, self.open_video_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.stages_table = QTableWidget(0, 4)
        self.stages_table.setHorizontalHeaderLabels(["Stage", "Status", "Duration", "Message"])
        self.stages_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.stages_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.stages_table)

        self.log_box = PlainTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)
        return page

    def _build_settings_tab(self) -> QWidget:
        page = QWidget()
        layout = QGridLayout(page)
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
        load_button.clicked.connect(self.load_models)
        save_button = PrimaryPushButton("Save settings")
        save_button.clicked.connect(self.save_settings)

        layout.addWidget(QLabel("YouTube cookie"), 0, 0)
        layout.addWidget(self.cookie_text, 0, 1, 1, 3)
        layout.addWidget(QLabel("yt-dlp proxy port"), 1, 0)
        layout.addWidget(self.proxy_input, 1, 1)
        layout.addWidget(QLabel("OpenAI base URL"), 2, 0)
        layout.addWidget(self.base_url_input, 2, 1, 1, 3)
        layout.addWidget(QLabel("OpenAI API key"), 3, 0)
        layout.addWidget(self.api_key_input, 3, 1, 1, 3)
        layout.addWidget(QLabel("Model"), 4, 0)
        layout.addWidget(self.model_input, 4, 1)
        layout.addWidget(self.models_combo, 4, 2)
        layout.addWidget(load_button, 4, 3)
        layout.addWidget(QLabel("Translate concurrency"), 5, 0)
        layout.addWidget(self.concurrency_input, 5, 1)
        layout.addWidget(save_button, 6, 3)
        return page

    def _run_backend_start(self) -> None:
        self._job(
            self.backend.start,
            lambda _: self._backend_ready(),
            lambda error: self._show_error(f"Backend failed to start: {error}"),
        )

    def _backend_ready(self) -> None:
        self.api = ApiClient(self.backend.base_url)
        self.status_label.setText(f"Backend: {self.backend.base_url}")
        self.refresh_tasks()
        self.load_settings()
        self.timer.start()

    def _job(self, fn: Callable[[], Any], done: Callable[[Any], None], error: Callable[[str], None] | None = None) -> None:
        self.pool.start(ApiJob(fn, done, error or self._show_error))

    def refresh_tasks(self) -> None:
        if not self.api or self._refresh_busy:
            return
        self._refresh_busy = True
        self._job(lambda: self.api.list_tasks(), self._tasks_loaded, self._refresh_error)

    def _refresh_error(self, error: str) -> None:
        self._refresh_busy = False
        self.status_label.setText(error)

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
                self.tasks_table.setItem(row, col, QTableWidgetItem(str(value)))
        if self.current_task_id:
            self.load_task_detail(self.current_task_id)

    def _select_task_from_table(self) -> None:
        selected = self.tasks_table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        if row >= len(self.tasks):
            return
        task_id = self.tasks[row]["id"]
        self.current_task_id = task_id
        self.tabs.setCurrentWidget(self.detail_tab)
        self.load_task_detail(task_id)

    def load_task_detail(self, task_id: str) -> None:
        if not self.api:
            return
        self._job(lambda: (self.api.get_task(task_id), self.api.get_log(task_id)), self._detail_loaded)

    def _detail_loaded(self, payload: tuple[dict[str, Any], str]) -> None:
        task, log = payload
        self.current_task = task
        stages = task.get("stages") or []
        completed = len([stage for stage in stages if stage.get("status") == "succeeded"])
        self.detail_title.setText(task.get("title") or task.get("url") or task.get("id"))
        self.detail_status.setText(
            f"Status: {_fmt(task.get('status'))} | Stage: {_fmt(task.get('current_stage'))} | ID: {task.get('id')}"
        )
        self.progress.setValue(round(completed / len(stages) * 100) if stages else 0)
        self.stages_table.setRowCount(len(stages))
        for row, stage in enumerate(stages):
            values = [
                stage.get("label") or stage.get("name") or "",
                stage.get("status") or "",
                self._duration(stage.get("started_at"), stage.get("completed_at")),
                stage.get("error_message") or stage.get("last_message") or "",
            ]
            for col, value in enumerate(values):
                self.stages_table.setItem(row, col, QTableWidgetItem(str(value)))
        self.log_box.setPlainText(log)
        self.resume_button.setEnabled(task.get("status") == "failed")
        self.rerun_button.setEnabled(not _is_active(task.get("status")))
        self.delete_button.setEnabled(not _is_active(task.get("status")))
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
        if not self.api:
            return
        youtube = self.youtube_input.text().strip()
        bilibili = self.bilibili_input.text().strip()
        if self.upload_file:
            direction = self.direction_combo.currentText()
            self._job(lambda: self.api.upload_task(self.upload_file, direction), self._created_task)
            return
        url = youtube or bilibili
        if not url:
            self._show_error("Enter a URL or choose a local video.")
            return
        self._job(lambda: self.api.create_task(url), self._created_task)

    def _created_task(self, task: dict[str, Any]) -> None:
        self.youtube_input.clear()
        self.bilibili_input.clear()
        self.upload_file = None
        self.file_label.setText("No local file selected")
        self.current_task_id = task["id"]
        self.refresh_tasks()
        self.load_task_detail(task["id"])
        self.tabs.setCurrentWidget(self.detail_tab)

    def _task_action(self, action: str) -> None:
        if not self.api or not self.current_task_id:
            return
        task_id = self.current_task_id
        if action == "delete":
            if QMessageBox.question(self, "Delete task", "Delete this task and its files?") != QMessageBox.Yes:
                return
            self._job(lambda: self.api.delete_task(task_id), lambda _: self._after_delete())
        elif action == "rerun":
            self._job(lambda: self.api.rerun_task(task_id), self._created_task)
        elif action == "resume":
            self._job(lambda: self.api.resume_task(task_id), self._created_task)

    def _after_delete(self) -> None:
        self.current_task_id = None
        self.current_task = None
        self.detail_title.setText("No task selected")
        self.log_box.clear()
        self.refresh_tasks()
        self.tabs.setCurrentWidget(self.create_tab)

    def open_final_video(self) -> None:
        if not self.current_task_id or not self.api:
            return
        task = self.current_task or next((item for item in self.tasks if item["id"] == self.current_task_id), None)
        path = task.get("final_video_path") if task else None
        if path and Path(path).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QDesktopServices.openUrl(QUrl(self.api.final_video_url(self.current_task_id)))

    def load_settings(self) -> None:
        if not self.api:
            return
        def load() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
            assert self.api
            return self.api.get_cookie_info(), self.api.get_openai_settings(), self.api.get_ytdlp_settings()
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
        if not self.api:
            return
        base_url = self.base_url_input.text().strip()
        api_key = self.api_key_input.text().strip()
        self._job(lambda: self.api.list_models(base_url, api_key), self._models_loaded)

    def _models_loaded(self, models: list[str]) -> None:
        self.models_combo.clear()
        self.models_combo.addItems(models)
        if models:
            self.model_input.setText(models[0])

    def save_settings(self) -> None:
        if not self.api:
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
            assert self.api
            if cookie:
                self.api.save_cookie(cookie)
            self.api.save_openai_settings(settings)
            self.api.save_ytdlp_settings(proxy_port)

        self._job(save, lambda _: self._info("Settings saved."))

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "YouDub Desktop", message)

    def _info(self, message: str) -> None:
        QMessageBox.information(self, "YouDub Desktop", message)

    @staticmethod
    def _duration(start: str | None, end: str | None) -> str:
        if not start:
            return "-"
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00")) if end else datetime.now(start_dt.tzinfo)
        except ValueError:
            return _fmt(end)
        seconds = max(0, round((end_dt - start_dt).total_seconds()))
        if seconds < 60:
            return f"{seconds}s"
        return f"{seconds // 60}m{seconds % 60:02d}s"
