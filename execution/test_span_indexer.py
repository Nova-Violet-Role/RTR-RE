# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Background span indexer tests (RRD-169).

The indexer thread watches project memory dirs and indexes new/changed
spans through the bounded index_files call — this is what makes sunk
spans searchable without a manual index run.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.absolute()))

import memory_engine


class TestSpanIndexer(unittest.TestCase):
    def setUp(self):
        from span_indexer import SpanIndexer

        self.test_dir = Path(tempfile.mkdtemp())
        self.proj = self.test_dir / "projects" / "idxproj"
        self.memdir = self.proj / ".opencode" / "memory"
        self.memdir.mkdir(parents=True)
        memory_engine.PROJECT_ROOTS = [self.test_dir / "projects"]
        memory_engine.PROJECTS_DIR = self.test_dir / "projects"
        memory_engine.DB_DIR = self.test_dir / "db"
        memory_engine.REGISTRY_FILE = self.test_dir / "registry.json"
        memory_engine.EXTRA_ROOTS_FILE = self.test_dir / "extra_roots.json"
        memory_engine.LEXIKON_GLOBAL_FILE = self.test_dir / "lexikon_global.json"
        from memory_engine import MemoryEngine

        self.engine = MemoryEngine()
        self.indexer = SpanIndexer(
            self.engine, [self.test_dir / "projects"], interval_seconds=3600
        )

    def tearDown(self):
        import shutil

        try:
            self.indexer.stop()
        finally:
            pass
        self.engine.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _span(self, name, text):
        p = self.memdir / name
        p.write_text(
            "<!-- test span -->\n"
            '<!ELEMENT span EMPTY>\n<span id="span-0">\n' + text + "\n</span>\n",
            encoding="utf-8",
        )
        return p

    def test_tick_indexes_new_span_file(self):
        self._span("rtrre-aaa.dtd", "UNIQUE-SPAN-MARKER-ONE keeper memory infinite")
        stats = self.indexer.tick()
        self.assertEqual(stats["new"], 1)
        results = self.engine.search("UNIQUE-SPAN-MARKER-ONE")
        self.assertTrue(results)

    def test_tick_skips_unchanged_spans(self):
        self._span("rtrre-aaa.dtd", "UNIQUE-SPAN-MARKER-TWO keeper memory infinite")
        first = self.indexer.tick()
        self.assertEqual(first["new"], 1)
        second = self.indexer.tick()
        self.assertEqual(second["new"], 0)
        self.assertEqual(second["unchanged"], 1)

    def test_tick_skips_under_commit_pressure(self):
        self._span("rtrre-aaa.dtd", "UNIQUE-SPAN-MARKER-THREE keeper memory infinite")
        with patch.object(memory_engine, "_worker_refusal", return_value="wedged"):
            stats = self.indexer.tick()
        self.assertEqual(stats.get("status"), "error")
        self.assertNotIn(
            str(self.memdir / "rtrre-aaa.dtd"), self.engine.load_registry()
        )

    def test_thread_lifecycle(self):
        self.indexer.start()
        try:
            self.assertTrue(self.indexer.is_alive())
        finally:
            self.indexer.stop()
        self.assertFalse(self.indexer.is_alive())


if __name__ == "__main__":
    unittest.main()
