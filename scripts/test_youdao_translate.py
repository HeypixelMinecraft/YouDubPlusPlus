from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.adapters.youdao_translate import translate_batch  # noqa: E402
from backend.app.sources import detect_source  # noqa: E402


DEFAULT_TEXTS = [
    "Hello.",
    "This is a Youdao Translate connectivity test.",
    "Let's see whether the response can be parsed correctly.",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Test the Youdao Translate adapter with live requests.")
    parser.add_argument("text", nargs="*", help="Text to translate. Defaults to a few English sample sentences.")
    parser.add_argument("--concurrency", type=int, default=1, help="Request concurrency.")
    args = parser.parse_args()

    texts = args.text or DEFAULT_TEXTS
    source = detect_source("https://www.youtube.com/watch?v=abcdefghijk")

    start = time.perf_counter()
    translations = translate_batch(texts, source, concurrency=args.concurrency)
    elapsed = time.perf_counter() - start

    print(
        json.dumps(
            {
                "ok": True,
                "elapsed_seconds": round(elapsed, 3),
                "items": [
                    {
                        "src": src,
                        "dst": dst,
                    }
                    for src, dst in zip(texts, translations)
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
