# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""verify_release red-capability: the secret tripwire must fire on dirty
input and stay silent on code-shaped lookalikes."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "verify_release", ROOT / "scripts" / "verify_release.py"
)
assert SPEC and SPEC.loader
vr = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = vr
assert SPEC.loader
SPEC.loader.exec_module(vr)


class TestSecretTripwire(unittest.TestCase):
    def test_fires_on_dirty_and_silent_on_code(self):
        before = len(vr.failures)
        vr.scan_text_for_secrets('{"api_key": "sk-abc123"}', "dirty")
        self.assertEqual(len(vr.failures), before + 1)
        vr.scan_text_for_secrets("def f(token: str): return token", "clean")
        vr.scan_text_for_secrets("ghp_" + "x" * 10, "short")
        self.assertEqual(len(vr.failures), before + 1)
        vr.failures.clear()

    def test_fires_on_github_token_shapes(self):
        before = len(vr.failures)
        vr.scan_text_for_secrets("key=ghp_" + "a" * 21, "ghp")
        self.assertEqual(len(vr.failures), before + 1)
        vr.failures.clear()


if __name__ == "__main__":
    unittest.main()
