from __future__ import annotations


def test_tts_uses_voxcpm(monkeypatch, tmp_path):
    from backend.app.adapters import tts

    calls = {}

    def fake_vox(translation_file, vocals_dir, session):
        calls["args"] = (translation_file, vocals_dir, session)
        return tmp_path / "tts"

    monkeypatch.setattr(tts, "_voxcpm", lambda: fake_vox)

    out, backend_name = tts.generate_tts(tmp_path / "a.json", tmp_path / "b", tmp_path / "c")

    assert backend_name == "VoxCPM2"
    assert calls["args"] == (tmp_path / "a.json", tmp_path / "b", tmp_path / "c")
    assert out == tmp_path / "tts"
