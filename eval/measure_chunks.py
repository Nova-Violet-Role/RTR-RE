"""Measure the chunk-count scale of the DTD-aware chunker over the staged corpus."""

from __future__ import annotations

import sys
from pathlib import Path

from execution.memory_engine import MemoryEngine

ROOT = Path("C:/RTR-RE")
STAGE = Path(r"C:\DTD_FAMILY\.dtd-file-examples")


def main() -> int:
    if not STAGE.exists():
        print(f"STAGE-MISSING {STAGE}")
        return 2
    files = sorted(STAGE.rglob("*"))
    files = [
        f for f in files if f.is_file() and f.suffix.lower() in (".dtd", ".mod", ".ent")
    ]
    print(f"FILES={len(files)}")
    engine = MemoryEngine()
    total = 0
    per_file = []
    try:
        for f in files:
            chunks = engine.chunk_dtd(f, f.name)
            total += len(chunks)
            per_file.append((f.name, len(chunks)))
        per_file.sort(key=lambda t: -t[1])
        print(f"TOTAL_CHUNKS={total}")
        print(f"MEAN_PER_FILE={total / max(1, len(files)):.1f}")
        for name, n in per_file[:10]:
            print(f"TOP {name} {n}")
    finally:
        engine.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
