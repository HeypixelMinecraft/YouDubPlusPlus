from __future__ import annotations

import json

import pytest
import requests

from backend.app.adapters import youdao_translate
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
            "utterances": [
                {"text": "Hello.", "start_time": 0, "end_time": 1000},
                {"text": "World.", "start_time": 1000, "end_time": 2000, "additions": {"speaker": "2"}},
            ]
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_youdao_sign_matches_webmain_sample():
    signed = youdao_translate._sign("hello", 1779526187456)

    assert signed == {
        "sign": "f7806d0a140056aea826df573e9af4e7",
        "t": "17795261874561",
        "client": "webmain",
        "keyfrom": "webfanyi.webmain",
    }


def test_translate_batch_uses_youdao_response(monkeypatch):
    seen = []

    def fake_post(url, data, headers, timeout):
        seen.append((url, data, headers, timeout))
        return FakeResponse({"fanyi": {"tran": f"zh:{data['q']}"}})

    monkeypatch.setattr(youdao_translate.requests, "post", fake_post)

    out = youdao_translate.translate_batch(["Hello.", "World."], YT_SOURCE, concurrency=1)

    assert out == ["zh:Hello.", "zh:World."]
    assert seen[0][0] == youdao_translate.YOUDAO_TRANSLATE_URL
    assert seen[0][1]["needTranslate"] == "true"
    assert seen[0][1]["client"] == "webmain"
    assert seen[0][1]["keyfrom"] == "webfanyi.webmain"
    assert "sign" in seen[0][1]


def test_extract_translation_prefers_youdao_ec_web_trans():
    payload = {
        "web_trans": {
            "web-translation": [
                {"trans": [{"value": "fallback"}]},
            ]
        },
        "ec": {
            "web_trans": ["您好", "哈啰", "喂"],
            "word": {"trs": [{"tran": "喂，你好"}]},
        },
    }

    assert youdao_translate._extract_translation(payload) == "您好"


def test_translate_sentence_wraps_network_errors(monkeypatch):
    def fake_post(url, data, headers, timeout):
        raise requests.RequestException("offline")

    monkeypatch.setattr(youdao_translate.requests, "post", fake_post)

    with pytest.raises(RuntimeError, match="Youdao Translate request failed"):
        youdao_translate.translate_sentence("Hello.", YT_SOURCE)


def test_translate_asr_writes_existing_translation_schema(tmp_path, monkeypatch):
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    asr_file = metadata / "asr.json"
    _write_asr(asr_file)
    monkeypatch.setattr(youdao_translate, "translate_batch", lambda texts, source, concurrency: [f"zh:{t}" for t in texts])

    out = youdao_translate.translate_asr(asr_file, tmp_path, {"translate_concurrency": "1"}, YT_SOURCE)
    items = json.loads(out.read_text(encoding="utf-8"))["translation"]

    assert out.name == "translation.zh.json"
    assert items[0]["src"] == "Hello."
    assert items[0]["dst"] == "zh:Hello."
    assert items[0]["src_lang"] == "en"
    assert items[0]["dst_lang"] == "zh"
    assert items[0]["speaker"] == "1"
    assert items[1]["speaker"] == "2"
