# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))

from graded_metrics import (
    average_precision,
    build_pool,
    err_at_k,
    gain,
    graded_precision_at_k,
    load_qrels,
    load_queries,
    ndcg_at_k,
    validate_dataset,
)


QRELS = {
    "q1": {"d3": 3, "d2": 2, "d1": 1, "d0": 0},
}


class TestGradedMetrics(unittest.TestCase):
    def test_gain_mapping_is_frozen(self):
        self.assertEqual([gain(g) for g in (0, 1, 2, 3)], [0, 1, 3, 7])
        with self.assertRaises(ValueError):
            gain(4)

    def test_perfect_ranking_ndcg_is_one(self):
        got = ["d3", "d2", "d1", "d0"]
        self.assertAlmostEqual(ndcg_at_k(got, QRELS["q1"], 4), 1.0)

    def test_reversed_ranking_hand_checked(self):
        got = ["d1", "d2", "d3"]
        dcg = 1 / math.log2(2) + 3 / math.log2(3) + 7 / math.log2(4)
        ideal = 7 / math.log2(2) + 3 / math.log2(3) + 1 / math.log2(4)
        self.assertAlmostEqual(ndcg_at_k(got, QRELS["q1"], 3), dcg / ideal)

    def test_duplicates_deduped_before_scoring(self):
        got = ["d3", "d3", "d2"]
        clean = ["d3", "d2"]
        self.assertAlmostEqual(
            ndcg_at_k(got, QRELS["q1"], 2), ndcg_at_k(clean, QRELS["q1"], 2)
        )

    def test_unjudged_counts_as_rank_not_relevant(self):
        stats = ndcg_at_k(["dx", "d3"], QRELS["q1"], 2)
        ideal_top = 7 / math.log2(2) + 3 / math.log2(3)
        self.assertAlmostEqual(stats, (7 / math.log2(3)) / ideal_top)

    def test_empty_ranking_and_no_relevant(self):
        self.assertEqual(ndcg_at_k([], QRELS["q1"], 10), 0.0)
        self.assertEqual(ndcg_at_k(["d3"], {"d3": 0}, 10), 0.0)
        self.assertEqual(err_at_k([], QRELS["q1"], 10), 0.0)
        self.assertEqual(average_precision([], QRELS["q1"]), 0.0)

    def test_err_hand_checked(self):
        # grades 3 then 2: p(stop1)=7/8; contribution2=(1/8)*(3/8)/2
        expected = 7 / 8 + (1 / 8) * (3 / 8) / 2
        self.assertAlmostEqual(err_at_k(["d3", "d2"], QRELS["q1"], 2), expected)

    def test_graded_precision_and_map(self):
        self.assertAlmostEqual(
            graded_precision_at_k(["d3", "d0"], QRELS["q1"], 2), 7 / 14
        )
        # relevant at ranks 2 and 3 of 2 judged-relevant docs: (1/2 + 2/3)/2
        self.assertAlmostEqual(
            average_precision(["d0", "d3", "d2"], QRELS["q1"]), (1 / 2 + 2 / 3) / 2
        )

    def test_pool_is_blind_and_deduped(self):
        rankings = {
            "sys-b": {"q1": ["d2", "d3", "d2"]},
            "sys-a": {"q1": ["d3", "d1"]},
        }
        pool = build_pool(rankings, depth=2)
        blind = pool["q1"]["blind"]
        self.assertEqual(blind, ["d1", "d2", "d3"])
        prov = pool["q1"]["provenance"]
        self.assertEqual(prov["d3"]["sys-a"], 1)
        self.assertEqual(prov["d2"]["sys-b"], 1)
        self.assertNotIn("sys-a", blind)


class TestDatasetLoading(unittest.TestCase):
    def _write(self, td, name, payload):
        p = Path(td) / name
        p.write_bytes(json.dumps(payload).encode("utf-8"))
        return p

    def test_load_and_validate(self):
        with tempfile.TemporaryDirectory() as td:
            qp = self._write(
                td,
                "queries.json",
                {
                    "version": "v1",
                    "queries": [
                        {
                            "id": "q1",
                            "corpus": "nt-studies",
                            "taxon": "G1",
                            "text": "how does branch filtering work",
                            "intent": "define branch filtering",
                        }
                    ],
                },
            )
            rp = self._write(
                td,
                "qrels.json",
                {
                    "version": "v1",
                    "judgments": [
                        {
                            "query_id": "q1",
                            "doc_id": "nt-studies/a.nt",
                            "grade": 3,
                            "rationale": "defining section",
                            "evidence": "title + body",
                            "annotator": "test",
                            "status": "judged",
                        }
                    ],
                },
            )
            queries = load_queries(qp)
            qrels = load_qrels(rp)
            self.assertEqual(queries["q1"]["corpus"], "nt-studies")
            self.assertEqual(qrels["q1"]["nt-studies/a.nt"], 3)
            report = validate_dataset(queries, qrels, {"nt-studies": {"a.nt"}})
            self.assertEqual(report["errors"], [])
            self.assertEqual(report["grade_histogram"], {"3": 1})

    def test_duplicate_and_bad_grade_refused(self):
        with tempfile.TemporaryDirectory() as td:
            rp = self._write(
                td,
                "qrels.json",
                {
                    "version": "v1",
                    "judgments": [
                        {"query_id": "q1", "doc_id": "c/a", "grade": 9},
                        {"query_id": "q1", "doc_id": "c/a", "grade": 1},
                    ],
                },
            )
            with self.assertRaises(ValueError):
                load_qrels(rp)


if __name__ == "__main__":
    unittest.main()
