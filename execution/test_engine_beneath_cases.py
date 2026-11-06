# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Acceptance: Engine Beneath case registry is open, deterministic, and red-capable."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "eval"))

from engine_beneath_cases import (  # noqa: E402
    _CASES,
    all_cases,
    register_case,
    run_all,
)


class TestEngineBeneathCases(unittest.TestCase):
    def test_registry_is_open_and_named(self):
        names = all_cases()
        self.assertGreaterEqual(len(names), 7)
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.assertIn(name, _CASES)

    def test_every_case_returns_a_verdict_record(self):
        result = run_all()
        self.assertEqual(result["schema"], "rtr-re.engine-beneath.cases/v1")
        self.assertEqual(result["summary"]["cases"], len(all_cases()))
        for case in result["cases"]:
            self.assertIn("case", case)
            self.assertIn("verdict", case)
            self.assertIn("checks", case)
            self.assertIn("required", case)
            self.assertIn("evidence", case)
            self.assertIn(case["verdict"], ("pass", "fail"))

    def test_red_capable_scoreboard(self):
        @register_case("deliberately-broken-red-proof")
        def _broken() -> dict:
            return {
                "case": "deliberately-broken-red-proof",
                "description": "must fail",
                "checks": {"always_false": 0.0},
                "required": ["always_false"],
                "verdict": "fail",
                "failed_required": ["always_false"],
                "evidence": {},
            }

        try:
            result = run_all()
            self.assertFalse(result["summary"]["pass"])
            self.assertGreaterEqual(result["summary"]["failed"], 1)
            broken = [
                c
                for c in result["cases"]
                if c["case"] == "deliberately-broken-red-proof"
            ]
            self.assertEqual(len(broken), 1)
            self.assertEqual(broken[0]["verdict"], "fail")
            self.assertEqual(broken[0]["failed_required"], ["always_false"])
        finally:
            _CASES.pop("deliberately-broken-red-proof", None)

    def test_corrupted_sink_case_surfaces_failure(self):
        result = run_all()
        case = next(
            c for c in result["cases"] if c["case"] == "corrupted-sink-reports-failed"
        )
        self.assertEqual(case["verdict"], "pass")
        self.assertEqual(case["evidence"]["status"], "failed")
        self.assertTrue(case["evidence"]["error"])

    def test_duplicate_case_is_deterministic(self):
        result = run_all()
        case = next(
            c
            for c in result["cases"]
            if c["case"] == "duplicate-submission-deterministic"
        )
        self.assertEqual(case["verdict"], "pass")


if __name__ == "__main__":
    unittest.main()
