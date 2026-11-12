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

    def test_abort_mid_wave_resumes_without_holes(self):
        # Cooperative kill mid-wave (SystemExit at the 2nd stale
        # prune): add-then-purge must leave every file with vectors
        # on every model (old or new, never zero), the registry
        # uncommitted, and a plain re-run must complete cleanly.
        import contextlib
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            with contextlib.contextmanager(self._isolated)(td) as root:
                d = root / "projects" / "ab" / "directives"
                d.mkdir(parents=True)
                files = []
                for i in range(4):
                    f = d / f"f{i}.md"
                    f.write_text(f"# F{i}\n\nABORT-MARKER-{i} v1", encoding="utf-8")
                    files.append(str(f))
                eng = MemoryEngine()
                try:
                    eng.index_all()
                    reg_before = dict(eng.load_registry())
                    for i, f in enumerate(files):
                        Path(f).write_text(
                            f"# F{i}\n\nABORT-MARKER-{i} v2", encoding="utf-8"
                        )
                    calls = []
                    orig_prune = MemoryEngine._prune_stale_ids

                    def killer(col, info, new_ids, old_ids):
                        calls.append(info["path"])
                        if len(calls) == 2:
                            raise SystemExit("simulated kill mid-wave")
                        return orig_prune(col, info, new_ids, old_ids)

                    with patch.object(
                        MemoryEngine, "_prune_stale_ids", side_effect=killer
                    ):
                        with self.assertRaises(SystemExit):
                            eng.index_all()
                    self.assertEqual(len(calls), 2)
                    cols = eng.rtr_collections()
                    for slug, col in cols.items():
                        if (
                            "opencode_memory_" in slug
                            and slug.replace("opencode_memory_", "") in cols
                        ):
                            continue
                        for f in files:
                            n = len(col.get(where={"source": f}, limit=5000)["ids"])
                            self.assertGreater(n, 0, f"{slug} holed {f} after abort")
                    self.assertEqual(eng.load_registry(), reg_before)
                    # resume: a plain re-run completes and converges
                    eng.index_all()
                    report = eng.reconcile_vectors()
                    total_missing = sum(len(v) for v in report["missing"].values())
                    self.assertEqual(total_missing, 0)
                    hits = eng.search("ABORT-MARKER-2 v2", k=3)
                    self.assertTrue(
                        any("f2.md" in h["metadata"].get("source", "") for h in hits)
                    )
                finally:
                    eng.close()

    def test_heal_batches_bounded_with_progress(self):
        # 60 holes heal across 3 batches of 25 (not one giant
        # wave): bounded materialization per batch is what keeps
        # RSS flat on thousand-file heals (19GB lesson).
        import contextlib
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            with contextlib.contextmanager(self._isolated)(td) as root:
                d = root / "projects" / "rec" / "directives"
                d.mkdir(parents=True)
                for i in range(60):
                    (d / f"h{i:02d}.md").write_text(
                        f"# H{i}\n\nBATCH-MARKER-{i}", encoding="utf-8"
                    )
                eng = MemoryEngine()
                try:
                    eng.index_all()
                    slug = next(
                        s for s in eng.rtr_collections() if s == "baai_bge_base_en_v1_5"
                    )
                    col = eng.rtr_collections()[slug]
                    for i in range(60):
                        victim = str(d / f"h{i:02d}.md")
                        dead = col.get(where={"source": victim}, limit=5000)["ids"]
                        self.assertGreater(len(dead), 0)
                        col.delete(ids=dead)
                    calls = []
                    orig_index = eng.index_all

                    def counting(*a, **k):
                        calls.append(1)
                        return orig_index(*a, **k)

                    with patch.object(eng, "index_all", side_effect=counting):
                        out = eng.reconcile_vectors(heal=True)
                    self.assertEqual(len(out["healed"]), 60)
                    self.assertEqual(out["batches"], 3)
                    self.assertEqual(len(calls), 3)
                    self.assertEqual(out["unhealed"], [])
                    report = eng.reconcile_vectors()
                    total = sum(len(v) for v in report["missing"].values())
                    self.assertEqual(total, 0)
                finally:
                    eng.close()

    def test_heal_reports_progress_per_batch(self):
        # Long heals must be watchable: on_batch fires per batch
        # with (done, total, rss_mb) so operators see progress live
        # instead of staring at a silent call.
        import contextlib

        with tempfile.TemporaryDirectory() as td:
            with contextlib.contextmanager(self._isolated)(td) as root:
                d = root / "projects" / "rec" / "directives"
                d.mkdir(parents=True)
                for i in range(30):
                    (d / f"p{i:02d}.md").write_text(
                        f"# P{i}\n\nPROGRESS-MARKER-{i}", encoding="utf-8"
                    )
                eng = MemoryEngine()
                try:
                    eng.index_all()
                    slug = next(
                        s for s in eng.rtr_collections() if s == "baai_bge_base_en_v1_5"
                    )
                    col = eng.rtr_collections()[slug]
                    for i in range(30):
                        victim = str(d / f"p{i:02d}.md")
                        dead = col.get(where={"source": victim}, limit=5000)["ids"]
                        col.delete(ids=dead)
                    seen = []
                    out = eng.reconcile_vectors(
                        heal=True,
                        on_batch=lambda done, total, rss: seen.append(
                            (done, total, rss)
                        ),
                    )
                    self.assertEqual(len(out["healed"]), 30)
                    self.assertEqual([s[0] for s in seen], [25, 30])
                    self.assertTrue(all(s[1] == 30 for s in seen))
                    self.assertTrue(all(s[2] > 0 for s in seen))
                finally:
                    eng.close()

    def test_index_trace_logs_per_file_timings(self):
        # Long heals must leave a trail even when killed: with
        # RTR_RE_INDEX_TRACE=1, every file embed+upsert logs one
        # timestamped line (model, chunks, ms) so a stall names its
        # file AND its minute. Both chunker families (.md + .dtd).
        import contextlib
        import io
        import os
        import re

        with tempfile.TemporaryDirectory() as td:
            with contextlib.contextmanager(self._isolated)(td) as root:
                d = root / "projects" / "rec" / "directives"
                d.mkdir(parents=True)
                (d / "t.md").write_text("# T\n\nTRACE-MARKER", encoding="utf-8")
                (d / "s.dtd").write_text(
                    "<!ELEMENT span (text)>\n<!ATTLIST span id ID #REQUIRED>\n",
                    encoding="utf-8",
                )
                eng = MemoryEngine()
                try:
                    old = os.environ.get("RTR_RE_INDEX_TRACE")
                    os.environ["RTR_RE_INDEX_TRACE"] = "1"
                    try:
                        import contextlib as cl

                        buf = io.StringIO()
                        with cl.redirect_stderr(buf):
                            eng.index_all()
                    finally:
                        if old is None:
                            del os.environ["RTR_RE_INDEX_TRACE"]
                        else:
                            os.environ["RTR_RE_INDEX_TRACE"] = old
                    out = buf.getvalue()
                    self.assertIn("trace index", out)
                    self.assertIn("t.md", out)
                    self.assertIn("s.dtd", out)
                    self.assertIn("ms", out)
                    self.assertTrue(
                        re.search(r"\d{2}:\d{2}:\d{2}", out),
                        "trace lines carry HH:MM:SS timestamps",
                    )
                finally:
                    eng.close()

    def test_heal_orders_batches_smallest_first(self):
        # Monsters (multi-MB spans) take minutes per file per model;
        # healing smallest-first streams early progress (and early
        # verification) instead of opening on an hour-long file.
        # Both chunker families (.md + .dtd): the database is spans,
        # but directives docs are markdown, and size order must hold
        # across both.
        import contextlib

        with tempfile.TemporaryDirectory() as td:
            with contextlib.contextmanager(self._isolated)(td) as root:
                d = root / "projects" / "rec" / "directives"
                d.mkdir(parents=True)
                (d / "a-huge.md").write_text(
                    "# Z\n\n" + "BIGPAD " * 2000, encoding="utf-8"
                )
                (d / "z-tiny.md").write_text("# A\n\ntiny", encoding="utf-8")
                (d / "m-mid.md").write_text(
                    "# M\n\n" + "MIDPAD " * 200, encoding="utf-8"
                )
                (d / "a-huge.dtd").write_text(
                    "<!ELEMENT big (x)>\n<!-- " + "P" * 22000 + " -->\n",
                    encoding="utf-8",
                )
                (d / "z-tiny.dtd").write_text("<!ELEMENT t (x)>\n", encoding="utf-8")
                (d / "m-mid.dtd").write_text(
                    "<!ELEMENT m (x)>\n<!-- " + "Q" * 2200 + " -->\n",
                    encoding="utf-8",
                )
                eng = MemoryEngine()
                try:
                    eng.index_all()
                    slug = next(
                        s for s in eng.rtr_collections() if s == "baai_bge_base_en_v1_5"
                    )
                    col = eng.rtr_collections()[slug]
                    for name in (
                        "a-huge.md",
                        "z-tiny.md",
                        "m-mid.md",
                        "a-huge.dtd",
                        "z-tiny.dtd",
                        "m-mid.dtd",
                    ):
                        victim = str(d / name)
                        dead = col.get(where={"source": victim}, limit=5000)["ids"]
                        self.assertGreater(len(dead), 0)
                        col.delete(ids=dead)
                    out = eng.reconcile_vectors(heal=True)
                    names = [Path(p).name for p in out["healed"]]
                    self.assertEqual(
                        names,
                        [
                            "z-tiny.md",
                            "z-tiny.dtd",
                            "m-mid.md",
                            "m-mid.dtd",
                            "a-huge.md",
                            "a-huge.dtd",
                        ],
                    )
                finally:
                    eng.close()

    def test_heal_heartbeat_dumps_stacks(self):
        # Long heals must X-ray themselves: with a short heartbeat,
        # stack dumps land on stderr during the run (post-kill
        # forensics included), naming the live frames.
        import contextlib
        import io
        import os

        with tempfile.TemporaryDirectory() as td:
            with contextlib.contextmanager(self._isolated)(td) as root:
                d = root / "projects" / "rec" / "directives"
                d.mkdir(parents=True)
                for i in range(20):
                    (d / f"h{i:02d}.md").write_text(
                        f"# H{i}\n\nHEARTBEAT-MARKER-{i}", encoding="utf-8"
                    )
                    (d / f"s{i:02d}.dtd").write_text(
                        f"<!ELEMENT beat{i} (pulse)>\n", encoding="utf-8"
                    )
                eng = MemoryEngine()
                try:
                    eng.index_all()
                    slug = next(
                        s for s in eng.rtr_collections() if s == "baai_bge_base_en_v1_5"
                    )
                    col = eng.rtr_collections()[slug]
                    victims = [str(p) for p in sorted(d.iterdir())]
                    for victim in victims:
                        dead = col.get(where={"source": victim}, limit=5000)["ids"]
                        self.assertGreater(len(dead), 0)
                        col.delete(ids=dead)
                    old = os.environ.get("RTR_RE_HEAL_HEARTBEAT_SEC")
                    os.environ["RTR_RE_HEAL_HEARTBEAT_SEC"] = "1"
                    try:
                        import contextlib as cl

                        err_path = root / "hb-stderr.log"
                        with open(err_path, "w", encoding="utf-8") as err:
                            with cl.redirect_stderr(err):
                                out = eng.reconcile_vectors(heal=True)
                        dumped = err_path.read_text(encoding="utf-8")
                    finally:
                        if old is None:
                            del os.environ["RTR_RE_HEAL_HEARTBEAT_SEC"]
                        else:
                            os.environ["RTR_RE_HEAL_HEARTBEAT_SEC"] = old
                    self.assertEqual(len(out["healed"]), 40)
                    self.assertIn("Thread", dumped)
                    self.assertIn("pulses, not failures", dumped)
                finally:
                    eng.close()

    def test_embed_splits_giant_texts_into_budgeted_calls(self):
        # One 150KB text sharing an embed call with 2455 friends pads
        # the whole batch to its length and kills ONNX Attention
        # (measured live). Texts split into sub-batches bounded by
        # total chars: the giant rides solo, small fry fuse as before.
        import contextlib
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            with contextlib.contextmanager(self._isolated)(td) as root:
                d = root / "projects" / "rec" / "directives"
                d.mkdir(parents=True)
                sections = "".join(
                    f"# S{i}\n\n" + "GIANT " * 2500 + "\n" for i in range(10)
                )
                (d / "g.md").write_text(sections, encoding="utf-8")
                (d / "s.md").write_text("# S\n\ntiny", encoding="utf-8")
                eng = MemoryEngine()
                try:
                    buckets = {}
                    with contextlib.ExitStack() as stack:
                        for slug, m in eng.models.items():
                            o = m.embed
                            b = []
                            buckets[slug] = b
                            stack.enter_context(
                                patch.object(
                                    m,
                                    "embed",
                                    side_effect=lambda t, o=o, b=b: (
                                        b.append(len(t)),
                                        o(t),
                                    )[1],
                                )
                            )
                        eng.index_all()
                    for slug, b in buckets.items():
                        self.assertGreater(len(b), 2, f"{slug} never split its calls")
                        self.assertEqual(sum(b), 11)
                    hits = eng.search("GIANT", k=3)
                    self.assertTrue(
                        any("g.md" in h["metadata"].get("source", "") for h in hits)
                    )
                    hits = eng.search("tiny", k=3)
                    self.assertTrue(
                        any("s.md" in h["metadata"].get("source", "") for h in hits)
                    )
                finally:
                    eng.close()


if __name__ == "__main__":
    unittest.main()
