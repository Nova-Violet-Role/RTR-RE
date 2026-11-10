# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""bench_versus unit tests (TODO-25, J1/J3/J4/J8).

J1: metrics([]) must return a zero OVERALL, not raise ZeroDivisionError
(a missing corpus stages zero files, derives zero queries, and must
fail the gate as a regression — never crash the bench).
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "bench_versus", ROOT / "eval" / "bench_versus.py"
)
assert SPEC and SPEC.loader
bv = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bv
assert SPEC.loader
SPEC.loader.exec_module(bv)


class TestVersusMetrics(unittest.TestCase):
    def test_empty_rows_yield_zero_overall(self):
        out = bv.metrics([])
        self.assertEqual(out["OVERALL"]["n"], 0)
        self.assertEqual(out["OVERALL"]["recall@1"], 0.0)
        self.assertEqual(out["OVERALL"]["recall@3"], 0.0)
        self.assertEqual(out["OVERALL"]["mrr"], 0.0)
        self.assertEqual(out["OVERALL"]["p50_ms"], 0)

    def test_t10_expected_set_accepts_either_owner(self):
        # J4: a df==2 cross-family term lives in BOTH files; the old code
        # expected cross[t][0] only, so returning the other valid owner
        # scored a miss against an arbitrary pick.
        rows = [
            {
                "taxon": "T10",
                "query": "t",
                "expected": ["a.dtd", "b.dtd"],
                "got": ["b.dtd", "x"],
                "ms": 1.0,
                "error": "",
            },
            {
                "taxon": "T1",
                "query": "q",
                "expected": "a.md",
                "got": ["a.md"],
                "ms": 1.0,
                "error": "",
            },
        ]
        out = bv.metrics(rows)
        self.assertEqual(out["T10"]["recall@1"], 1.0)
        self.assertEqual(out["T10"]["recall@3"], 1.0)
        self.assertEqual(out["T10"]["mrr"], 1.0)
        self.assertEqual(out["T1"]["recall@1"], 1.0)

    def test_overall_macro_means_taxon_rates(self):
        # J8: OVERALL is micro (pooled rows); OVERALL_MACRO must mean the
        # per-taxon rates so big easy taxons cannot dominate the verdict.
        rows = [
            {
                "taxon": "T1",
                "query": "q",
                "expected": "a",
                "got": ["a"],
                "ms": 1.0,
                "error": "",
            },
            {
                "taxon": "T1",
                "query": "q",
                "expected": "a",
                "got": ["a"],
                "ms": 1.0,
                "error": "",
            },
            {
                "taxon": "T1",
                "query": "q",
                "expected": "a",
                "got": ["zzz"],
                "ms": 1.0,
                "error": "",
            },
            {
                "taxon": "T6",
                "query": "q",
                "expected": "b",
                "got": ["zzz"],
                "ms": 1.0,
                "error": "",
            },
        ]
        out = bv.metrics(rows)
        # Micro: 2/4. Macro: mean(2/3, 0/1).
        self.assertEqual(out["OVERALL"]["recall@1"], 0.5)
        self.assertAlmostEqual(out["OVERALL_MACRO"]["recall@1"], 2 / 3 / 2, places=4)

    def test_overall_carries_bootstrap_ci(self):
        # 25-power: every OVERALL rate carries a seeded 95% bootstrap CI
        # so claims have error bars, not just points.
        rows = [
            {
                "taxon": "T1",
                "query": "q",
                "expected": "a",
                "got": ["a"] if i % 2 == 0 else ["zzz"],
                "ms": 1.0,
                "error": "",
            }
            for i in range(20)
        ]
        out = bv.metrics(rows)
        ci = out["OVERALL"]["ci95_recall@1"]
        self.assertEqual(len(ci), 2)
        self.assertLessEqual(ci[0], out["OVERALL"]["recall@1"])
        self.assertGreaterEqual(ci[1], out["OVERALL"]["recall@1"])
        # Deterministic: same rows, same interval.
        again = bv.metrics(rows)
        self.assertEqual(again["OVERALL"]["ci95_recall@1"], ci)


class TestT5SeedFailure(unittest.TestCase):
    # J3: a failed T5 lexikon seed must skip the T5 lane visibly, never
    # score meaningless T5 queries against an unseeded lexikon.

    def _stage_t5_pair(self, root):
        import random

        bv.BENCH_ROOT = Path(root) / "roots"
        bv.BENCH_ROOT.mkdir(parents=True)
        proj = bv.BENCH_ROOT / "bench-t5"
        d = proj / "directives"
        d.mkdir(parents=True)
        (d / "alpha.md").write_text(
            "# Alpha\ndispatch gateway packets north\n", encoding="utf-8"
        )
        (d / "beta.md").write_text("# Beta\nfiller words only here\n", encoding="utf-8")
        return proj, random.Random(42)

    def test_fixture_derives_t5_when_seed_succeeds(self):
        import tempfile

        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            proj, rng = self._stage_t5_pair(td)
            with patch.object(bv.mem, "PROJECT_ROOTS", [bv.BENCH_ROOT]):
                with patch.object(bv.mem, "EXTRA_ROOTS_FILE", Path(td) / "extra.json"):
                    queries = bv.derive_queries(proj, rng, "md")
        taxons = [t for t, _, _ in queries]
        self.assertIn("T5", taxons)

    def test_seed_failure_skips_t5_and_flags(self):
        import tempfile

        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            proj, rng = self._stage_t5_pair(td)
            with patch.object(bv.mem, "PROJECT_ROOTS", [bv.BENCH_ROOT]):
                with patch.object(bv.mem, "EXTRA_ROOTS_FILE", Path(td) / "extra.json"):
                    with patch.object(
                        bv.MemoryEngine,
                        "add_lexikon_term",
                        side_effect=RuntimeError("seed boom"),
                    ):
                        queries = bv.derive_queries(proj, rng, "md")
        taxons = [t for t, _, _ in queries]
        self.assertNotIn("T5", taxons)
        self.assertTrue(getattr(bv.derive_queries, "_t5_seed_failed", False))


if __name__ == "__main__":
    unittest.main()
