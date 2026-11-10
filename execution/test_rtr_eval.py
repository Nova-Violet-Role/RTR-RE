# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Smoke + isolation test for the rtr_eval release gate.

The gate must pass end to end on its fixture AND leave a pre-existing
global lexikon byte-identical (its lexikon probe term must not leak).
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))

import memory_engine as mem


class TestRtrEvalGate(unittest.TestCase):
    def test_gate_passes_and_restores_global_lexikon(self):
        import rtr_eval

        tmp = tempfile.TemporaryDirectory()
        try:
            mdir = Path(tmp.name) / "memory"
            dbd = mdir / ".local_vector_db"
            old = {}
            for attr, val in [
                ("MEMORY_DIR", mdir),
                ("DB_DIR", dbd),
                ("REGISTRY_FILE", mdir / "wiki_registry.json"),
                ("EXTRA_ROOTS_FILE", mdir / "extra_roots.json"),
                ("LEXIKON_GLOBAL_FILE", mdir / "lexikon_global.json"),
            ]:
                old[attr] = getattr(mem, attr)
                setattr(mem, attr, val)
            try:
                pre = {
                    "terms": {
                        "sacred term": {
                            "term": "Sacred Term",
                            "definition": "untouchable",
                            "aliases": [],
                            "source": "hand",
                        }
                    }
                }
                (mdir / "lexikon_global.json").parent.mkdir(parents=True, exist_ok=True)
                (mdir / "lexikon_global.json").write_text(
                    json.dumps(pre), encoding="utf-8"
                )
                code = None
                try:
                    rtr_eval.main()
                except SystemExit as e:
                    code = e.code
                after = json.loads(
                    (mdir / "lexikon_global.json").read_text(encoding="utf-8")
                )
                self.assertEqual(after, pre)
                self.assertEqual(code, 0)
            finally:
                for attr, val in old.items():
                    setattr(mem, attr, val)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
