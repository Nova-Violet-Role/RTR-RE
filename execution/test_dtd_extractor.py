# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Acceptance: the DTD structural feature extractor is deterministic, safe,
and reproduces known answers from the corpus."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "dtd_extractor", ROOT / "eval" / "dtd_extractor.py"
)
assert SPEC and SPEC.loader
ext = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ext
SPEC.loader.exec_module(ext)

DTD_FAMILY = Path(r"C:\DTD_FAMILY\.dtd-file-examples")


def write_tmp(text: str) -> Path:
    f = Path(tempfile.mkdtemp()) / "sample.dtd"
    f.write_text(text, encoding="utf-8", newline="\n")
    return f


class TestDTDExtractorKnownAnswers(unittest.TestCase):
    def test_dtbook_sample_matches_catalogue_counts(self):
        p = DTD_FAMILY / "daisy" / "dtbook-2005-2.dtd"
        if not p.exists():
            self.skipTest("daisy dtbook sample absent")
        prof = ext.extract_dtd_profile(p)
        self.assertEqual(prof.elements, 82)
        self.assertEqual(prof.attr_decls, 82)
        self.assertEqual(prof.attributes, 36)
        self.assertGreaterEqual(prof.param_entities, 50)

    def test_datatypes_entity_count(self):
        p = DTD_FAMILY / "datatypes.dtd"
        if not p.exists():
            self.skipTest("datatypes.dtd absent")
        prof = ext.extract_dtd_profile(p)
        self.assertEqual(prof.elements, 16)
        self.assertGreaterEqual(prof.param_entities, 50)

    def test_corpus_extraction_full_scope(self):
        if not DTD_FAMILY.exists():
            self.skipTest("DTD family source absent")
        profiles = ext.extract_corpus(DTD_FAMILY)
        self.assertGreaterEqual(len(profiles), 768)
        self.assertTrue(all(p.elements >= 0 for p in profiles))


class TestDTDExtractorDeterminism(unittest.TestCase):
    def test_same_input_same_output(self):
        text = '<!ELEMENT root (a, b*)>\n<!ATTLIST root id ID #REQUIRED>\n<!ENTITY amp "&">\n'
        p1 = write_tmp(text)
        p2 = write_tmp(text)
        a = ext.extract_dtd_profile(p1).to_dict()
        b = ext.extract_dtd_profile(p2).to_dict()
        a.pop("path")
        b.pop("path")
        self.assertEqual(a, b)
        self.assertEqual(a["elements"], 1)
        self.assertEqual(a["attributes"], 1)
        self.assertEqual(a["entities"], 1)
        self.assertEqual(a["content_models"]["sequences"], 1)
        self.assertEqual(a["content_models"]["repetitions"], 1)


class TestDTDExtractorSafety(unittest.TestCase):
    def test_parameter_entity_reported_as_data_never_expanded(self):
        hostile = (
            '<!ENTITY % inject "<!ELEMENT injected EMPTY>">\n<!ELEMENT safe EMPTY>\n'
        )
        p = write_tmp(hostile)
        prof = ext.extract_dtd_profile(p)
        self.assertEqual(prof.param_entities, 1)
        self.assertIn("inject", prof.param_entity_names)
        self.assertEqual(prof.elements, 1)
        self.assertNotIn("injected", prof.element_names)

    def test_parameter_entity_internal_subset_never_expanded(self):
        hostile = (
            "<!ENTITY % evil [ <!ELEMENT injected EMPTY> ]>\n"
            "<!ENTITY % worse [ <!ATTLIST injected id ID #REQUIRED> ]>\n"
            "<!ELEMENT safe EMPTY>\n"
        )
        p = write_tmp(hostile)
        prof = ext.extract_dtd_profile(p)
        self.assertEqual(prof.elements, 1)
        self.assertNotIn("injected", prof.element_names)
        self.assertEqual(prof.attributes, 0)
        self.assertNotIn("injected", prof.attribute_names)
        self.assertIn("evil", prof.param_entity_names)
        self.assertIn("worse", prof.param_entity_names)

    def test_parameter_entity_injecting_entity_declaration_never_expanded(self):
        hostile = "<!ENTITY % evil \"<!ENTITY injected 'x'>\">\n<!ELEMENT safe EMPTY>\n"
        p = write_tmp(hostile)
        prof = ext.extract_dtd_profile(p)
        self.assertNotIn("injected", prof.entity_names)
        self.assertIn("evil", prof.param_entity_names)

    def test_parameter_entity_injecting_notation_never_expanded(self):
        hostile = (
            "<!ENTITY % evil \"<!NOTATION injected SYSTEM 'image/x'>\">\n"
            "<!ELEMENT safe EMPTY>\n"
        )
        p = write_tmp(hostile)
        prof = ext.extract_dtd_profile(p)
        self.assertNotIn("injected", prof.notation_names)

    def test_malformed_dtd_does_not_crash(self):
        broken = "<!ELEMENT unclosed (a, b>\n<!ATTLIST broken\n<!ENTITY\n"
        p = write_tmp(broken)
        prof = ext.extract_dtd_profile(p)
        self.assertIsInstance(prof.elements, int)
        self.assertIsInstance(prof.attributes, int)

    def test_empty_file(self):
        p = write_tmp("")
        prof = ext.extract_dtd_profile(p)
        self.assertEqual(prof.elements, 0)
        self.assertEqual(prof.attributes, 0)
        self.assertEqual(prof.entities, 0)
        self.assertEqual(prof.param_entities, 0)


