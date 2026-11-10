# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Bullet-proof end-to-end: the live memory loop through real ONNX+Chroma.

One tiny project, real models, real vector DB, temp-isolated: submit
spans through the worker, auto-index tick, search finds them verbatim.
Relay, scoped index, janitor prune, holder PID and readable errors ride
along. If this file is green, the loop stands.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))

import memory_engine


class TestLiveLoopBulletproof(unittest.TestCase):
    def setUp(self):
        from memory_engine import MemoryEngine

        self.test_dir = Path(tempfile.mkdtemp())
        self.proj = self.test_dir / "projects" / "bulletproof"
        self.memdir = self.proj / ".opencode" / "memory"
        self.memdir.mkdir(parents=True)
        memory_engine.PROJECT_ROOTS = [self.test_dir / "projects"]
        memory_engine.PROJECTS_DIR = self.test_dir / "projects"
        memory_engine.DB_DIR = self.test_dir / "db"
        memory_engine.REGISTRY_FILE = self.test_dir / "registry.json"
        memory_engine.EXTRA_ROOTS_FILE = self.test_dir / "extra_roots.json"
        memory_engine.LEXIKON_GLOBAL_FILE = self.test_dir / "lexikon_global.json"
        self.engine = MemoryEngine()

    def tearDown(self):
        import shutil

        self.engine.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_worker_sink_tick_search_roundtrip_verbatim(self):
        import json

        from span_indexer import SpanIndexer
        from symbiose_worker import SessionSpanSink, SymbioseWorker

        marker = "BULLETPROOF-LOOP-7ZQ"
        worker = SymbioseWorker(
            SessionSpanSink(self.memdir),
            config={
                "trigger_tokens": 100,
                "target_tokens": 50,
                "max_keep_messages": 200,
            },
        )
        try:
            ticket = worker.submit(
                [
                    {"role": "user", "text": f"{marker} first question here"},
                    {"role": "assistant", "text": "filler " * 300},
                    {"role": "user", "text": "latest"},
                ]
            )
            done = worker.wait(ticket["id"], timeout=30)
        finally:
            worker.close()
        self.assertEqual(done["status"], "ready")
        spans = sorted(self.memdir.glob("rtrre-*.dtd"))
        self.assertTrue(spans)
        self.assertIn(marker, spans[0].read_text(encoding="utf-8"))
        indexer = SpanIndexer(self.engine, [self.test_dir / "projects"])
        try:
            stats = indexer.tick()
        finally:
            indexer.stop()
        self.assertGreaterEqual(stats["new"], 1)
        results = self.engine.search(marker)
        self.assertTrue(results)
        self.assertIn(marker, results[0]["document"])
        # Dense-only: BM25 must not be the only reason this passes —
        # the ONNX vectors themselves have to retrieve the span.
        dense_only = self.engine.search(marker, hybrid=False)
        self.assertTrue(dense_only)
        self.assertIn(marker, dense_only[0]["document"])

    def test_relay_case_is_ticket_free(self):
        import json

        from symbiose_worker import (
            SessionSpanSink,
            SymbioseWorker,
            drain_submit_sidecars,
        )

        sidecar = self.memdir / "rtrre-bp.submit.json"
        sidecar.write_text(
            json.dumps(
                {
                    "digest": "bp",
                    "ts": "2026-11-10T00:00:00Z",
                    "messages": [{"role": "user", "text": "one"}],
                }
            ),
            encoding="utf-8",
        )
        (self.memdir / "rtrre-bp.dtd").write_text(
            '<span id="span-0">\none\n</span>\n', encoding="utf-8"
        )
        worker = SymbioseWorker(SessionSpanSink(self.memdir))
        try:
            report = drain_submit_sidecars(worker, self.memdir)
        finally:
            worker.close()
        self.assertEqual(len(report["drained"]), 1)
        self.assertTrue(report["drained"][0].get("relayed"))

    def test_scoped_index_never_purges_outside_scope(self):
        keep = self.proj / "directives" / "keep.md"
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.write_text("# Keep\n\nstays indexed forever here", encoding="utf-8")
        self.engine.index_all()
        self.assertIn(str(keep), self.engine.load_registry())
        other = self.proj / "directives" / "other.md"
        other.write_text("# Other\n\nscoped newcomer file", encoding="utf-8")
        stats = self.engine.index_files([str(other)])
        self.assertEqual(stats["new"], 1)
        registry = self.engine.load_registry()
        self.assertIn(str(keep), registry)
        self.assertIn(str(other), registry)

    def test_janitor_prunes_dead_but_keeps_live(self):
        import shutil as _shutil

        dead = self.test_dir / "projects" / "deadproj"
        dead.mkdir()
        memory_engine.register_extra_root(dead)
        _shutil.rmtree(dead)
        report = self.engine.janitor(dry_run=False)
        roots = [str(r) for r in memory_engine._load_extra_roots()]
        self.assertNotIn(str(dead), roots)
        self.assertIn(str(dead), report.get("pruned_roots", []))

    def test_second_engine_names_its_holder(self):
        import os

        from memory_engine import MemoryEngine

        second = MemoryEngine()
        try:
            self.assertTrue(second.read_only)
            self.assertEqual(second._writer_holder, os.getpid())
        finally:
            second.close()

    def test_bare_errors_render_non_blank(self):
        import memory_cli
        import memory_mcp_server

        self.assertEqual(memory_cli._error_text(MemoryError()), "MemoryError()")
        self.assertEqual(memory_mcp_server._error_text(MemoryError()), "MemoryError()")


if __name__ == "__main__":
    unittest.main()
