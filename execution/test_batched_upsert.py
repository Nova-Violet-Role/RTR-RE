# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Batched upsert: one embed call per model, identical results."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.absolute()))

import memory_engine
from memory_engine import MemoryEngine


class TestBatchedUpsert(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        memory_engine.PROJECT_ROOTS = [self.test_dir / "projects"]
        memory_engine.PROJECTS_DIR = self.test_dir / "projects"
        memory_engine.DB_DIR = self.test_dir / "db"
        memory_engine.REGISTRY_FILE = self.test_dir / "registry.json"
        memory_engine.EXTRA_ROOTS_FILE = self.test_dir / "extra.json"
        memory_engine.LEXIKON_GLOBAL_FILE = self.test_dir / "lex.json"
        self.engine = MemoryEngine()

    def tearDown(self):
        import shutil

        self.engine.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_one_embed_call_per_model(self):
        d = self.test_dir / "projects" / "batchproj" / "directives"
        d.mkdir(parents=True)
        for i in range(5):
            (d / f"doc{i}.md").write_text(
                f"# Doc {i}\n\nBatch marker BATCH{i:02d} " + ("text " * 20),
                encoding="utf-8",
            )
        calls = []
        real_models = self.engine.models
        for slug, model in real_models.items():
            orig = model.embed

            def counting(texts, _o=orig, _s=slug):
                calls.append(_s)
                return _o(texts)

            model.embed = counting
        try:
            stats = self.engine.index_all()
        finally:
            pass
        self.assertEqual(stats["failed"], 0)
        # One call per model, not one per file per model.
        for slug in real_models:
            self.assertEqual(calls.count(slug), 1, slug)
        hits = self.engine.search("BATCH03", k=3)
        self.assertTrue(hits)


if __name__ == "__main__":
    unittest.main()
