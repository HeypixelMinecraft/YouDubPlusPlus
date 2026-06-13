from __future__ import annotations

import json

import pytest
import requests

from backend.app.adapters import google_translate
from backend.app.sources import detect_source


YT_SOURCE = detect_source("https://www.youtube.com/watch?v=abcdefghijk")


class FakeResponse:
    def __init__(self, payload, status_error: Exception | None = None):
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        return self.payload


def _write_asr(path) -> None:
    payload = {
        "result": {
            "language": "vi",
            "utterances": [
                {"text": "Hello.", "start_time": 0, "end_time": 1000},
                {
                    "text": "World.",
                    "start_time": 1000,
                    "end_time": 2000,
                    "additions": {"speaker": "2"},
                },
            ]
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_translate_batch_uses_google_response(monkeypatch):
    seen = []

    def fake_get(url, params, timeout):
        seen.append((url, params, timeout))
        return FakeResponse([[[f"zh:{params['q']}", params["q"], None, None]]])

    monkeypatch.setattr(google_translate.requests, "get", fake_get)

    out = google_translate.translate_batch(["Hello.", "World."], YT_SOURCE, concurrency=1)

    assert out == ["zh:Hello.", "zh:World."]
    assert seen[0][0] == google_translate.GOOGLE_TRANSLATE_URL
    assert seen[0][1]["sl"] == "auto"
    assert seen[0][1]["tl"] == "zh"


def test_translate_sentence_wraps_network_errors(monkeypatch):
    def fake_get(url, params, timeout):
        raise requests.RequestException("offline")

    monkeypatch.setattr(google_translate.requests, "get", fake_get)

    with pytest.raises(RuntimeError, match="Google Translate request failed"):
        google_translate.translate_sentence("Hello.", YT_SOURCE)


def test_translate_asr_writes_existing_translation_schema(tmp_path, monkeypatch):
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    asr_file = metadata / "asr.json"
    _write_asr(asr_file)
    monkeypatch.setattr(
        google_translate,
        "translate_batch",
        lambda texts, source, concurrency, source_language: [f"zh:{t}" for t in texts],
    )

    out = google_translate.translate_asr(asr_file, tmp_path, {"translate_concurrency": "1"}, YT_SOURCE)
    items = json.loads(out.read_text(encoding="utf-8"))["translation"]

    assert out.name == "translation.zh.json"
    assert items[0]["src"] == "Hello."
    assert items[0]["dst"] == "zh:Hello."
    assert items[0]["src_lang"] == "vi"
    assert items[0]["dst_lang"] == "zh"
    assert items[0]["speaker"] == "1"
    assert items[1]["speaker"] == "2"
