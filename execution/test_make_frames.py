# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""make_frames determinism: two runs produce byte-identical frames."""

import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _frame_hash():
    return hashlib.sha256(
        (ROOT / "media" / "frames-a" / "frame-01.png").read_bytes()
    ).hexdigest()


def _run_make_frames():
    spec = importlib.util.spec_from_file_location(
        "make_frames_run", ROOT / "media" / "make_frames.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    assert spec.loader
    spec.loader.exec_module(mod)


class TestMakeFrames(unittest.TestCase):
    def test_two_runs_are_byte_identical(self):
        _run_make_frames()
        first = _frame_hash()
        _run_make_frames()
        self.assertEqual(_frame_hash(), first)

    def test_collages_cover_78_frames(self):
        count = len(sorted((ROOT / "media").glob("frames-[abc]/frame-*.png")))
        self.assertEqual(count, 78)


if __name__ == "__main__":
    unittest.main()
