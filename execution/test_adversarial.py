# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Adversarial subsystem battery (TODO-7 round 2): each probe attacks one
subsystem and either proves it holds or names the break with severity."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.absolute()))
sys.path.insert(0, str(Path(__file__).parent.parent / "eval"))

import memory_engine as mem
from engine_beneath_cases import _engine_tempdir  # noqa: E402
from memory_engine import MemoryEngine


@contextmanager
def isolated_roots(td):
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


class WorkerRaggedTests(unittest.TestCase):
    def test_empty_submit_is_ready_not_crash(self):
        from symbiose_worker import SymbioseWorker

        w = SymbioseWorker(lambda spans: "ok")
        try:
            t = w.submit([])
            out = w.wait(t["id"], timeout=5)
            self.assertEqual(out["status"], "ready")
        finally:
            w.close()

    def test_malformed_submit_json_refuses(self):
        from symbiose_worker import SymbioseWorker, submit_json

        w = SymbioseWorker(lambda spans: "ok")
        try:
            # The contract is refusal-by-ValueError; both surfaces
            # (MCP Refused panel, CLI refusal) catch it by design.
            with self.assertRaises(ValueError):
                submit_json(w, "not json{{{")
            with self.assertRaises(ValueError):
                submit_json(w, '{"role": "user"}')
        finally:
            w.close()

    def test_corrupt_keeper_status_yields_zero_live_tokens(self):
        from symbiose_worker import _read_keeper_live_tokens

        with tempfile.TemporaryDirectory() as td:
            oc = Path(td) / ".opencode"
            oc.mkdir(parents=True)
            (oc / "rtr-re-cumulative.json").write_text("{}", encoding="utf-8")
            (oc / "rtr-re-keeper-status.json").write_text(
                "{corrupt!!!", encoding="utf-8"
            )
            self.assertEqual(_read_keeper_live_tokens(oc / "rtr-re-cumulative.json"), 0)

    def test_drain_missing_memory_dir_is_empty_not_crash(self):
        from symbiose_worker import SymbioseWorker, drain_submit_sidecars

        w = SymbioseWorker(lambda spans: "ok")
        try:
            with tempfile.TemporaryDirectory() as td:
                report = drain_submit_sidecars(w, Path(td) / "no-such-dir", limit=5)
                self.assertEqual(report.get("consumed", []), [])
        finally:
            w.close()


class EngineAdversarialTests(unittest.TestCase):
    def test_malformed_huge_and_weird_corpus(self):
        with _engine_tempdir(prefix="rtrre-adv-") as td:
            with isolated_roots(td) as root:
                proj = root / "projects" / "adv"
                d = proj / "directives"
                d.mkdir(parents=True)
                (d / "ok.md").write_text(
                    "# Ok\n\nUNIQUE-ADVERSARIAL-MARKER-42 and some prose.",
                    encoding="utf-8",
                )
                (d / "broken.dtd").write_text(
                    "<!ELEMENT foo (bar\n<!ATTLIST broken\n[[[unclosed {{{",
                    encoding="utf-8",
                )
                (d / "binary.dtd").write_bytes(b"\x00\xff\xfe\x00binary\x00junk")
                (d / "huge.md").write_text(
                    "# Huge\n\n" + ("lorem ipsum dolor sit amet " * 200000),
                    encoding="utf-8",
                )
                eng = MemoryEngine()
                try:
                    stats = eng.index_all()
                    # binary garbage is counted honestly, never crashes,
                    # never blocks the healthy files, and never lands in
                    # the registry (no silent index holes)
                    self.assertEqual(stats["failed"], 1)
                    self.assertEqual(stats["new"], 4)
                    reg = eng.load_registry()
                    self.assertNotIn(str(d / "binary.dtd"), reg)
                    self.assertIn(str(d / "ok.md"), reg)
                    hits = eng.search("UNIQUE-ADVERSARIAL-MARKER-42", k=3)
                    self.assertTrue(
                        any("ok.md" in h["metadata"].get("source", "") for h in hits)
                    )
                    # malformed + huge must not break search either
                    self.assertIsInstance(eng.search("", k=3), list)
                    self.assertIsInstance(eng.search("e", k=0), list)
                    self.assertIsInstance(eng.search("e", k=-1), list)
                    self.assertIsInstance(eng.search("e", k=10**6), list)
                    self.assertIsInstance(eng.search("héllo wörld → ⛄", k=3), list)
                finally:
                    eng.close()

    def test_second_engine_is_read_only(self):
        with _engine_tempdir(prefix="rtrre-adv-ro-") as td:
            with isolated_roots(td):
                eng1 = MemoryEngine()
                try:
                    eng2 = MemoryEngine()
                    try:
                        self.assertTrue(eng2.read_only)
                        self.assertIsInstance(eng2.discover_wikis(), list)
                    finally:
                        eng2.close()
                finally:
                    eng1.close()


