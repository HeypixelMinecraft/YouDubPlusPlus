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


def test_synthesize_speech_uses_voxcpm(monkeypatch, tmp_path):
    from backend.app.adapters import tts

    calls = {}

    def fake_synthesize(text, reference_wav_path, output_file, log=None):
        calls["args"] = (text, reference_wav_path, output_file)
        output_file.write_bytes(b"wav")
        return output_file

    monkeypatch.setattr("backend.app.adapters.voxcpm.synthesize_speech", fake_synthesize)

    reference = tmp_path / "ref.wav"
    reference.write_bytes(b"ref")
    output = tmp_path / "out.wav"
    backend_name = tts.synthesize_speech("hello", reference, output)

    assert backend_name == "VoxCPM2"
    assert calls["args"] == ("hello", reference, output)
    assert output.exists()
