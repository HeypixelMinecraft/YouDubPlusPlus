from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests

from ..sources import SourceConfig

YOUDAO_TRANSLATE_URL = "https://dict.youdao.com/jsonapi_s?doctype=json&jsonversion=4"
YOUDAO_CLIENT = "webmain"
YOUDAO_KEYFROM = "webfanyi.webmain"
YOUDAO_SECRET = "t2he2k4m2g6QKRigK0KAmSpXKgAezywG"
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


def _md5(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def _sign(q: str, now_ms: int | None = None) -> dict[str, str]:
    suffix = len(f"{q}{YOUDAO_KEYFROM}") % 10
    timestamp = f"{now_ms if now_ms is not None else int(time.time() * 1000)}{suffix}"
    query_hash = _md5(f"{q}{YOUDAO_KEYFROM}")
    raw = f"{YOUDAO_CLIENT}{q}{timestamp}{YOUDAO_SECRET}{query_hash}"
    return {
        "sign": _md5(raw),
        "t": timestamp,
        "client": YOUDAO_CLIENT,
        "keyfrom": YOUDAO_KEYFROM,
    }


def _extract_translation(payload: Any) -> str:
    if isinstance(payload, dict):
        fanyi = payload.get("fanyi")
        if isinstance(fanyi, dict):
            tran = fanyi.get("tran")
            if isinstance(tran, str) and tran.strip():
                return tran.strip()

        ec = payload.get("ec")
        if isinstance(ec, dict):
            web_trans = ec.get("web_trans")
            if isinstance(web_trans, list):
                for item in web_trans:
                    if isinstance(item, str) and item.strip():
                        return item.strip()

        web_trans = payload.get("web_trans")
        if isinstance(web_trans, dict):
            for item in web_trans.get("web-translation") or []:
                if not isinstance(item, dict):
                    continue
                values = [
                    trans.get("value")
                    for trans in item.get("trans") or []
                    if isinstance(trans, dict) and trans.get("value")
                ]
                if values:
                    return "; ".join(str(value).strip() for value in values if str(value).strip())

        if isinstance(ec, dict):
            word = ec.get("word")
            words = word if isinstance(word, list) else [word]
            for word_item in words:
                if not isinstance(word_item, dict):
                    continue
                values: list[str] = []
                for tr in word_item.get("trs") or []:
                    if not isinstance(tr, dict):
                        continue
                    tran = tr.get("tran")
                    if isinstance(tran, str):
                        values.append(tran)
                        continue
                    for item in tr.get("tr") or []:
                        if isinstance(item, dict) and item.get("l", {}).get("i"):
                            values.extend(str(v) for v in item["l"]["i"])
                if values:
                    return "; ".join(value.strip() for value in values if value.strip())

    raise RuntimeError(f"Youdao Translate returned an unexpected response: {payload!r}")


def translate_sentence(text: str, source: SourceConfig) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    payload = {
        "needTranslate": "false",
        "dicts": json.dumps({"count": "1", "dicts": ["ec"]}, separators=(",", ":")),
        "q": stripped,
        **_sign(stripped),
    }
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://fanyi.youdao.com",
        "Referer": "https://fanyi.youdao.com/",
        "User-Agent": "Mozilla/5.0",
    }
    try:
        response = requests.post(YOUDAO_TRANSLATE_URL, data=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Youdao Translate request failed: {exc}") from exc
    return _extract_translation(response.json())


def translate_batch(texts: list[str], source: SourceConfig, *, concurrency: int = DEFAULT_CONCURRENCY) -> list[str]:
    if not texts:
        return []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        return list(pool.map(lambda text: translate_sentence(text, source), texts))


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
    dst_list = translate_batch(texts, source, concurrency=_concurrency_from(settings))

    translation = [
        {
            "src": text,
            "dst": dst,
            "src_lang": source.asr_language,
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
