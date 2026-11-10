# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""profile_run: hot-frame math plus a live py-spy record smoke test."""

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "profile_run", ROOT / "scripts" / "profile_run.py"
)
assert SPEC and SPEC.loader
pr = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pr
assert SPEC.loader
SPEC.loader.exec_module(pr)


class TestHotFrames(unittest.TestCase):
    def test_ranks_by_sample_weight(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "s.json"
            p.write_text(
                json.dumps(
                    {
                        "profiles": [
                            {
                                "frames": [{"name": "a"}, {"name": "b"}],
                                "samples": [[[0], 10], [[0, 1], 5], [[1], 1]],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            hot = pr.hot_frames(p, top=2)
            self.assertEqual(hot[0]["frame"], "a")
            self.assertEqual(hot[0]["weight"], 15)
            self.assertEqual(hot[1]["frame"], "b")
            self.assertEqual(hot[1]["weight"], 6)

    def test_empty_profile_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "s.json"
            p.write_text(json.dumps({"profiles": []}), encoding="utf-8")
            self.assertEqual(pr.hot_frames(p), [])


class TestLiveRecord(unittest.TestCase):
    def test_dump_captures_live_stacks(self):
        import subprocess
        import time

        if shutil.which("py-spy") is None:
            self.skipTest("py-spy not on PATH")
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(8)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(1.0)
            try:
                out = pr.dump_pid(proc.pid)
            except RuntimeError as e:
                # py-spy cannot read uv's temp-build interpreters
                # ("Failed to find python version"); stable installs dump
                # fine (proven live on the tool-env server).
                if "Failed to find python version" in str(e):
                    self.skipTest(f"py-spy cannot read this interpreter: {e}")
                raise
        finally:
            proc.terminate()
            proc.wait(timeout=10)
        self.assertIn("Python", out)
        self.assertIn("Thread", out)


if __name__ == "__main__":
    unittest.main()
