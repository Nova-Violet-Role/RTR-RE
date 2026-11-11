# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Dedica plate: ASCII plus SVG render the passed-in measured numbers."""

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "dedica_plate", ROOT / "media" / "dedica_plate.py"
)
assert SPEC and SPEC.loader
dp = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = dp
assert SPEC.loader
SPEC.loader.exec_module(dp)


class TestDedica(unittest.TestCase):
    def test_ascii_carries_numbers_and_verdict(self):
        text = dp.render_ascii(3430000, 390000, 1000, 700000)
        self.assertIn("3,430,000", text)
        self.assertIn("391,000", text)
        self.assertIn("88.6", text)
        self.assertIn("no prompt cache", text)

    def test_svg_has_both_bars(self):
        svg = dp.render_svg(3430000, 390000, 1000, 700000)
        self.assertIn("without RTR: 3,430,000", svg)
        self.assertIn("with RTR: 391,000", svg)
        self.assertIn("<svg", svg)


if __name__ == "__main__":
    unittest.main()
