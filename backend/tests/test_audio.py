from __future__ import annotations

import json
from pathlib import Path


def test_split_audio_by_segments_file_supports_translation_json(tmp_path: Path) -> None:
    from backend.app.adapters.audio import split_audio_by_segments_file
    from pydub import AudioSegment
    from pydub.generators import Sine

    audio_file = tmp_path / "vocals.wav"
    Sine(440).to_audio_segment(duration=3000).export(audio_file, format="wav")

    segments_file = tmp_path / "translation.json"
    segments_file.write_text(
        json.dumps(
            {
                "translation": [
                    {"text": "hello", "start_time": 0, "end_time": 1000},
                    {"text": "world", "start_time": 1500, "end_time": 2500},
                ]
            }
        ),
        encoding="utf-8",
    )

    session = tmp_path / "session"
    output_dir = split_audio_by_segments_file(audio_file, segments_file, session)

    files = sorted(output_dir.glob("*.wav"))
    assert len(files) == 2
    assert files[0].name == "0001.wav"
    assert files[1].name == "0002.wav"


def test_split_audio_by_segments_file_supports_asr_json(tmp_path: Path) -> None:
    from backend.app.adapters.audio import split_audio_by_segments_file
    from pydub.generators import Sine

    audio_file = tmp_path / "vocals.wav"
    Sine(440).to_audio_segment(duration=2000).export(audio_file, format="wav")

    segments_file = tmp_path / "asr.json"
    segments_file.write_text(
        json.dumps(
            {
                "result": {
                    "utterances": [
                        {"text": "hello", "start_time": 0, "end_time": 1200},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    session = tmp_path / "session"
    output_dir = split_audio_by_segments_file(audio_file, segments_file, session)

    assert len(list(output_dir.glob("*.wav"))) == 1
