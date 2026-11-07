# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Regression gate acceptance tests (TODO-43).

Proves the gate is red-capable: a deliberately broken current file must
make it exit 1, and the real frozen state must exit 0.
"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))
sys.path.insert(0, str(Path(__file__).parent.parent.absolute() / "eval"))

import regression_gate as gate

RESULTS = Path(__file__).parent.parent / "eval" / "results"


class TestRegressionGate(unittest.TestCase):
    def setUp(self):
        self.baseline = gate.load(RESULTS / "baseline-1.0.0.json")
        self.versus = gate.load(RESULTS / "versus.json")
        self.eb = gate.load(RESULTS / "engine-beneath-cases.json")

    def _write(self, tmp, obj):
        p = tmp / "current.json"
        p.write_text(json.dumps(obj), encoding="utf-8")
        return str(p)

    def test_real_state_passes(self):
        self.assertEqual(gate.main([]), 0)

    def test_lowered_score_goes_red(self):
        with tempfile.TemporaryDirectory() as td:
            broken = copy.deepcopy(self.versus)
            corpus = broken["corpora"]["dtd-family"]["systems"]["rtr-full"]
            corpus["metrics"]["OVERALL"]["recall@1"] = 0.1
            p = self._write(Path(td), broken)
            self.assertEqual(
                gate.main(
                    [
                        str(RESULTS / "baseline-1.0.0.json"),
                        p,
                        str(RESULTS / "engine-beneath-cases.json"),
                    ]
                ),
                1,
            )

    def test_failed_case_goes_red(self):
        with tempfile.TemporaryDirectory() as td:
            broken = copy.deepcopy(self.eb)
            broken["cases"][0]["verdict"] = False
            p = self._write(Path(td), broken)
            self.assertEqual(
                gate.main(
                    [
                        str(RESULTS / "baseline-1.0.0.json"),
                        str(RESULTS / "versus.json"),
                        p,
                    ]
                ),
                1,
            )

    def test_missing_case_goes_red(self):
        with tempfile.TemporaryDirectory() as td:
            broken = copy.deepcopy(self.eb)
            broken["cases"] = broken["cases"][:-1]
            broken["summary"]["cases"] = len(broken["cases"])
            p = self._write(Path(td), broken)
            self.assertEqual(
                gate.main(
                    [
                        str(RESULTS / "baseline-1.0.0.json"),
                        str(RESULTS / "versus.json"),
                        p,
                    ]
                ),
                1,
            )

    def test_missing_source_exits_2(self):
        with self.assertRaises(SystemExit) as cm:
            gate.main(
                [
                    str(RESULTS / "baseline-1.0.0.json"),
                    "C:/definitely/not/here.json",
                    "x",
                ]
            )
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
