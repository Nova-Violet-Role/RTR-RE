"""Measure fastembed throughput on short texts (the DTD chunk shape)."""

from __future__ import annotations

import time

from execution.memory_engine import MemoryEngine

N = 2000
TEXT = (
    "Document: sample.dtd\nSection: ELEMENT: book\n\n<!ELEMENT book (title, chapter+)>"
)


def main() -> int:
    engine = MemoryEngine()
    try:
        texts = [TEXT] * N
        t0 = time.time()
        out = engine.embed_all(texts)
        dt = time.time() - t0
        for slug, vecs in out.items():
            per_sec = N / dt if dt > 0 else float("inf")
            print(f"MODEL {slug}: {N} texts in {dt:.1f}s -> {per_sec:.1f}/s")
        return 0
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
