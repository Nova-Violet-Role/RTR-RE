# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Plate tests: versus T10-set counting plus graded doctor red-capability."""

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


pv = _load("plates_versus", "eval/plates_versus.py")
pg = _load("plates_graded", "eval/plates_graded.py")


def _versus_data(rows):
    return {
        "seed": 1,
        "corpora": {"c1": {"files": 1, "systems": {"rtr-full": {"rows": rows}}}},
        "combined": {
            "rtr-full": {
                "n": len(rows),
                "metrics": {
                    "OVERALL": {"recall@1": 1.0, "recall@3": 1.0, "mrr": 1.0},
                },
            }
        },
    }


class TestPlatesVersus(unittest.TestCase):
    def test_t10_expected_sets_count_as_hits(self):
        rows = [
            {
                "taxon": "T10",
                "expected": ["a.dtd", "b.dtd"],
                "got": ["b.dtd", "x"],
                "ms": 1.0,
            }
        ]
        data = _versus_data(rows)
        table = pv.combined_taxon_recall3(data, ["rtr-full"])
        self.assertEqual(table["rtr-full"]["T10"], 1.0)

    def test_systems_of_refuses_missing_rows(self):
        data = _versus_data([])
        data["corpora"]["c1"]["systems"] = {}
        with self.assertRaises(SystemExit):
            pv.systems_of(data)


def _graded_data(ndcg=0.5, unjudged=1):
    row = {
        "query_id": "q1",
        "corpus": "c1",
        "scores": {"ndcg@10": ndcg, "unjudged_returned": unjudged},
    }
    return {
        "dataset": "gold-v2-test",
        "depth": 20,
        "queries": 1,
        "judgments": 1,
        "corpora": {"c1": {"systems": {"rtr-full": {"rows": [row]}}}},
        "combined": {
            "rtr-full": {"ndcg@10": ndcg, "unjudged_returned": unjudged},
        },
    }


class TestPlatesGradedDoctor(unittest.TestCase):
    def test_doctor_accepts_honest_data(self):
        systems, rows = pg.doctor(_graded_data())
        self.assertEqual(systems, ["rtr-full"])
        self.assertEqual(len(rows["rtr-full"]), 1)

    def test_doctor_refuses_forged_combined(self):
        data = _graded_data()
        data["combined"]["rtr-full"]["ndcg@10"] = 0.9999
        with self.assertRaises(SystemExit):
            pg.doctor(data)

    def test_doctor_refuses_wrong_dataset(self):
        data = _graded_data()
        data["dataset"] = "gold-v9-fake"
        with self.assertRaises(SystemExit):
            pg.doctor(data)


if __name__ == "__main__":
    unittest.main()
