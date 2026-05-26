from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PyQt5.QtCore import QObject, QRunnable, QSettings, Qt, QThreadPool, QTimer, QUrl, pyqtSignal
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
from ..mcp_service import current_mcp_service, start_mcp_service, stop_mcp_service
from .i18n import LANGUAGE_NAMES, configured_language, save_language, translate


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
        self._last_log_text = ""
        self._last_log_task_id: str | None = None
        self.language = configured_language()

        self.setWindowTitle("YouDubPlusPlus")
        self.resize(1220, 820)
        self.setMinimumSize(980, 680)
        if hasattr(self, "setMicaEffectEnabled"):
            self.setMicaEffectEnabled(True)

        self.tasks_page = self._build_tasks_page()
        self.detail_page = self._build_detail_page()
        self.mcp_page = self._build_mcp_page()
        self.settings_page = self._build_settings_page()
        self.addSubInterface(self.tasks_page, FIF.HOME, self._t("Tasks"))
        self.addSubInterface(self.detail_page, FIF.VIDEO, self._t("Detail"))
        self.addSubInterface(self.mcp_page, FIF.CONNECT, self._t("MCP"))
        self.addSubInterface(self.settings_page, FIF.SETTING, self._t("Settings"))

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh_tasks)
        self._job(self._init_client, self._ready)

    def _init_client(self) -> DirectClient:
        return DirectClient()

    def _t(self, text: str) -> str:
        return translate(text, self.language)

    def _ready(self, client: DirectClient) -> None:
        self.client = client
        self._toast(self._t("YouDub backend is running inside the desktop app."))
        self.refresh_tasks()
        self.load_settings()
        self.timer.start()

    def _build_tasks_page(self) -> QWidget:
        page = _page("tasksPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(18)

        title = SubtitleLabel(self._t("Create localization task"))
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
        self.file_label = BodyLabel(self._t("No file selected"))
        choose_file = PushButton(self._t("Choose video"))
        choose_file.setIcon(FIF.FOLDER)
        choose_file.clicked.connect(self.choose_upload_file)
        create_button = PrimaryPushButton(self._t("Create task"))
        create_button.setIcon(FIF.PLAY)
        create_button.clicked.connect(self.create_task)

        form.addWidget(StrongBodyLabel(self._t("YouTube URL")), 0, 0)
        form.addWidget(self.youtube_input, 0, 1, 1, 3)
        form.addWidget(StrongBodyLabel(self._t("Bilibili URL")), 1, 0)
        form.addWidget(self.bilibili_input, 1, 1, 1, 3)
        form.addWidget(StrongBodyLabel(self._t("Local video")), 2, 0)
        form.addWidget(self.file_label, 2, 1)
        form.addWidget(choose_file, 2, 2)
        form.addWidget(self.direction_combo, 2, 3)
        form.addWidget(create_button, 3, 3)
        layout.addWidget(card)

        layout.addWidget(SubtitleLabel(self._t("Task history")))
        self.tasks_table = TableWidget()
        self.tasks_table.setColumnCount(5)
        self.tasks_table.setHorizontalHeaderLabels(
            [self._t("Title"), self._t("Status"), self._t("Stage"), self._t("Created"), self._t("ID")]
        )
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
        self.detail_title = SubtitleLabel(self._t("No task selected"))
        self.detail_status = BodyLabel(self._t("Choose a task from the task history."))
        self.progress = ProgressBar()
        overview_layout.addWidget(self.detail_title)
        overview_layout.addWidget(self.detail_status)
        overview_layout.addWidget(self.progress)
        actions = QHBoxLayout()
        self.resume_button = PushButton(self._t("Resume"))
        self.resume_button.setIcon(FIF.PLAY)
        self.resume_button.clicked.connect(lambda: self._task_action("resume"))
        self.rerun_button = PushButton(self._t("Rerun"))
        self.rerun_button.setIcon(FIF.SYNC)
        self.rerun_button.clicked.connect(lambda: self._task_action("rerun"))
        self.delete_button = PushButton(self._t("Delete"))
        self.delete_button.setIcon(FIF.DELETE)
        self.delete_button.clicked.connect(lambda: self._task_action("delete"))
        self.open_video_button = PrimaryPushButton(self._t("Open final video"))
        self.open_video_button.setIcon(FIF.VIDEO)
        self.open_video_button.clicked.connect(self.open_final_video)
        for button in (self.resume_button, self.rerun_button, self.delete_button, self.open_video_button):
            actions.addWidget(button)
        actions.addStretch(1)
        overview_layout.addLayout(actions)
        layout.addWidget(overview)

        self.stages_table = TableWidget()
        self.stages_table.setColumnCount(4)
        self.stages_table.setHorizontalHeaderLabels(
            [self._t("Stage"), self._t("Status"), self._t("Duration"), self._t("Message")]
        )
        self.stages_table.verticalHeader().hide()
        self.stages_table.setEditTriggers(TableWidget.NoEditTriggers)
        layout.addWidget(self.stages_table, 1)

        self.log_box = PlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText(self._t("Logs will appear when a task starts."))
        layout.addWidget(self.log_box, 1)
        return page

    def _build_mcp_page(self) -> QWidget:
        page = _page("mcpPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(18)
        layout.addWidget(SubtitleLabel(self._t("MCP server")))

        card = CardWidget()
        grid = QGridLayout(card)
        grid.setContentsMargins(22, 18, 22, 18)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)

        settings = QSettings("YouDubPlusPlus", "YouDubPlusPlus")
        self.mcp_host_input = LineEdit()
        self.mcp_host_input.setText(str(settings.value("mcp/host", "127.0.0.1")))
        self.mcp_port_input = LineEdit()
        self.mcp_port_input.setText(str(settings.value("mcp/port", "8765")))
        self.mcp_status_label = BodyLabel("")
        self.mcp_url_label = BodyLabel("")
        self.mcp_url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.mcp_start_button = PrimaryPushButton(self._t("Start MCP"))
        self.mcp_start_button.setIcon(FIF.PLAY)
        self.mcp_start_button.clicked.connect(self.start_mcp_from_page)
        self.mcp_stop_button = PushButton(self._t("Stop MCP"))
        self.mcp_stop_button.setIcon(FIF.CLOSE)
        self.mcp_stop_button.clicked.connect(self.stop_mcp_from_page)

        grid.addWidget(StrongBodyLabel(self._t("Host")), 0, 0)
        grid.addWidget(self.mcp_host_input, 0, 1, 1, 2)
        grid.addWidget(StrongBodyLabel(self._t("Port")), 1, 0)
        grid.addWidget(self.mcp_port_input, 1, 1, 1, 2)
        grid.addWidget(StrongBodyLabel(self._t("Status")), 2, 0)
        grid.addWidget(self.mcp_status_label, 2, 1, 1, 2)
        grid.addWidget(StrongBodyLabel(self._t("SSE URL")), 3, 0)
        grid.addWidget(self.mcp_url_label, 3, 1, 1, 2)
        grid.addWidget(self.mcp_start_button, 4, 1)
        grid.addWidget(self.mcp_stop_button, 4, 2)
        layout.addWidget(card)
        layout.addStretch(1)
        self._refresh_mcp_page()
        return page

    def _build_settings_page(self) -> QWidget:
        page = _page("settingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(18)
        layout.addWidget(SubtitleLabel(self._t("Runtime settings")))

        card = CardWidget()
        grid = QGridLayout(card)
        grid.setContentsMargins(22, 18, 22, 18)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        self.cookie_text = TextEdit()
        self.cookie_text.setPlaceholderText(self._t("Paste Netscape YouTube cookie content"))
        cookie_help = BodyLabel(
            self._t(
                "Use get-cookies.txt LOCALLY to export YouTube cookies in Netscape format, "
                "then paste the content here: "
                "https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc"
            )
        )
        cookie_help.setWordWrap(True)
        self.language_combo = ComboBox()
        for code, name in LANGUAGE_NAMES.items():
            self.language_combo.addItem(name, userData=code)
        index = self.language_combo.findData(self.language)
        self.language_combo.setCurrentIndex(max(index, 0))
        self.proxy_input = LineEdit()
        self.proxy_input.setPlaceholderText("7890")
        self.translation_mode_combo = ComboBox()
        self.translation_mode_combo.addItem("OpenAI", userData="openai")
        self.translation_mode_combo.addItem("Google Translate", userData="google")
        self.translation_mode_combo.addItem("Youdao Translate", userData="youdao")
        self.translation_mode_combo.currentIndexChanged.connect(self._update_translation_settings_visibility)
        self.base_url_input = LineEdit()
        self.api_key_input = LineEdit()
        self.api_key_input.setEchoMode(LineEdit.Password)
        self.model_input = LineEdit()
        self.concurrency_input = LineEdit()
        self.models_combo = ComboBox()
        load_button = PushButton(self._t("Get models"))
        load_button.setIcon(FIF.CLOUD_DOWNLOAD)
        load_button.clicked.connect(self.load_models)
        save_button = PrimaryPushButton(self._t("Save settings"))
        save_button.setIcon(FIF.SAVE)
        save_button.clicked.connect(self.save_settings)
        self.openai_setting_widgets = [
            StrongBodyLabel(self._t("OpenAI base URL")),
            StrongBodyLabel(self._t("OpenAI API key")),
            StrongBodyLabel(self._t("Model")),
            self.base_url_input,
            self.api_key_input,
            self.model_input,
            self.models_combo,
            load_button,
        ]
        openai_base_label, openai_key_label, openai_model_label = self.openai_setting_widgets[:3]

        grid.addWidget(StrongBodyLabel(self._t("Interface language")), 0, 0)
        grid.addWidget(self.language_combo, 0, 1)
        grid.addWidget(BodyLabel(self._t("Language changes take effect after restart.")), 0, 2, 1, 2)
        grid.addWidget(StrongBodyLabel(self._t("YouTube cookie")), 1, 0)
        grid.addWidget(self.cookie_text, 1, 1, 1, 3)
        grid.addWidget(cookie_help, 2, 1, 1, 3)
        grid.addWidget(StrongBodyLabel(self._t("yt-dlp proxy port")), 3, 0)
        grid.addWidget(self.proxy_input, 3, 1)
        grid.addWidget(StrongBodyLabel(self._t("Translation mode")), 4, 0)
        grid.addWidget(self.translation_mode_combo, 4, 1)
        grid.addWidget(openai_base_label, 5, 0)
        grid.addWidget(self.base_url_input, 5, 1, 1, 3)
        grid.addWidget(openai_key_label, 6, 0)
        grid.addWidget(self.api_key_input, 6, 1, 1, 3)
        grid.addWidget(openai_model_label, 7, 0)
        grid.addWidget(self.model_input, 7, 1)
        grid.addWidget(self.models_combo, 7, 2)
        grid.addWidget(load_button, 7, 3)
        grid.addWidget(StrongBodyLabel(self._t("Translate concurrency")), 8, 0)
        grid.addWidget(self.concurrency_input, 8, 1)
        grid.addWidget(save_button, 9, 3)
        self._update_translation_settings_visibility()
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
                self._t(task.get("status") or ""),
                self._t(task.get("current_stage") or ""),
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
        self.detail_status.setText(
            f"{self._t(task.get('status') or '')} / {self._t(task.get('current_stage') or 'done')} / {task.get('id')}"
        )
        self.progress.setValue(round(completed / len(stages) * 100) if stages else 0)
        self.stages_table.setRowCount(len(stages))
        for row, stage in enumerate(stages):
            values = [
                self._t(stage.get("label") or stage.get("name") or ""),
                self._t(stage.get("status") or ""),
                _duration(stage.get("started_at"), stage.get("completed_at")),
                stage.get("error_message") or self._t(stage.get("last_message") or ""),
            ]
            for col, value in enumerate(values):
                self.stages_table.setItem(row, col, _item(value))
        self.stages_table.resizeColumnsToContents()
        self._set_log_text(task.get("id") or "", log)
        self.resume_button.setEnabled(task.get("status") == "failed")
        self.rerun_button.setEnabled(not _active(task.get("status")))
        self.delete_button.setEnabled(not _active(task.get("status")))
        self.open_video_button.setEnabled(bool(task.get("final_video_path")))

    def choose_upload_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._t("Choose local video"),
            str(self.repo_root),
            self._t("Video Files (*.mp4 *.mov *.m4v *.mkv *.webm *.avi *.flv *.wmv);;All Files (*)"),
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
            self._error(self._t("Enter a URL or choose a local video."))
            return
        self._job(lambda: self.client.create_task(url), self._created_task)

    def _created_task(self, task: dict[str, Any]) -> None:
        self.youtube_input.clear()
        self.bilibili_input.clear()
        self.upload_file = None
        self.file_label.setText(self._t("No file selected"))
        self.current_task_id = task["id"]
        self.refresh_tasks()
        self.load_task_detail(task["id"])
        self.switchTo(self.detail_page)

    def _task_action(self, action: str) -> None:
        if not self.client or not self.current_task_id:
            return
        task_id = self.current_task_id
        if action == "delete":
            if QMessageBox.question(self, self._t("Delete task"), self._t("Delete this task and its files?")) != QMessageBox.Yes:
                return
            self._job(lambda: self.client.delete_task(task_id), lambda _: self._after_delete())
        elif action == "rerun":
            self._job(lambda: self.client.rerun_task(task_id), self._created_task)
        elif action == "resume":
            self._job(lambda: self.client.resume_task(task_id), self._created_task)

    def _after_delete(self) -> None:
        self.current_task_id = None
        self.current_task = None
        self.detail_title.setText(self._t("No task selected"))
        self.log_box.clear()
        self._last_log_text = ""
        self._last_log_task_id = None
        self.refresh_tasks()
        self.switchTo(self.tasks_page)

    def _set_log_text(self, task_id: str, log: str) -> None:
        if task_id == self._last_log_task_id and log == self._last_log_text:
            return

        scrollbar = self.log_box.verticalScrollBar()
        previous_value = scrollbar.value()
        was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 4
        task_changed = task_id != self._last_log_task_id

        self.log_box.setPlainText(log)
        if task_changed or was_at_bottom:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(min(previous_value, scrollbar.maximum()))

        self._last_log_text = log
        self._last_log_task_id = task_id

    def open_final_video(self) -> None:
        task = self.current_task
        path = Path(task["final_video_path"]) if task and task.get("final_video_path") else None
        if path and path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            self._error(self._t("Final video is not available yet."))

    def load_settings(self) -> None:
        if not self.client:
            return

        def load() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
            assert self.client
            return (
                self.client.get_cookie_info(),
                self.client.get_openai_settings(),
                self.client.get_ytdlp_settings(),
                self.client.get_translate_settings(),
            )

        self._job(load, self._settings_loaded)

    def _settings_loaded(
        self,
        payload: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
    ) -> None:
        cookie, openai, ytdlp, translate_settings = payload
        self.cookie_text.setPlaceholderText(
            self._t("Saved cookie exists") if cookie.get("exists") else self._t("Paste cookie content")
        )
        mode_index = self.translation_mode_combo.findData(translate_settings.get("mode", "openai"))
        self.translation_mode_combo.setCurrentIndex(max(mode_index, 0))
        self.base_url_input.setText(openai.get("base_url", ""))
        self.api_key_input.setText(openai.get("api_key", "") if openai.get("has_api_key") else "")
        self.model_input.setText(openai.get("model", ""))
        self.concurrency_input.setText(openai.get("translate_concurrency", "50"))
        self.proxy_input.setText(ytdlp.get("proxy_port", ""))
        self._update_translation_settings_visibility()

    def load_models(self) -> None:
        if self.client and self._current_translation_mode() == "openai":
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
        language = self.language_combo.currentData() or self.language
        translation_mode = self.translation_mode_combo.currentData() or "openai"

        def save() -> None:
            assert self.client
            save_language(language)
            if cookie:
                self.client.save_cookie(cookie)
            self.client.save_translate_settings(translation_mode)
            self.client.save_openai_settings(settings)
            self.client.save_ytdlp_settings(proxy_port)

        self._job(save, lambda _: self._toast(self._t("Settings saved.")))

    def start_mcp_from_page(self) -> None:
        host = self.mcp_host_input.text().strip() or "127.0.0.1"
        raw_port = self.mcp_port_input.text().strip() or "8765"
        if not raw_port.isdigit() or not 1024 <= int(raw_port) <= 65535:
            self._error(self._t("MCP port must be between 1024 and 65535."))
            return

        port = int(raw_port)
        settings = QSettings("YouDubPlusPlus", "YouDubPlusPlus")
        settings.setValue("mcp/host", host)
        settings.setValue("mcp/port", str(port))

        try:
            info = start_mcp_service(host, port)
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))
            return
        self._refresh_mcp_page()
        if info:
            self._toast(f"{self._t('MCP server started')}: {info.sse_url}")
        else:
            self._error(self._t("MCP server is disabled."))

    def stop_mcp_from_page(self) -> None:
        stop_mcp_service()
        self._refresh_mcp_page()
        self._toast(self._t("MCP server stopped"))

    def _refresh_mcp_page(self) -> None:
        info = current_mcp_service()
        running = info is not None
        self.mcp_status_label.setText(self._t("Running") if running else self._t("Stopped"))
        self.mcp_url_label.setText(info.sse_url if info else self._t("Start MCP to show the SSE URL."))
        self.mcp_start_button.setEnabled(not running)
        self.mcp_stop_button.setEnabled(running)

    def _toast(self, message: str) -> None:
        InfoBar.success("YouDubPlusPlus", message, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=2200)

    def _error(self, message: str) -> None:
        InfoBar.error("YouDubPlusPlus", message, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=4500)

    def _current_translation_mode(self) -> str:
        return self.translation_mode_combo.currentData() or "openai"

    def _update_translation_settings_visibility(self) -> None:
        show_openai = self._current_translation_mode() == "openai"
        for widget in getattr(self, "openai_setting_widgets", []):
            widget.setVisible(show_openai)


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
