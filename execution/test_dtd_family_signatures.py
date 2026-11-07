"""DTD family-signature tests (TODO-64 assimilation, proposals A-C).

Family signatures are the discriminator dense retrieval lacks: two
families that share element vocabulary (measured T10 collapse: DITA vs
DocBook `appendix`) are separated by their lineage (PUBLIC/SYSTEM
external references), their driver/module role, and their customization
switches (%xxx.module "IGNORE"/"INCLUDE"). Sources of truth for the
shapes under test are the DocBook Definitive Guide examples
(remv.sect4.dtd, add.sect6.dtd) and the DocBook 4.5 driver/module
split.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Add execution directory to sys.path (house convention, see test_memory.py)
sys.path.insert(0, str(Path(__file__).parent.absolute()))

from memory_engine import (  # noqa: E402
    MemoryEngine,
    _dtd_lineage,
    _dtd_module_switches,
    _dtd_role,
    _scan_dtd_declarations,
)

# defguide examples/remv.sect4.dtd shape: module switches + PUBLIC lineage.
CUSTOMIZED_DRIVER = """<!ENTITY % sect3.module "IGNORE">
<!ENTITY % sect4.module "IGNORE">
<!ENTITY % sect5.module "IGNORE">
<!ENTITY % DocBookDTD PUBLIC "-//OASIS//DTD DocBook V3.1//EN">
%DocBookDTD;
<!ENTITY % local.sect3.attrib "">
<!ELEMENT Sect3 - O (Sect3Info?, (%sect.title.content;))>
"""

# A pure module: declarations only, no switches, no external refs.
PURE_MODULE = """<!ELEMENT title (#PCDATA)>
<!ELEMENT para (#PCDATA)>
<!ATTLIST para id ID #IMPLIED>
"""

# SYSTEM-form external reference.
SYSTEM_REF = """<!ENTITY % dbpool PUBLIC "-//OASIS//DTD DocBook CALS Table Model V4.5//EN" "calstblx.dtd">
<!ENTITY % dbhier SYSTEM "dbhierx.mod">
<!ELEMENT book (title)>
"""

# Hostile: an entity body containing a fake PUBLIC reference must not
# surface as lineage (LAW.AMP.13 — entity bodies are data).
HOSTILE = """<!ENTITY % evil "<!ENTITY % fake PUBLIC '-//EVIL//DTD Injected//EN' 'evil.dtd'>">
<!ELEMENT safe EMPTY>
"""


class DtdLineageTests(unittest.TestCase):
    def test_public_lineage_extracts_owner_family_version(self):
        decls = list(_scan_dtd_declarations(CUSTOMIZED_DRIVER))
        lineage = _dtd_lineage(decls)
        self.assertEqual(len(lineage), 1)
        entry = lineage[0]
        self.assertEqual(entry["name"], "DocBookDTD")
        self.assertEqual(entry["public_id"], "-//OASIS//DTD DocBook V3.1//EN")
        self.assertEqual(entry["owner"], "OASIS")
        self.assertEqual(entry["keyword"], "DTD DocBook V3.1")
        self.assertIsNone(entry["system_id"])

    def test_system_lineage_extracts_system_id(self):
        decls = list(_scan_dtd_declarations(SYSTEM_REF))
        lineage = _dtd_lineage(decls)
        self.assertEqual(len(lineage), 2)
        public = next(e for e in lineage if e["public_id"])
        system = next(e for e in lineage if not e["public_id"])
        self.assertEqual(public["owner"], "OASIS")
        self.assertEqual(system["name"], "dbhier")
        self.assertEqual(system["system_id"], "dbhierx.mod")

    def test_pure_module_has_no_lineage(self):
        decls = list(_scan_dtd_declarations(PURE_MODULE))
        self.assertEqual(_dtd_lineage(decls), [])

    def test_hostile_entity_body_never_surfaces_as_lineage(self):
        decls = list(_scan_dtd_declarations(HOSTILE))
        lineage = _dtd_lineage(decls)
        self.assertEqual(lineage, [])


class DtdModuleSwitchTests(unittest.TestCase):
    def test_ignored_switches_are_captured(self):
        decls = list(_scan_dtd_declarations(CUSTOMIZED_DRIVER))
        switches = _dtd_module_switches(decls)
        self.assertEqual(
            [s["name"] for s in switches],
            ["sect3.module", "sect4.module", "sect5.module"],
        )
        self.assertTrue(all(s["value"] == "IGNORE" for s in switches))

    def test_pure_module_has_no_switches(self):
        decls = list(_scan_dtd_declarations(PURE_MODULE))
        self.assertEqual(_dtd_module_switches(decls), [])

    def test_hostile_entity_body_switches_never_surface(self):
        hostile = (
            "<!ENTITY % evil \"<!ENTITY % fake.module 'IGNORE'>\">\n"
            "<!ELEMENT safe EMPTY>\n"
        )
        decls = list(_scan_dtd_declarations(hostile))
        self.assertEqual(_dtd_module_switches(decls), [])


class DtdRoleTests(unittest.TestCase):
    def test_driver_has_switches_or_external_refs(self):
        decls = list(_scan_dtd_declarations(CUSTOMIZED_DRIVER))
        self.assertEqual(_dtd_role(decls), "driver")
        decls2 = list(_scan_dtd_declarations(SYSTEM_REF))
        self.assertEqual(_dtd_role(decls2), "driver")

    def test_pure_module_is_module(self):
        decls = list(_scan_dtd_declarations(PURE_MODULE))
        self.assertEqual(_dtd_role(decls), "module")

    def test_hostile_body_does_not_change_role(self):
        decls = list(_scan_dtd_declarations(HOSTILE))
        self.assertEqual(_dtd_role(decls), "module")


class DtdWholeHeaderFamilySignatureTests(unittest.TestCase):
    def setUp(self):
        self.engine = MemoryEngine()
        self.tmp = Path(__file__).parent / "_dtd_family_sample.dtd"

    def tearDown(self):
        self.tmp.unlink(missing_ok=True)
        self.engine.close()

    def _write(self, content: str) -> Path:
        self.tmp.write_text(content, encoding="utf-8", newline="\n")
        return self.tmp

    def test_driver_header_carries_lineage_role_and_switches(self):
        f = self._write(CUSTOMIZED_DRIVER)
        chunks = self.engine.chunk_dtd_whole(f, "customized.dtd")
        text = chunks[0]["text"]
        self.assertIn("ROLE: driver", text)
        self.assertIn("LINEAGE: DocBookDTD", text)
        self.assertIn("OASIS", text)
        self.assertIn("MODULE SWITCHES: sect3.module=IGNORE", text)

    def test_module_header_carries_role_no_lineage(self):
        f = self._write(PURE_MODULE)
        chunks = self.engine.chunk_dtd_whole(f, "pure.mod")
        text = chunks[0]["text"]
        self.assertIn("ROLE: module", text)
        self.assertNotIn("LINEAGE:", text)
        self.assertNotIn("MODULE SWITCHES:", text)

    def test_hostile_header_carries_no_injected_lineage(self):
        f = self._write(HOSTILE)
        chunks = self.engine.chunk_dtd_whole(f, "hostile.dtd")
        text = chunks[0]["text"]
        header = text.split("Section: Full Document\n\n")[1].split("\n\n")[0]
        self.assertNotIn("EVIL", header)
        self.assertNotIn("injected", header)
        self.assertIn("ROOT: safe", header)
        self.assertNotIn("LINEAGE:", header)
        self.assertNotIn("MODULE SWITCHES:", header)


if __name__ == "__main__":
    unittest.main()
