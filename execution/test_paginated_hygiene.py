# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Janitor/repair pagination: big collections scan in pages, deduped by name."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.absolute()))

import memory_engine
from memory_engine import MemoryEngine


class FakeCol:
    def __init__(self, name, metas):
        self.name = name
        self._metas = list(metas)
        self.calls = []
        self.deleted = []

    def count(self):
        return len(self._metas)

    def get(self, limit=None, offset=0, include=None):
        self.calls.append((limit, offset))
        if limit is not None and limit > 1000:
            raise RuntimeError("too many SQL variables")
        chunk = self._metas[offset : offset + (limit or 0)]
        return {
            "ids": [f"id-{offset + i}" for i in range(len(chunk))],
            "metadatas": chunk,
        }

    def delete(self, ids):
        self.deleted.extend(ids)


class TestPaginatedHygiene(unittest.TestCase):
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

    def test_janitor_pages_big_collection(self):
        live = self.test_dir / "live.md"
        live.write_text("# Live\n", encoding="utf-8")
        metas = [{"source": str(live)}] * 600 + [
            {"source": str(self.test_dir / "ghost.md")}
        ] * 600
        col = FakeCol("opencode_memory_test", metas)
        with patch.object(
            MemoryEngine, "rtr_collections", return_value={"a": col, "b": col}
        ):
            report = self.engine.janitor(dry_run=True)
        self.assertEqual(report["freed"], 600)
        self.assertTrue(all(lim <= 1000 for lim, _ in col.calls))
        self.assertGreater(len(col.calls), 1)
        # Same collection object under two keys scans once.
        self.assertEqual(len(report["collections"]), 1)

    def test_repair_pages_big_collection(self):
        live = self.test_dir / "keep.md"
        live.write_text("# Keep\n", encoding="utf-8")
        metas = [{"source": str(live)}] * 1200
        col = FakeCol("opencode_memory_test", metas)
        with patch.object(
            MemoryEngine, "rtr_collections", return_value={"a": col, "b": col}
        ):
            res = self.engine.repair_registry()
        self.assertEqual(res["status"], "success")
        self.assertIn(str(live), self.engine.load_registry())
        self.assertTrue(all(lim <= 1000 for lim, _ in col.calls))

    def test_repair_snapshots_pre_image_backup(self):
        import json

        live = self.test_dir / "pre.md"
        live.write_text("# Pre\n", encoding="utf-8")
        self.engine.save_registry({"old-entry": "hash"})
        metas = [{"source": str(live)}]
        col = FakeCol("opencode_memory_test", metas)
        with patch.object(MemoryEngine, "rtr_collections", return_value={"a": col}):
            res = self.engine.repair_registry()
        self.assertEqual(res["repaired"], 1)
        bak = Path(str(memory_engine.REGISTRY_FILE) + ".bak")
        self.assertTrue(bak.exists())
        self.assertEqual(
            json.loads(bak.read_text(encoding="utf-8")), {"old-entry": "hash"}
        )


if __name__ == "__main__":
    unittest.main()