class TestDTDExtractorFamilySignatures(unittest.TestCase):
    """TODO-64 assimilation: lineage, role, module switches mirror the engine."""

    CUSTOMIZED_DRIVER = """<!ENTITY % sect3.module "IGNORE">
<!ENTITY % sect4.module "IGNORE">
<!ENTITY % DocBookDTD PUBLIC "-//OASIS//DTD DocBook V3.1//EN">
%DocBookDTD;
<!ELEMENT Sect3 - O (Sect3Info?, (%sect.title.content;))>
"""

    PURE_MODULE = """<!ELEMENT title (#PCDATA)>
<!ELEMENT para (#PCDATA)>
<!ATTLIST para id ID #IMPLIED>
"""

    HOSTILE = """<!ENTITY % evil "<!ENTITY % fake PUBLIC '-//EVIL//DTD Injected//EN' 'evil.dtd'>">
<!ELEMENT safe EMPTY>
"""

    def test_public_lineage_extracts_owner_family_version(self):
        p = write_tmp(self.CUSTOMIZED_DRIVER)
        prof = ext.extract_dtd_profile(p)
        self.assertEqual(len(prof.lineage), 1)
        entry = prof.lineage[0]
        self.assertEqual(entry["name"], "DocBookDTD")
        self.assertEqual(entry["public_id"], "-//OASIS//DTD DocBook V3.1//EN")
        self.assertEqual(entry["owner"], "OASIS")
        self.assertEqual(entry["keyword"], "DTD DocBook V3.1")

    def test_switches_and_role_driver(self):
        p = write_tmp(self.CUSTOMIZED_DRIVER)
        prof = ext.extract_dtd_profile(p)
        self.assertEqual(prof.role, "driver")
        self.assertEqual(
            [s["name"] for s in prof.module_switches],
            ["sect3.module", "sect4.module"],
        )
        self.assertTrue(all(s["value"] == "IGNORE" for s in prof.module_switches))

    def test_pure_module_role(self):
        p = write_tmp(self.PURE_MODULE)
        prof = ext.extract_dtd_profile(p)
        self.assertEqual(prof.role, "module")
        self.assertEqual(prof.lineage, [])
        self.assertEqual(prof.module_switches, [])

    def test_hostile_body_never_surfaces_as_lineage(self):
        p = write_tmp(self.HOSTILE)
        prof = ext.extract_dtd_profile(p)
        self.assertEqual(prof.lineage, [])
        self.assertEqual(prof.role, "module")
        self.assertNotIn("EVIL", [e["name"] for e in prof.lineage])

    def test_to_dict_carries_family_signatures(self):
        p = write_tmp(self.CUSTOMIZED_DRIVER)
        d = ext.extract_dtd_profile(p).to_dict()
        self.assertEqual(d["role"], "driver")
        self.assertGreaterEqual(len(d["lineage"]), 1)
        self.assertGreaterEqual(len(d["module_switches"]), 1)


class TestDTDExtractorStructural(unittest.TestCase):
    def test_content_model_shape_detection(self):
        cm = ext.content_model_shape("(a, b | c)*")
        self.assertTrue(cm.has_sequence)
        self.assertTrue(cm.has_choice)
        self.assertTrue(cm.has_repetition)

    def test_nesting_depth(self):
        cm = ext.content_model_shape("((a, b), c)")
        self.assertGreaterEqual(cm.max_nesting, 1)

    def test_attr_decl_vs_attr_items(self):
        text = "<!ATTLIST root a CDATA #IMPLIED b ID #REQUIRED>\n"
        p = write_tmp(text)
        prof = ext.extract_dtd_profile(p)
        self.assertEqual(prof.attr_decls, 1)
        self.assertEqual(prof.attributes, 2)

    def test_attribute_types_extracted(self):
        text = '<!ATTLIST root a CDATA #IMPLIED b ID #REQUIRED c (one|two) "one">\n'
        p = write_tmp(text)
        prof = ext.extract_dtd_profile(p)
        self.assertEqual(prof.attribute_types.get("a"), "CDATA")
        self.assertEqual(prof.attribute_types.get("b"), "ID")
        self.assertEqual(prof.attribute_types.get("c"), "(one|two)")

    def test_content_model_fragments_extracted(self):
        text = (
            "<!ELEMENT book (title, author*)>\n"
            "<!ELEMENT title (#PCDATA)>\n"
            "<!ELEMENT author (first | last)>\n"
        )
        p = write_tmp(text)
        prof = ext.extract_dtd_profile(p)
        self.assertIn("(title, author*)", prof.content_model_fragments)
        self.assertIn("(#PCDATA)", prof.content_model_fragments)
        self.assertIn("(first | last)", prof.content_model_fragments)

    def test_content_model_fragments_deduplicated_and_capped(self):
        text = (
            "<!ELEMENT a (x, y, z)>\n<!ELEMENT b (x, y, z)>\n<!ELEMENT c (x, y, z)>\n"
        )
        p = write_tmp(text)
        prof = ext.extract_dtd_profile(p)
        self.assertEqual(prof.content_model_fragments.count("(x, y, z)"), 1)


if __name__ == "__main__":
    unittest.main()
