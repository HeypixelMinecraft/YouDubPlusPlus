from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests

from ..sources import SourceConfig

GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
DEFAULT_CONCURRENCY = 50
REQUEST_TIMEOUT = 20


def _speaker(utt: dict[str, Any]) -> str:
    additions = utt.get("additions") or {}
    if isinstance(additions, dict):
        return str(additions.get("speaker") or "1")
    return "1"


def _concurrency_from(settings: dict[str, str]) -> int:
    raw = str(settings.get("translate_concurrency") or DEFAULT_CONCURRENCY).strip()
    return max(1, int(raw or DEFAULT_CONCURRENCY))


def _extract_translation(payload: Any) -> str:
    try:
        parts = payload[0]
    except (TypeError, IndexError) as exc:
        raise RuntimeError(f"Google Translate returned an unexpected response: {payload!r}") from exc
    text = "".join(str(part[0] or "") for part in parts if part and part[0] is not None).strip()
    if not text:
        raise RuntimeError(f"Google Translate returned an empty translation: {payload!r}")
    return text


def translate_sentence(text: str, source: SourceConfig, source_language: str = "auto") -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    params = {
        "client": "gtx",
        "sl": source_language or "auto",
        "tl": source.target_language,
        "dt": "t",
        "q": stripped,
    }
    try:
        response = requests.get(GOOGLE_TRANSLATE_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Google Translate request failed: {exc}") from exc
    return _extract_translation(response.json())


def translate_batch(
    texts: list[str],
    source: SourceConfig,
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
    source_language: str = "auto",
) -> list[str]:
    if not texts:
        return []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        return list(pool.map(lambda text: translate_sentence(text, source, source_language), texts))


def _asr_language(data: dict[str, Any]) -> str:
    language = str(data.get("result", {}).get("language") or "").strip().lower()
    return language or "auto"


def translate_asr(
    asr_file: Path,
    session: Path,
    settings: dict[str, str],
    source: SourceConfig,
) -> Path:
    output_file = session / "metadata" / f"translation.{source.target_language}.json"
    if output_file.exists():
        return output_file

    data = json.loads(asr_file.read_text(encoding="utf-8"))
    utterances = data["result"]["utterances"]
    texts = [u["text"].strip() for u in utterances]
    src_lang = _asr_language(data)
    dst_list = translate_batch(
        texts,
        source,
        concurrency=_concurrency_from(settings),
        source_language="auto",
    )

    translation = [
        {
            "src": text,
            "dst": dst,
            "src_lang": src_lang,
            "dst_lang": source.target_language,
            "start_time": utt["start_time"],
            "end_time": utt["end_time"],
            "speaker": _speaker(utt),
        }
        for text, dst, utt in zip(texts, dst_list, utterances)
    ]
    output_file.write_text(
        json.dumps({"translation": translation}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_file
