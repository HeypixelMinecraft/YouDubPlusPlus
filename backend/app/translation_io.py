from __future__ import annotations

import json
from pathlib import Path

from . import database

REVIEW_MARKER = "translation.reviewed"


def translation_review_enabled() -> bool:
    settings = database.get_translate_settings()
    return settings.get("review_enabled", "true").strip().lower() in {"1", "true", "yes", "on"}


def find_translation_file(session: Path) -> Path:
    metadata = session / "metadata"
    matches = sorted(metadata.glob("translation.*.json"))
    if not matches:
        raise FileNotFoundError("Translation file not found.")
    return matches[0]


def is_translation_reviewed(session: Path) -> bool:
    return (session / "metadata" / REVIEW_MARKER).exists()


def mark_translation_reviewed(session: Path) -> None:
    marker = session / "metadata" / REVIEW_MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(database.now_iso(), encoding="utf-8")


def load_translation_segments(session: Path) -> tuple[Path, list[dict]]:
    path = find_translation_file(session)
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = data.get("translation")
    if not isinstance(segments, list):
        raise RuntimeError("Translation file is missing a 'translation' array.")
    return path, segments


def save_translation_segments(path: Path, segments: list[dict]) -> None:
    cleaned: list[dict] = []
    for index, item in enumerate(segments, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Segment {index} is invalid.")
        dst = (item.get("dst") or item.get("zh") or "").strip()
        if not dst:
            raise ValueError(f"Segment {index} translation cannot be empty.")
        updated = dict(item)
        updated["dst"] = dst
        cleaned.append(updated)
    path.write_text(json.dumps({"translation": cleaned}, ensure_ascii=False, indent=2), encoding="utf-8")
