# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Cross-surface parity: every hardcoded mirror must match its source.

Plates hardcode taxon lists and system colors; frame collages hardcode
bench numbers; Lean models hardcode engine constants. When a source
moves, its mirrors must move too — these tests are the tripwires.
"""

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


class TestPlateBenchParity(unittest.TestCase):
    def test_plate_taxons_cover_bench_taxons(self):
        pv = _load("plates_versus", "eval/plates_versus.py")
        bv = _load("bench_versus", "eval/bench_versus.py")
        bench_taxons = set(bv.CAPS) | set(bv.DTD_CAPS) | {"T4", "T5", "T6", "T13"}
        for taxon in bench_taxons:
            self.assertIn(taxon, pv.TAXONS, f"plate drops {taxon}")

    def test_plate_colors_cover_bench_systems(self):
        pv = _load("plates_versus", "eval/plates_versus.py")
        bv = _load("bench_versus", "eval/bench_versus.py")
        for system in bv.SYSTEMS:
            self.assertIn(system, pv.SERIES_FILL, f"plate grays {system}")


class TestCollageArtifactParity(unittest.TestCase):
    def _collage_text(self):
        spec = importlib.util.spec_from_file_location(
            "make_frames_src", ROOT / "media" / "make_frames.py"
        )
        # Read source without executing (no PIL needed for the pin).
        return (ROOT / "media" / "make_frames.py").read_text(encoding="utf-8")

    def test_collage_headlines_match_frozen_versus(self):
        text = self._collage_text()
        frozen = json.loads(
            (ROOT / "eval" / "results" / "versus.json").read_text(encoding="utf-8")
        )
        full = frozen["combined"]["rtr-full"]["metrics"]["OVERALL"]
        for key in ("recall@1", "recall@3", "mrr"):
            val = f"{full[key]:.3f}"
            self.assertIn(val, text, f"collage stale on rtr-full {key} {val}")

    def test_collage_query_count_matches_frozen(self):
        text = self._collage_text()
        frozen = json.loads(
            (ROOT / "eval" / "results" / "versus.json").read_text(encoding="utf-8")
        )
        n = frozen["combined"]["rtr-full"]["n"]
        self.assertIn(str(n), text)


class TestLeanCodeParity(unittest.TestCase):
    def test_lane_cap_matches_engine_weight(self):
        lane_src = (ROOT / "formal" / "Symbiose" / "Lane.lean").read_text(
            encoding="utf-8"
        )
        self.assertIn("def laneCap : Rat := 3 / 20", lane_src)
        sys.path.insert(0, str(ROOT / "execution"))
        import memory_engine

        self.assertAlmostEqual(memory_engine.EXACT_LANE_WEIGHT, 3 / 20)

    def test_gain_table_matches_graded_metrics(self):
        sys.path.insert(0, str(ROOT / "execution"))
        import graded_metrics

        self.assertEqual([graded_metrics.gain(g) for g in range(4)], [0, 1, 3, 7])
        graded_src = (ROOT / "formal" / "Symbiose" / "Graded.lean").read_text(
            encoding="utf-8"
        )
        self.assertIn("gain 0 = 0 ∧ gain 1 = 1 ∧ gain 2 = 3 ∧ gain 3 = 7", graded_src)

    def test_control_verbs_cover_keeper_verbs(self):
        control_src = (ROOT / "formal" / "Symbiose" / "Control.lean").read_text(
            encoding="utf-8"
        )
        keeper_src = (ROOT / "opencode-plugin" / "rtr-re-keeper.js").read_text(
            encoding="utf-8"
        )
        m = re.search(r"const numeric = \{([^}]+)\}", keeper_src)
        self.assertIsNotNone(m, "keeper numeric verb map not found")
        verbs = re.findall(r"(\w+):", m.group(1))
        verbs += ["status", "help", "enable", "disable", "preset", "cpu", "modality"]
        verbs += ["threads", "parking"]
        for verb in verbs:
            self.assertIn(f".{verb}", control_src, f"Lean drops verb {verb}")


if __name__ == "__main__":
    unittest.main()
