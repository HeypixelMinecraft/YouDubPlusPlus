from __future__ import annotations

from pathlib import Path

from ..sources import SourceConfig


def translate_asr(
    asr_file: Path,
    session: Path,
    translate_settings: dict[str, str],
    openai_settings: dict[str, str],
    source: SourceConfig,
) -> Path:
    mode = translate_settings.get("mode", "openai")
    if mode == "google":
        from .google_translate import translate_asr as google_translate_asr

        shared_settings = {
            "translate_concurrency": openai_settings.get("translate_concurrency", ""),
        }
        return google_translate_asr(asr_file, session, shared_settings, source)
    if mode == "youdao":
        from .youdao_translate import translate_asr as youdao_translate_asr

        shared_settings = {
            "translate_concurrency": openai_settings.get("translate_concurrency", ""),
        }
        return youdao_translate_asr(asr_file, session, shared_settings, source)
    if mode == "openai":
        from .openai_translate import translate_asr as openai_translate_asr

        return openai_translate_asr(asr_file, session, openai_settings, source)
    raise ValueError(f"Unsupported translation mode: {mode}")
