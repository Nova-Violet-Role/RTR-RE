# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Vector reconciliation tests (TODO-15): the missing third leg.

repair_registry rebuilds registry FROM Chroma; janitor deletes chunks
for dead files. Neither sees a live file whose chunks are MISSING
(holes: registry says indexed, the model has nothing). reconcile_vectors
diffs registry-vs-Chroma per model, reports holes, and (heal=True)
re-queues holed files through the normal incremental path.
"""

import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.absolute()))

import memory_engine as mem
from memory_engine import MemoryEngine


class ReconcileTests(unittest.TestCase):
    def _isolated(self, td):
        root = Path(td)
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
        return root, saved

    def _restore(self, saved):
        (
            mem.PROJECT_ROOTS,
            mem.PROJECTS_DIR,
            mem.DB_DIR,
            mem.REGISTRY_FILE,
            mem.EXTRA_ROOTS_FILE,
            mem.LEXIKON_GLOBAL_FILE,
        ) = saved

    def _bge_slug(self, eng):
        for slug in eng.rtr_collections():
            if "bge" in slug:
                return slug
        self.fail("no bge collection")

    def test_report_names_planted_hole_without_changing_anything(self):
        with tempfile.TemporaryDirectory() as td:
            root, saved = self._isolated(td)
            try:
                d = root / "projects" / "rec" / "directives"
                d.mkdir(parents=True)
                (d / "a.md").write_text(
                    "# A\n\nRECONCILE-MARKER-ALPHA", encoding="utf-8"
                )
                (d / "b.md").write_text(
                    "# B\n\nRECONCILE-MARKER-BETA", encoding="utf-8"
                )
                eng = MemoryEngine()
                try:
                    eng.index_all()
                    slug = self._bge_slug(eng)
                    col = eng.rtr_collections()[slug]
                    # PLANT THE HOLE: murder b's bge chunks directly.
                    victim = str(d / "b.md")
                    dead = col.get(where={"source": victim}, limit=5000)["ids"]
                    self.assertGreater(len(dead), 0)
                    col.delete(ids=dead)
                    report = eng.reconcile_vectors()
                    self.assertEqual(report["status"], "success")
                    self.assertIn(victim, report["missing"][slug])
                    # report mode changes nothing: still missing after.
                    again = col.get(where={"source": victim}, limit=5000)["ids"]
                    self.assertEqual(again, [])
                finally:
                    eng.close()
            finally:
                self._restore(saved)

    def test_heal_closes_planted_hole(self):
        with tempfile.TemporaryDirectory() as td:
            root, saved = self._isolated(td)
            try:
                d = root / "projects" / "rec" / "directives"
                d.mkdir(parents=True)
                (d / "a.md").write_text(
                    "# A\n\nRECONCILE-MARKER-ALPHA", encoding="utf-8"
                )
                (d / "b.md").write_text(
                    "# B\n\nRECONCILE-MARKER-BETA", encoding="utf-8"
                )
                eng = MemoryEngine()
                try:
                    eng.index_all()
                    slug = self._bge_slug(eng)
                    col = eng.rtr_collections()[slug]
                    victim = str(d / "b.md")
                    dead = col.get(where={"source": victim}, limit=5000)["ids"]
                    col.delete(ids=dead)
                    out = eng.reconcile_vectors(heal=True)
                    self.assertIn(victim, out["healed"])
                    back = col.get(where={"source": victim}, limit=5000)["ids"]
                    self.assertGreater(len(back), 0)
                    # and the file is retrievable again
                    hits = eng.search("RECONCILE-MARKER-BETA", k=3)
                    self.assertTrue(
                        any("b.md" in h["metadata"].get("source", "") for h in hits)
                    )
                finally:
                    eng.close()
            finally:
                self._restore(saved)


class TestAbortSafeUpsert(unittest.TestCase):
    def _isolated(self, td):
        root = Path(td)
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
            yield root
        finally:
            (
                mem.PROJECT_ROOTS,
                mem.PROJECTS_DIR,
                mem.DB_DIR,
                mem.REGISTRY_FILE,
                mem.EXTRA_ROOTS_FILE,
                mem.LEXIKON_GLOBAL_FILE,
            ) = saved

    def test_failed_reembed_keeps_old_chunks(self):
        # Purge-then-add destroys good vectors when the re-embed
        # fails; add-then-purge must keep serving the old chunks
        # (and keep the old hash so the next run retries).
        import contextlib
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            with contextlib.contextmanager(self._isolated)(td) as root:
                d = root / "projects" / "ab" / "directives"
                d.mkdir(parents=True)
                f = d / "a.md"
                f.write_text("# A\n\nALPHA content here", encoding="utf-8")
                eng = MemoryEngine()
                try:
                    eng.index_all()
                    old_hash = eng.load_registry()[str(f)]
                    cols = eng.rtr_collections()
                    slug = next(s for s in cols if "bge" in s)
                    col = cols[slug]
                    before = col.get(where={"source": str(f)}, limit=5000)["ids"]
                    self.assertGreater(len(before), 0)
                    f.write_text(
                        "# A\n\nALPHA content here plus POISON words",
                        encoding="utf-8",
                    )

                    def poison(texts, orig):
                        if any("POISON" in t for t in texts):
                            raise RuntimeError("embed boom")
                        return orig(texts)

                    with contextlib.ExitStack() as stack:
                        for m in eng.models.values():
                            o = m.embed
                            stack.enter_context(
                                patch.object(
                                    m,
                                    "embed",
                                    side_effect=lambda t, o=o: poison(t, o),
                                )
                            )
                        stats = eng.index_all()
                    self.assertEqual(stats["failed"], 2)
                    after = col.get(where={"source": str(f)}, limit=5000)["ids"]
                    self.assertEqual(sorted(after), sorted(before))
                    self.assertEqual(eng.load_registry()[str(f)], old_hash)
                finally:
                    eng.close()

    def test_shrink_cleans_stale_chunks(self):
        # Add-then-purge must still remove stale ids on success:
        # no ghost chunks from the longer version may linger.
        import contextlib

        with tempfile.TemporaryDirectory() as td:
            with contextlib.contextmanager(self._isolated)(td) as root:
                d = root / "projects" / "ab" / "directives"
                d.mkdir(parents=True)
                f = d / "long.md"
                f.write_text(
                    "".join(
                        f"# Section {i}\n\nBody text {i} filler.\n\n" for i in range(20)
                    ),
                    encoding="utf-8",
                )
                eng = MemoryEngine()
                try:
                    eng.index_all()
                    cols = eng.rtr_collections()
                    slug = next(s for s in cols if "bge" in s)
                    col = eng.rtr_collections()[slug]
                    before = col.get(where={"source": str(f)}, limit=5000)["ids"]
                    self.assertGreater(len(before), 1)
                    f.write_text("# L\n\none short line", encoding="utf-8")
                    eng.index_all()
                    got = col.get(
                        where={"source": str(f)},
                        limit=5000,
                        include=["metadatas"],
                    )
                    self.assertLess(len(got["ids"]), len(before))
                    cur = eng.load_registry()[str(f)]
                    for m in got["metadatas"]:
                        self.assertEqual(m["content_hash"], cur)
                finally:
                    eng.close()

    def test_heal_closes_dtd_hole(self):
        # Spans are .dtd whole-file chunks: same hole mechanics,
        # same heal. Pinned separately so markdown coverage never
        # stands in for it.
        import tempfile
        from pathlib import Path

        from memory_engine import MemoryEngine

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
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
                d = root / "projects" / "rec" / "directives"
                d.mkdir(parents=True)
                (d / "c.dtd").write_text(
                    "<!ELEMENT note (to,from,body)>\n"
                    "<!ATTLIST note id ID #REQUIRED>\n"
                    "<!ELEMENT to (#PCDATA)>\n",
                    encoding="utf-8",
                )
                eng = MemoryEngine()
                try:
                    eng.index_all()
                    slug = next(
                        s for s in eng.rtr_collections() if s == "baai_bge_base_en_v1_5"
                    )
                    col = eng.rtr_collections()[slug]
                    victim = str(d / "c.dtd")
                    dead = col.get(where={"source": victim}, limit=5000)["ids"]
                    self.assertGreater(len(dead), 0)
                    col.delete(ids=dead)
                    report = eng.reconcile_vectors()
                    self.assertIn(victim, report["missing"][slug])
                    out = eng.reconcile_vectors(heal=True)
                    self.assertIn(victim, out["healed"])
                    back = col.get(where={"source": victim}, limit=5000)["ids"]
                    self.assertGreater(len(back), 0)
                finally:
                    eng.close()
            finally:
                (
                    mem.PROJECT_ROOTS,
                    mem.PROJECTS_DIR,
                    mem.DB_DIR,
                    mem.REGISTRY_FILE,
                    mem.EXTRA_ROOTS_FILE,
                    mem.LEXIKON_GLOBAL_FILE,
                ) = saved


if __name__ == "__main__":
    unittest.main()
