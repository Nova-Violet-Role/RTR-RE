# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""parity_gate: one-shot arming plus live-tree checks."""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "parity_gate", ROOT / "scripts" / "parity_gate.py"
)
assert SPEC and SPEC.loader
pg = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pg
assert SPEC.loader
SPEC.loader.exec_module(pg)


class TestOneShot(unittest.TestCase):
    def test_consumed_state_refuses_without_arm(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "state.json"
            fake.write_text('{"consumed": true}', encoding="utf-8")
            with patch.object(pg, "STATE_PATH", fake):
                self.assertEqual(pg.main([]), 2)

    def test_arm_runs_and_consumes(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "state.json"
            with patch.object(pg, "STATE_PATH", fake):
                rc = pg.main(["--arm"])
                self.assertIn(rc, (0, 1))
                self.assertTrue(fake.exists())


class TestLiveTree(unittest.TestCase):
    def test_versions_cohere_at_package_version(self):
        import tomllib

        with open(ROOT / "pyproject.toml", "rb") as f:
            expected = tomllib.load(f)["project"]["version"]
        for name, val in pg.versions().items():
            self.assertEqual(val, expected, name)

    def test_command_counts(self):
        counts = pg.command_counts()
        self.assertEqual(counts["palette"], 14)
        self.assertEqual(counts["rtr_verbs"], 16)
        self.assertEqual(counts["cli_verbs"], 21)
        self.assertEqual(counts["mcp_tools"], 32)


if __name__ == "__main__":
    unittest.main()
