# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Preset x CPU performance: index + search latency per thread mode.

Fixed corpus (12 files), fixed queries (10), isolated DB per combo.
Each combo runs in its own engine with its own ONNX pool, so thread
modes are honestly separated. Outputs eval/results/preset-perf.json.

Usage: uv run python eval/bench_preset_perf.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "execution"))

import memory_engine as mem
from memory_engine import MemoryEngine

THREAD_MODES = (2, 4, 8)
QUERIES = [
    "quokka router nocturnal dispatch",
    "badger arbiter midnight ledger",
    "tide tables gateways packets",
    "burrow index moonrise cache",
    "throughput ceiling dusk cycle",
    "latency budget hop gateway",
    "fallback cache burrow",
    "midnight roundtrips bridge",
    "nocturnal packets gateway",
    "dawn tide tables caches",
]
DOCS = [
    "# Quokka Routing Notes\n\nThe quokka router6834 dispatches nocturnal packets through the southern gateway. Latency budget is eleven milliseconds per hop. The fallback cache lives beside the burrow index and warms on first moonrise.\n",
    "# Badger Latency Ledger\n\nThe badger arbiter counts midnight roundtrips across the northern bridge. Throughput ceiling is fortytwo thousand packets per dusk cycle.\n",
    "# General Packet Lore\n\nPackets travel at dawn. Gateways open and close with the tide tables. Caches warm slowly when nobody watches them.\n",
]


def run_combo(threads: int) -> dict:
    os.environ["OPENCODE_MEMORY_EMBED_THREADS"] = str(threads)
    os.environ["OPENCODE_MEMORY_EMBED_MODELS"] = "BAAI/bge-base-en-v1.5"
    with tempfile.TemporaryDirectory(prefix="rtrre-presetperf-") as td:
        root = Path(td)
        proj = root / "projects" / "perfproj"
        d = proj / "directives"
        d.mkdir(parents=True)
        for i in range(12):
            (d / f"doc{i:02d}.md").write_text(DOCS[i % 3], encoding="utf-8")
        saved = (
            mem.PROJECT_ROOTS,
            mem.PROJECTS_DIR,
            mem.DB_DIR,
            mem.REGISTRY_FILE,
            mem.EXTRA_ROOTS_FILE,
            mem.LEXIKON_GLOBAL_FILE,
        )
        mem.PROJECT_ROOTS = [root / "projects"]
        mem.PROJECTS_DIR = root / "projects"
        mem.DB_DIR = root / "db"
        mem.REGISTRY_FILE = root / "registry.json"
        mem.EXTRA_ROOTS_FILE = root / "extra.json"
        mem.LEXIKON_GLOBAL_FILE = root / "lex.json"
        try:
            engine = MemoryEngine()
            try:
                t0 = time.time()
                st = engine.index_all()
                t_index = time.time() - t0
                lat = []
                for q in QUERIES:
                    t1 = time.time()
                    engine.search(q, k=3)
                    lat.append((time.time() - t1) * 1000.0)
                lat.sort()
                return {
                    "threads": threads,
                    "files": st["new"],
                    "index_s": round(t_index, 2),
                    "search_p50_ms": round(lat[len(lat) // 2], 1),
                    "search_max_ms": round(max(lat), 1),
                }
            finally:
                engine.close()
        finally:
            (
                mem.PROJECT_ROOTS,
                mem.PROJECTS_DIR,
                mem.DB_DIR,
                mem.REGISTRY_FILE,
                mem.EXTRA_ROOTS_FILE,
                mem.LEXIKON_GLOBAL_FILE,
            ) = saved


def main() -> int:
    results: dict = {"tool": "preset-perf v1", "combos": []}
    for t in THREAD_MODES:
        row = run_combo(t)
        results["combos"].append(row)
        print(
            f"[T{t}] index={row['index_s']}s "
            f"search_p50={row['search_p50_ms']}ms max={row['search_max_ms']}ms"
        )
    out = Path(__file__).parent / "results" / "preset-perf.json"
    out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
