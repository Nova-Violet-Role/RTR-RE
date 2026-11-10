# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Infinite-context plate: numbers present, SVG well-formed, layers three."""

import importlib.util
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "infinite_context_plate", ROOT / "media" / "infinite_context_plate.py"
)
assert SPEC and SPEC.loader
plate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = plate
assert SPEC.loader
SPEC.loader.exec_module(plate)


class TestInfinitePlate(unittest.TestCase):
    def test_ascii_carries_all_numbers_and_layers(self):
        text = plate.render_ascii(3394962, 1146, 61276, 389999)
        for needle in ("3,394,962", "1,146", "61,276", "389,999"):
            self.assertIn(needle, text)
        for layer in ("LIVE WINDOW", "SUNK SPANS", "CHROMA VECTORS"):
            self.assertIn(layer, text)
        self.assertIn("never deleted", text)

    def test_svg_is_well_formed_and_labeled(self):
        svg = plate.render_svg(3394962, 1146, 61276, 389999)
        root = ET.fromstring(svg)
        self.assertTrue(root.tag.endswith("svg"))
        self.assertIn("3,394,962", svg)
        self.assertIn("CHROMA VECTORS", svg)


if __name__ == "__main__":
    unittest.main()