class MigrationLieTests(unittest.TestCase):
    def test_version_tuple_edges(self):
        import memory_mcp_server as mcp

        self.assertTrue(hasattr(mcp, "_version_tuple"))
        # mixed numeric/string segments compare segment-wise
        self.assertGreater(mcp._version_tuple("1.2.0"), mcp._version_tuple("1.1.0"))
        self.assertEqual(mcp._version_tuple("1.2.0"), mcp._version_tuple("1.2.0"))
        # garbage, empty, and partial versions must not crash
        for weird in ("abc", "", "1", "1.2.3.4", "1.x", None):
            try:
                got = mcp._version_tuple(weird)  # type: ignore[arg-type]
            except Exception as e:  # noqa: BLE001
                self.fail(f"_version_tuple({weird!r}) raised {e!r}")
            self.assertIsInstance(got, tuple)

    def test_corrupt_marker_is_error_not_crash(self):
        import memory_mcp_server as mcp

        class FakeEngine:
            def __init__(self, collections):
                self.collections = collections

            def repair_registry(self):
                return {"repaired": 0, "total": 0}

            def janitor(self, dry_run=False):
                return {"freed": 0, "pruned_roots": []}

        class FakeCol:
            def count(self):
                return 5

        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "memory"
            home.mkdir(parents=True)
            (home / "rtr-re-schema.json").write_text("{corrupt", encoding="utf-8")
            with patch.object(mcp, "engine", FakeEngine({"c": FakeCol()})):
                out = mcp.maybe_migrate_db(str(home), "1.2.0")
            self.assertIn(out["action"], ("error", "amend", "stamp", "skip"))


class PerfMeasureTests(unittest.TestCase):
    def test_expansion_fanout_measured(self):
        with tempfile.TemporaryDirectory() as td:
            with isolated_roots(td) as root:
                eng = MemoryEngine()
                try:
                    for i in range(5):
                        eng.add_lexikon_term(
                            "_global",
                            f"perfterm{i}",
                            definition="d",
                            aliases=[f"pa{i}a", f"pa{i}b", f"pa{i}c"],
                        )
                    lex, _ = eng.build_expansions("perfterm0 pa0a", "_global")
                    print(f"\nfanout: {len(lex)} expansions")
                    self.assertLess(len(lex), 50)
                finally:
                    eng.close()

    def test_resolve_write_amplification_measured(self):
        with tempfile.TemporaryDirectory() as td:
            with isolated_roots(td) as root:
                proj = root / "projects" / "w"
                (proj / "state").mkdir(parents=True)
                eng = MemoryEngine()
                try:
                    writes = []
                    orig = eng._save_concept_registry
                    eng._save_concept_registry = lambda project, registry: (
                        writes.append(1) or orig(project, registry)
                    )
                    eng._resolve_concept(str(proj), "alpha one")
                    new_writes = len(writes)
                    eng._resolve_concept(str(proj), "alpha one")
                    exact_writes = len(writes) - new_writes
                    print(
                        f"\nresolve writes: new={new_writes} "
                        f"exact-repeat={exact_writes}"
                    )
                    self.assertEqual(new_writes, 1)
                    self.assertEqual(exact_writes, 0)
                finally:
                    eng.close()


class TickBurstTests(unittest.TestCase):
    def test_tick_survives_corrupt_and_burst(self):
        from span_indexer import SpanIndexer

        with tempfile.TemporaryDirectory() as td:
            with isolated_roots(td) as root:
                proj = root / "projects" / "tick"
                mem_dir = proj / ".opencode" / "memory"
                mem_dir.mkdir(parents=True)
                (mem_dir / "rtrre-broken.dtd").write_bytes(b"\x00\xff corrupt \xfe")
                for i in range(20):
                    (mem_dir / f"rtrre-tick{i:03d}.dtd").write_text(
                        "<!-- span -->\n<!ELEMENT span EMPTY>\n"
                        f"TICKMARKER-{i:03d} verbal content here.",
                        encoding="utf-8",
                    )
                eng = MemoryEngine()
                try:
                    idx = SpanIndexer(eng, [str(proj)])
                    out = idx.tick()
                    self.assertIsInstance(out, dict)
                    hits = eng.search("TICKMARKER-007", k=3)
                    self.assertTrue(
                        any(
                            "rtrre-tick007" in h["metadata"].get("source", "")
                            for h in hits
                        )
                    )
                finally:
                    eng.close()


if __name__ == "__main__":
    unittest.main()
