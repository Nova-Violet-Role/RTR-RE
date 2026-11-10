# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""TUI renderer pins: status tags, panel borders, table shapes."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))

from tui_renderer import TUIRenderer


class TestTuiRenderer(unittest.TestCase):
    def test_status_tags_map_known_states(self):
        self.assertEqual(TUIRenderer.status_tag("ok"), "🟢 SUCCESS")
        self.assertEqual(TUIRenderer.status_tag("error"), "🔴 ERROR")
        self.assertEqual(TUIRenderer.status_tag("search"), "🔍 SEARCHING")
        self.assertEqual(TUIRenderer.status_tag("restore"), "🧠 RESTORING")

    def test_unknown_status_falls_through_with_bulb(self):
        self.assertEqual(TUIRenderer.status_tag("weird"), "💡 WEIRD")

    def test_panel_has_borders_and_title(self):
        out = TUIRenderer.render_panel("Hello", ["line one"], status="ok")
        self.assertTrue(out.startswith("╔"))
        self.assertIn("Hello", out)
        self.assertIn("line one", out)
        self.assertTrue(out.rstrip().endswith("╝"))

    def test_panel_wraps_long_lines(self):
        out = TUIRenderer.render_panel("W", ["x" * 200], status="ok", width=70)
        for line in out.split("\n")[1:-1]:
            self.assertLessEqual(len(line), 70)

    def test_table_shapes_and_empty(self):
        self.assertEqual(TUIRenderer.render_table(["H"], []), ["No data available"])
        rows = TUIRenderer.render_table(["A", "B"], [["1", "2"]])
        self.assertEqual(len(rows), 3)
        self.assertIn("A", rows[0])
        self.assertIn("1", rows[2])


if __name__ == "__main__":
    unittest.main()
