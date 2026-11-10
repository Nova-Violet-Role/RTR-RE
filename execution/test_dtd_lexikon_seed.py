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
        # The owner element 'doc' appears in both files (df=2): a common
        # element is never a T1 query target, so it is a safe alias.
        (d / "alpha.dtd").write_text(
            "<!ELEMENT doc (beta*)>\n"
            "<!ATTLIST doc rareattr CDATA #IMPLIED>\n"
            '<!ENTITY uniquebody "x">\n',
            encoding="utf-8",
        )
        (d / "beta.dtd").write_text(
            "<!ELEMENT doc EMPTY>\n<!ATTLIST doc commonattr CDATA #IMPLIED>\n",
            encoding="utf-8",
        )
        mem.PROJECT_ROOTS = [proj.parent]
        mem.PROJECTS_DIR = proj.parent
        return tmp, proj

    def test_seeding_respects_lane_discipline(self):
        tmp, proj = self._stage_tiny()
        try:
            crng = random.Random(42)
            eng1, eng2 = mem.MemoryEngine(), mem.MemoryEngine()
            try:
                count = eng1.seed_dtd_lexikon(str(proj))
                lex = eng2.get_lexikon(str(proj))
            finally:
                eng1.close()
                eng2.close()
            terms = lex
            # rareattr: df==1, owner doc -> seeded; element context lives
            # in the definition, not the aliases, so T1/T10 queries that
            # contain element names can never trigger the expansion. CDATA
            # (the majority type) is deliberately not added to the
            # definition (measured: it pollutes the expansion, TODO-33).
            self.assertIn("rareattr", terms)
            self.assertEqual(terms["rareattr"]["aliases"], [])
            self.assertEqual(terms["rareattr"]["definition"], "doc")
            # uniquebody: df==1, root doc -> seeded
            self.assertIn("uniquebody", terms)
            self.assertEqual(terms["uniquebody"]["aliases"], [])
            self.assertEqual(terms["uniquebody"]["definition"], "doc")
            # commonattr: df==1, owner doc -> seeded
            self.assertIn("commonattr", terms)
            self.assertEqual(terms["commonattr"]["aliases"], [])
            self.assertEqual(terms["commonattr"]["definition"], "doc")
            self.assertGreaterEqual(count, 3)
        finally:
            tmp.cleanup()

    def test_expansion_resolves_seeded_term(self):
        tmp, proj = self._stage_tiny()
        try:
            crng = random.Random(42)
            seeder = mem.MemoryEngine()
            try:
                seeder.seed_dtd_lexikon(str(proj))
            finally:
                seeder.close()
            eng = mem.MemoryEngine()
            expanded = eng.lexikon_expansion(str(proj), "rareattr")
            self.assertIn("doc", expanded)
            # A T1-style query (element name) must NOT expand: it never
            # matches a seeded term, so it cannot be polluted.
            self.assertEqual(eng.lexikon_expansion(str(proj), "doc"), [])
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
            eng1, eng2 = mem.MemoryEngine(), mem.MemoryEngine()
            try:
                eng1.seed_dtd_lexikon(str(proj))
                lex = eng2.get_lexikon(str(proj))
            finally:
                eng1.close()
                eng2.close()
            terms = lex
            # dupattr appears in two files -> df==2 -> not seeded
            self.assertNotIn("dupattr", terms)
        finally:
            tmp.cleanup()

    def test_seeding_ignores_noise_dirs(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            proj = Path(tmp.name) / "bench-noise"
            d = proj / "directives"
            (d / "node_modules").mkdir(parents=True)
            (d / "node_modules" / "vend.dtd").write_text(
                "<!ELEMENT vendored EMPTY>\n<!ATTLIST vendored noiseattr CDATA #IMPLIED>\n",
                encoding="utf-8",
            )
            (d / "own.dtd").write_text(
                "<!ELEMENT owned EMPTY>\n<!ATTLIST owned ownattr CDATA #IMPLIED>\n",
                encoding="utf-8",
            )
            mem.PROJECT_ROOTS = [proj.parent]
            mem.PROJECTS_DIR = proj.parent
            eng = mem.MemoryEngine()
            try:
                eng.seed_dtd_lexikon(str(proj))
                lex = eng.get_lexikon(str(proj))
            finally:
                eng.close()
            self.assertIn("ownattr", lex)
            self.assertNotIn("noiseattr", lex)
        finally:
            tmp.cleanup()


class TestGlossaryDtdEscaping(unittest.TestCase):
    def test_special_chars_are_escaped_in_attributes(self):
        engine = mem.MemoryEngine()
        try:
            with tempfile.TemporaryDirectory() as d:
                terms = {
                    'a"b&c<d>': {
                        "term": 'a"b&c<d>',
                        "aliases": ['x"y'],
                        "definition": "e&f",
                        "source": "hand",
                        "updated": "2026-11-09",
                    }
                }
                path = engine._write_glossary_dtd(Path(d), terms)
                self.assertIsNotNone(path)
                assert path is not None
                text = path.read_text(encoding="utf-8")
                self.assertNotIn('a"b&c<d>', text)
                self.assertIn("&amp;", text)
                self.assertIn("&lt;", text)
                self.assertIn("&gt;", text)
        finally:
            engine.close()


if __name__ == "__main__":
    unittest.main()
