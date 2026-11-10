# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""preset-perf plates: shapes, files, white+dark pair."""

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "plates_preset_perf", ROOT / "eval" / "plates_preset_perf.py"
)
assert SPEC and SPEC.loader
pp = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pp
assert SPEC.loader
SPEC.loader.exec_module(pp)


class TestPresetPerfPlates(unittest.TestCase):
    def _data(self):
        return {
            "combos": [
                {"threads": 2, "index_s": 0.7, "search_p50_ms": 9.5},
                {"threads": 8, "index_s": 0.5, "search_p50_ms": 7.9},
            ]
        }

    def test_render_carries_numbers_both_themes(self):
        for dark in (False, True):
            svg = pp.render(self._data(), dark=dark)
            self.assertIn("0.7", svg)
            self.assertIn("T8", svg)
            self.assertIn("<svg", svg)

    def test_artifacts_exist_as_a_pair(self):
        self.assertTrue((ROOT / "eval" / "preset-perf.svg").exists())
        self.assertTrue((ROOT / "eval" / "preset-perf-dark.svg").exists())


if __name__ == "__main__":
    unittest.main()
