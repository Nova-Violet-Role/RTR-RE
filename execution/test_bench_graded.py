# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Graded bench suffix tests (TODO-24, J15).

The graded bench must stage .dtd sources (dtd-family queries exist
in gold v2); the file-suffix allowlist must include them.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "bench_graded", ROOT / "eval" / "bench_graded.py"
)
assert SPEC and SPEC.loader
bg = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bg
assert SPEC.loader
SPEC.loader.exec_module(bg)


class TestGradedSuffixes(unittest.TestCase):
    def test_suffix_allowlist_includes_dtd_sources(self):
        staged = bg.GRADED_FILE_SUFFIXES.split(",")
        for suffix in (".dtd", ".mod", ".ent"):
            self.assertIn(suffix, staged)


class TestSkippedCorpora(unittest.TestCase):
    def test_corpora_without_gold_queries_are_listed(self):
        # J16: skipped corpora must be recorded, never silent.
        specs = [{"name": "a"}, {"name": "b"}]
        queries = {"q1": {"corpus": "a"}}
        self.assertEqual(bg.skipped_corpora(specs, queries), ["b"])


class TestAggregateCI(unittest.TestCase):
    def _row(self, v):
        return {
            "scores": {
                "ndcg@3": v,
                "ndcg@5": v,
                "ndcg@10": v,
                "ndcg@20": v,
                "err@10": v,
                "gprec@10": v,
                "ap": v,
                "unjudged_returned": 0,
            },
            "ms": 1.0,
        }

    def test_aggregate_carries_bootstrap_ci(self):
        # 25-power: graded means carry seeded 95% CIs like the binary bench.
        rows = [self._row(1.0 if i % 2 == 0 else 0.0) for i in range(20)]
        out = bg.aggregate(rows)
        ci = out["ci95_ndcg@10"]
        self.assertEqual(len(ci), 2)
        self.assertLessEqual(ci[0], out["ndcg@10"])
        self.assertGreaterEqual(ci[1], out["ndcg@10"])
