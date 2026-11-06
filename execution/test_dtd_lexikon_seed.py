"""Tests for DTD lexikon seeding (TODO-37).

Covers: the extractor's attribute->owner mapping, the seed_dtd_lexikon
lane discipline (source present, single owner, alias present in owner
file, alias differs from source, empty definition), and that a seeded
term resolves through the engine's lexikon expansion.
"""

from __future__ import annotations

import hashlib
import importlib.util
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "bench_versus", ROOT / "eval" / "bench_versus.py"
)
assert SPEC and SPEC.loader
b = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = b
assert SPEC.loader
SPEC.loader.exec_module(b)

sys.path.insert(0, str(ROOT / "eval"))
import dtd_extractor as dx
import memory_engine as mem

SAMPLE_DTD = """<!ELEMENT book (title, chapter*)>
<!ATTLIST book version CDATA #IMPLIED>
<!ATTLIST chapter id ID #REQUIRED>
<!ENTITY lc "Lowest Common Denominator">
<!ENTITY % common.attrib "id ID #IMPLIED">
<!NOTATION gif SYSTEM "image/gif">
"""


class TestExtractorAttrOwners(unittest.TestCase):
    def test_attr_owners_maps_attr_to_element(self):
        scanned = dx.mask_entity_bodies(SAMPLE_DTD)
        owners = dx.extract_attr_owners(scanned)
        self.assertEqual(owners.get("version"), "book")
        self.assertEqual(owners.get("id"), "chapter")

    def test_profile_carries_owners(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sample.dtd"
            p.write_text(SAMPLE_DTD, encoding="utf-8")
            prof = dx.extract_dtd_profile(p)
            self.assertEqual(prof.attribute_owners.get("version"), "book")
            d = prof.to_dict()
            self.assertEqual(d["attribute_owners"]["version"], "book")

    def test_first_declaration_wins(self):
        dtd = (
            "<!ELEMENT a EMPTY>\n"
            "<!ATTLIST a id ID #IMPLIED>\n"
            "<!ATTLIST b id ID #IMPLIED>\n"
        )
        scanned = dx.mask_entity_bodies(dtd)
        owners = dx.extract_attr_owners(scanned)
        self.assertEqual(owners.get("id"), "a")


class TestSeedDtdLexikon(unittest.TestCase):
    def _stage_tiny(self):
        tmp = tempfile.TemporaryDirectory()
        proj = Path(tmp.name) / "bench-tiny"
        d = proj / "directives"
        d.mkdir(parents=True)
        (d / "alpha.dtd").write_text(
            "<!ELEMENT alpha (beta*)>\n"
            "<!ATTLIST alpha rareattr CDATA #IMPLIED>\n"
            '<!ENTITY uniquebody "x">\n',
            encoding="utf-8",
        )
        (d / "beta.dtd").write_text(
            "<!ELEMENT beta EMPTY>\n<!ATTLIST beta commonattr CDATA #IMPLIED>\n",
            encoding="utf-8",
        )
        mem.PROJECT_ROOTS = [proj.parent]
        mem.PROJECTS_DIR = proj.parent
        return tmp, proj

    def test_seeding_respects_lane_discipline(self):
        tmp, proj = self._stage_tiny()
        try:
            crng = random.Random(42)
            count = b.seed_dtd_lexikon(proj, crng)
            lex = mem.MemoryEngine().get_lexikon(str(proj))
            terms = lex
            # rareattr: df==1, owner alpha -> seeded
            self.assertIn("rareattr", terms)
            self.assertEqual(terms["rareattr"]["aliases"], ["alpha"])
            self.assertEqual(terms["rareattr"]["definition"], "")
            # uniquebody: df==1, root alpha -> seeded
            self.assertIn("uniquebody", terms)
            self.assertEqual(terms["uniquebody"]["aliases"], ["alpha"])
            # commonattr: df==1 too (only in beta) -> seeded with owner beta
            self.assertIn("commonattr", terms)
            self.assertEqual(terms["commonattr"]["aliases"], ["beta"])
            self.assertGreaterEqual(count, 3)
        finally:
            tmp.cleanup()

    def test_expansion_resolves_seeded_term(self):
        tmp, proj = self._stage_tiny()
        try:
            crng = random.Random(42)
            b.seed_dtd_lexikon(proj, crng)
            eng = mem.MemoryEngine()
            expanded = eng.lexikon_expansion(str(proj), "rareattr")
            self.assertIn("alpha", expanded)
            eng.close()
        finally:
            tmp.cleanup()

    def test_seeding_skips_multi_owner(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            proj = Path(tmp.name) / "bench-multi"
            d = proj / "directives"
            d.mkdir(parents=True)
            shared = (
                "<!ELEMENT shared EMPTY>\n<!ATTLIST shared dupattr CDATA #IMPLIED>\n"
            )
            (d / "one.dtd").write_text(shared, encoding="utf-8")
            (d / "two.dtd").write_text(shared, encoding="utf-8")
            mem.PROJECT_ROOTS = [proj.parent]
            mem.PROJECTS_DIR = proj.parent
            crng = random.Random(42)
            b.seed_dtd_lexikon(proj, crng)
            lex = mem.MemoryEngine().get_lexikon(str(proj))
            terms = lex
            # dupattr appears in two files -> df==2 -> not seeded
            self.assertNotIn("dupattr", terms)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
