# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent.absolute()))
SPEC = importlib.util.spec_from_file_location(
    "calibrate_symbiose", ROOT / "eval" / "calibrate_symbiose.py"
)
assert SPEC and SPEC.loader
cal = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cal)


class TestCalibrationTool(unittest.TestCase):
    def test_generated_markdown_is_lf_bytes(self):
        import tempfile

        payload = {
            "profile": {"trigger": 40000, "target": 20000, "sink": "file"},
            "summary": [],
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "calibration.md"
            cal.write_markdown(path, payload)
            self.assertNotIn(b"\r", path.read_bytes())

    def test_parse_token_counts(self):
        self.assertEqual(cal.parse_token_count("40000"), 40000)
        self.assertEqual(cal.parse_token_count("40k"), 40000)
        self.assertEqual(cal.parse_token_count("1.5k"), 1500)
        with self.assertRaises(Exception):
            cal.parse_token_count("0")
        with self.assertRaises(Exception):
            cal.parse_token_count("many")

    def test_generate_messages_exact_estimate_and_lanes(self):
        msgs = cal.generate_messages(1000, message_count=4, salt="unit")
        self.assertEqual(len(msgs), 4)
        self.assertEqual(sum(len(m["text"]) for m in msgs), 4000)
        self.assertEqual(msgs[-1]["role"], "user")
        self.assertTrue(msgs[0]["text"].startswith("[unit:0]"))

    def test_summarize_groups_and_humanizes(self):
        rows = [
            {
                "context_tokens": 40000,
                "status": "ready",
                "submit_ms": 1.0,
                "queue_ms": 2.0,
                "plan_ms": 3.0,
                "sink_ms": 4.0,
                "elapsed_ms": 10.0,
            },
            {
                "context_tokens": 40000,
                "status": "ready",
                "submit_ms": 3.0,
                "queue_ms": 4.0,
                "plan_ms": 5.0,
                "sink_ms": 6.0,
                "elapsed_ms": 30.0,
            },
        ]
        out = cal.summarize(rows)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["elapsed_ms"]["median"], 20.0)
        self.assertEqual(out[0]["elapsed_ms"]["median_human"], "20.0 ms")
        self.assertEqual(out[0]["tokens_per_second_median"], 2_000_000.0)


if __name__ == "__main__":
    unittest.main()
