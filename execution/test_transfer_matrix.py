"""Tests for the cross-family transfer matrix instrument (TODO-35).

The instrument is an evaluation probe (eval/transfer_matrix.py): it
computes pairwise vocabulary overlap between DTD families from the
catalogue. These tests pin the pure functions and the known-answer
properties of the matrix on synthetic input.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "transfer_matrix", ROOT / "eval" / "transfer_matrix.py"
)
assert SPEC and SPEC.loader
tm = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = tm
assert SPEC.loader
SPEC.loader.exec_module(tm)


class TestFamilyOf(unittest.TestCase):
    def test_nested_file_belongs_to_directory_family(self):
        self.assertEqual(
            tm.family_of(r"C:\DTD_FAMILY\.dtd-file-examples\daisy\bookmark.dtd"),
            "daisy",
        )

    def test_root_level_file_belongs_to_root(self):
        self.assertEqual(
            tm.family_of(r"C:\DTD_FAMILY\.dtd-file-examples\schema.dtd"),
            "(root)",
        )

    def test_unknown_root_falls_back_to_root(self):
        self.assertEqual(tm.family_of(r"C:\elsewhere\file.dtd"), "(root)")


class TestSimilarity(unittest.TestCase):
    def test_jaccard(self):
        self.assertEqual(tm.jaccard({"a", "b"}, {"b", "c"}), 1 / 3)

    def test_jaccard_empty_both(self):
        self.assertEqual(tm.jaccard(set(), set()), 0.0)

    def test_containment(self):
        self.assertEqual(tm.containment({"a", "b"}, {"b", "c"}), 0.5)
        self.assertEqual(tm.containment(set(), {"a"}), 0.0)


class TestMatrixStructure(unittest.TestCase):
    def _write_catalogue(self, tmp: Path) -> Path:
        files = [
            {
                "path": r"C:\DTD_FAMILY\.dtd-file-examples\a\one.dtd",
                "element_names": ["x", "y", "z"],
                "attribute_names": ["p", "q"],
                "entity_names": [],
                "notation_names": [],
            },
            {
                "path": r"C:\DTD_FAMILY\.dtd-file-examples\a\two.dtd",
                "element_names": ["x", "y"],
                "attribute_names": ["p"],
                "entity_names": [],
                "notation_names": [],
            },
            {
                "path": r"C:\DTD_FAMILY\.dtd-file-examples\b\one.dtd",
                "element_names": ["x", "w"],
                "attribute_names": ["r"],
                "entity_names": [],
                "notation_names": [],
            },
            {
                "path": r"C:\DTD_FAMILY\.dtd-file-examples\c\one.dtd",
                "element_names": ["m", "n"],
                "attribute_names": ["s"],
                "entity_names": [],
                "notation_names": [],
            },
        ]
        cat = {"files": files}
        path = tmp / "catalogue.json"
        path.write_text(json.dumps(cat), encoding="utf-8")
        return path

    def test_family_vocabularies_union(self):
        with tempfile.TemporaryDirectory() as d:
            cat_path = self._write_catalogue(Path(d))
            cat = json.loads(cat_path.read_text(encoding="utf-8"))
            fam = tm.family_vocabularies(cat)
            self.assertEqual(set(fam["a"]["elements"]), {"x", "y", "z"})
            self.assertEqual(set(fam["b"]["elements"]), {"x", "w"})
            self.assertEqual(set(fam["c"]["elements"]), {"m", "n"})

    def test_matrix_pair_properties(self):
        with tempfile.TemporaryDirectory() as d:
            cat_path = self._write_catalogue(Path(d))
            cat = json.loads(cat_path.read_text(encoding="utf-8"))
            fam = tm.family_vocabularies(cat)
            matrix = tm.build_matrix(fam)
            ab = next(
                p
                for p in matrix["pairs"]
                if p["family_a"] == "a" and p["family_b"] == "b"
            )
            self.assertEqual(ab["family_b"], "b")
            self.assertGreater(ab["combined_jaccard"], 0.0)
            self.assertGreater(ab["combined_containment_a_in_b"], 0.0)
            self.assertLess(ab["combined_containment_b_in_a"], 1.0)
            ac = next(
                p
                for p in matrix["pairs"]
                if {p["family_a"], p["family_b"]} == {"a", "c"}
            )
            self.assertEqual(ac["combined_jaccard"], 0.0)

    def test_lane_decision_bands(self):
        decision = tm.lane_decision({"pairs": []})
        self.assertIn("decision", decision)
        self.assertIn("unified", decision["decision"])


if __name__ == "__main__":
    unittest.main()
