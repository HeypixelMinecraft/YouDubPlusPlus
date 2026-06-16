from __future__ import annotations

import os

from PyQt5.QtCore import QLocale, QSettings


LANGUAGE_NAMES = {
    "zh_CN": "简体中文",
    "en_US": "English",
}

_ZH_CN = {
    "Tasks": "任务",
    "Detail": "详情",
    "Settings": "设置",
    "MCP": "MCP",
    "MCP server": "MCP 服务",
    "Host": "监听地址",
    "Port": "端口",
    "Status": "状态",
    "SSE URL": "SSE 地址",
    "Start MCP": "启动 MCP",
    "Stop MCP": "停止 MCP",
    "Running": "运行中",
    "Stopped": "已停止",
    "Start MCP to show the SSE URL.": "启动 MCP 后显示 SSE 地址。",
    "MCP port must be between 1024 and 65535.": "MCP 端口必须在 1024 到 65535 之间。",
    "MCP server started": "MCP 服务已启动",
    "MCP server stopped": "MCP 服务已停止",
    "MCP server is disabled.": "MCP 服务已禁用。",
    "Environment check": "环境检查",
    "Unsupported environment detected: {os_name}. YouDub desktop mainly supports Windows 10/11, Linux, Ubuntu, and NVIDIA GPU.": "检测到不受支持的系统：{os_name}。YouDub 桌面端主要支持 Windows 10/11、Linux 和 Ubuntu 、NVIDIA GPU上使用。",
    "YouDub backend is running inside the desktop app.": "YouDub 后端已在桌面应用内运行。",
    "Create localization task": "创建本地化任务",
    "No file selected": "未选择文件",
    "Choose video": "选择视频",
    "Create task": "创建任务",
    "YouTube URL": "YouTube 链接",
    "Bilibili URL": "Bilibili 链接",
    "Local video": "本地视频",
    "Task history": "任务历史",
    "Title": "标题",
    "Status": "状态",
    "Stage": "阶段",
    "Created": "创建时间",
    "ID": "ID",
    "No task selected": "未选择任务",
    "Choose a task from the task history.": "请从任务历史中选择一个任务。",
    "Resume": "继续",
    "Rerun": "重新运行",
    "Delete": "删除",
    "Open final video": "打开最终视频",
    "Duration": "耗时",
    "Message": "消息",
    "Logs will appear when a task starts.": "任务开始后日志会显示在这里。",
    "Runtime settings": "运行设置",
    "Interface language": "界面语言",
    "Language changes take effect after restart.": "语言设置会在重启后生效。",
    "Paste Netscape YouTube cookie content": "请使用 get-cookies.txt LOCALLY 插件导出 Netscape 格式的 YouTube cookie，然后粘贴到这里。",
    "Use get-cookies.txt LOCALLY to export YouTube cookies in Netscape format, then paste the content here: https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc": "请使用 get-cookies.txt LOCALLY 插件导出 Netscape 格式的 YouTube cookie，然后粘贴到这里：https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc",
    "Get models": "获取模型",
    "Save settings": "保存设置",
    "YouTube cookie": "YouTube cookie",
    "yt-dlp proxy port": "yt-dlp 代理端口",
    "Translation mode": "翻译模式",
    "Youdao Translate": "有道翻译",
    "OpenAI base URL": "OpenAI 接口地址",
    "OpenAI API key": "OpenAI API key",
    "Model": "模型",
    "Translate concurrency": "翻译并发数",
    "Choose local video": "选择本地视频",
    "Video Files (*.mp4 *.mov *.m4v *.mkv *.webm *.avi *.flv *.wmv);;All Files (*)": "视频文件 (*.mp4 *.mov *.m4v *.mkv *.webm *.avi *.flv *.wmv);;所有文件 (*)",
    "Enter a URL or choose a local video.": "请输入链接或选择一个本地视频。",
    "Delete task": "删除任务",
    "Delete this task and its files?": "要删除这个任务及其文件吗？",
    "Final video is not available yet.": "最终视频还不可用。",
    "Saved cookie exists": "已保存 cookie",
    "Paste cookie content": "粘贴 Netscape 格式 cookie 内容",
    "Settings saved.": "设置已保存。",
    "done": "完成",
    "queued": "排队中",
    "running": "运行中",
    "succeeded": "已成功",
    "failed": "失败",
    "Download": "下载",
    "Demucs": "Demucs 分离",
    "Whisper": "Whisper 识别",
    "Split sentences": "句子切分",
    "Translate": "翻译",
    "Split audio": "切分音频",
    "TTS": "语音合成",
    "TTS tool": "语音合成工具",
    "Enter text to synthesize": "输入要合成的文本",
    "No reference audio selected": "未选择参考音频",
    "Choose reference audio": "选择参考音频",
    "Auto save to workfolder/tts_tool": "自动保存到 workfolder/tts_tool",
    "Choose output file": "选择输出文件",
    "Generate speech": "生成语音",
    "Open output audio": "打开输出音频",
    "Reference audio": "参考音频",
    "Output file": "输出文件",
    "Text": "文本",
    "TTS logs will appear here.": "语音合成日志会显示在这里。",
    "Enter text to synthesize.": "请输入要合成的文本。",
    "Choose a reference audio file.": "请选择一个参考音频文件。",
    "Generating speech...": "正在生成语音...",
    "Speech generated with {backend}.": "已使用 {backend} 生成语音。",
    "Output audio is not available yet.": "输出音频还不可用。",
    "Audio Files (*.wav *.mp3 *.flac *.ogg *.m4a);;All Files (*)": "音频文件 (*.wav *.mp3 *.flac *.ogg *.m4a);;所有文件 (*)",
    "WAV Files (*.wav);;All Files (*)": "WAV 文件 (*.wav);;所有文件 (*)",
    "Merge audio": "混合音频",
    "Merge video": "合成视频",
    "download": "下载",
    "separate": "Demucs 分离",
    "asr": "Whisper 识别",
    "asr_fix": "句子切分",
    "translate": "翻译",
    "split_audio": "切分音频",
    "tts": "语音合成",
    "merge_audio": "混合音频",
    "merge_video": "合成视频",
    "Started": "已开始",
    "Completed": "已完成",
    "Failed": "失败",
}


def configured_language() -> str:
    configured = os.getenv("YOUDUB_APP_LANGUAGE", "").strip()
    if configured in LANGUAGE_NAMES:
        return configured

    saved = QSettings("YouDubPlusPlus", "YouDubPlusPlus").value("language", "auto")
    if saved in LANGUAGE_NAMES:
        return str(saved)

    return "zh_CN" if QLocale.system().name().lower().startswith("zh") else "en_US"


def save_language(language: str) -> None:
    if language in LANGUAGE_NAMES:
        QSettings("YouDubPlusPlus", "YouDubPlusPlus").setValue("language", language)


def translate(text: str, language: str | None = None) -> str:
    if (language or configured_language()) == "zh_CN":
        return _ZH_CN.get(text, text)
    return text
