# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Tests for the per-family DTD suites wiring (TODO-36).

Covers: the 14 per-family corpus specs (all real families present,
paths exist, bounded at 40 files), the staging + query derivation path
for a single family, and the per-family scoreboard writer.
"""

from __future__ import annotations

import hashlib
import importlib.util
import random
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "bench_versus", ROOT / "eval" / "bench_versus.py"
)
assert SPEC and SPEC.loader
b = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = b
assert SPEC.loader
SPEC.loader.exec_module(b)

EXPECTED_FAMILIES = {
    "dtd-jats",
    "dtd-daisy",
    "dtd-docbook",
    "dtd-dtds",
    "dtd-mathml",
    "dtd-office",
    "dtd-dita-spec11",
    "dtd-dita12",
    "dtd-dita13",
    "dtd-xdita",
    "dtd-svg",
    "dtd-tei",
    "dtd-xhtml",
    "dtd-xhtml11",
}

SOURCES_AVAILABLE = all(c["src"].exists() for c in b.PER_FAMILY_CORPORA)
NEEDS_SOURCES = "needs operator-local DTD corpus; CI cannot stage families"


class TestPerFamilySpecs(unittest.TestCase):
    def test_all_fourteen_families_present(self):
        names = {c["name"] for c in b.PER_FAMILY_CORPORA}
        self.assertEqual(names, EXPECTED_FAMILIES)

    def test_specs_unique_and_bounded(self):
        names = [c["name"] for c in b.PER_FAMILY_CORPORA]
        self.assertEqual(len(names), len(set(names)))
        for spec in b.PER_FAMILY_CORPORA:
            self.assertLessEqual(spec["n"], 40)
            self.assertEqual(spec["title"], "dtd")
            self.assertEqual(spec["mode"], "step")
            self.assertTrue(spec["prefix_rel"])

    @unittest.skipUnless(SOURCES_AVAILABLE, NEEDS_SOURCES)
    def test_spec_sources_exist(self):
        for spec in b.PER_FAMILY_CORPORA:
            self.assertTrue(spec["src"].exists(), spec["name"])
            self.assertTrue(spec["src"].is_dir(), spec["name"])

    def test_default_run_excludes_per_family(self):
        default_names = {c["name"] for c in b.CORPORA}
        self.assertTrue(default_names.isdisjoint(EXPECTED_FAMILIES))


class TestPerFamilyDerivation(unittest.TestCase):
    def _stage_and_derive(self, name):
        with tempfile.TemporaryDirectory() as d:
            b.BENCH_ROOT = Path(d) / "roots"
            b.BENCH_ROOT.mkdir(parents=True)
            spec = next(c for c in b.PER_FAMILY_CORPORA if c["name"] == name)
            _base, proj, staged = b.stage_corpus(spec, spec["name"])
            crng = random.Random(
                b.SEED + int(hashlib.sha256(spec["name"].encode()).hexdigest()[:8], 16)
            )
            queries = b.derive_dtd_queries(proj, crng)
            return staged, queries

    @unittest.skipUnless(SOURCES_AVAILABLE, NEEDS_SOURCES)
    def test_daisy_derives_queries_no_cross_family(self):
        staged, queries = self._stage_and_derive("dtd-daisy")
        self.assertGreater(len(staged), 0)
        self.assertGreater(len(queries), 0)
        taxons = Counter(t for t, _, _ in queries)
        self.assertEqual(taxons.get("T10", 0), 0)

    @unittest.skipUnless(SOURCES_AVAILABLE, NEEDS_SOURCES)
    def test_tiny_family_derives(self):
        staged, queries = self._stage_and_derive("dtd-xdita")
        self.assertGreater(len(staged), 0)
        self.assertGreater(len(queries), 0)

    @unittest.skipUnless(SOURCES_AVAILABLE, NEEDS_SOURCES)
    def test_docbook_substructure_t10_is_cross_version(self):
        staged, queries = self._stage_and_derive("dtd-docbook")
        prefixes = {n.split("__")[0] for n in staged if "__" in n}
        self.assertGreater(len(prefixes), 1)
        self.assertGreater(Counter(t for t, _, _ in queries).get("T10", 0), 0)


class TestPerFamilyBoard(unittest.TestCase):
    def test_board_writes_only_dtd_family_rows(self):
        results = {
            "tool": "t",
            "seed": 1,
            "corpora": {
                "dtd-jats": {
                    "files": 40,
                    "queries": 72,
                    "systems": {
                        "rtr-full": {
                            "metrics": {
                                "OVERALL": {
                                    "n": 72,
                                    "recall@1": 0.5,
                                    "recall@3": 0.6,
                                    "mrr": 0.55,
                                }
                            }
                        }
                    },
                },
                "nt-studies": {
                    "files": 36,
                    "queries": 164,
                    "systems": {},
                },
            },
        }
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "board.md"
            b.write_per_family_board(out, results)
            text = out.read_text(encoding="utf-8")
            self.assertIn("dtd-jats", text)
            self.assertNotIn("nt-studies", text)
            self.assertIn("0.5000", text)

    def test_board_absent_without_per_family(self):
        results = {"tool": "t", "seed": 1, "corpora": {"nt-studies": {}}}
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "board.md"
            b.write_per_family_board(out, results)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
