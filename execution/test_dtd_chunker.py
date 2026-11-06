"""DTD-aware chunking tests (TODO-30/32 amplification).

Hybrid contract: files with up to OPENCODE_MEMORY_DTD_PER_DECLARATION_MAX
declarations (default 300) get one atomic chunk per declaration; files
above the threshold get consecutive declarations grouped into chunks
bounded by OPENCODE_MEMORY_DTD_CHUNK_TOKENS (default 512). Declaration
boundaries are always respected; quoted '>' inside entity values never
splits a declaration.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from execution.memory_engine import MemoryEngine, _scan_dtd_declarations

SAMPLE_DTD = """<!-- sample DTD -->
<!ELEMENT book (title, chapter+)>
<!ATTLIST book id ID #REQUIRED lang CDATA "en">
<!ENTITY copyright "Copyright 2026">
<!ENTITY % xhtml.list "ul | ol | dl">
<!NOTATION gif SYSTEM "image/gif">
"""

ENTITY_WITH_GT = """<!ENTITY weird "a > b < c">
<!ELEMENT root (a|b)>
"""

BIG_FILE = "".join(
    f"<!ELEMENT elem{i:04d} (alpha, beta, gamma, delta, epsilon, zeta, eta, theta, iota, kappa)>\n"
    for i in range(500)
)


class ScanDtdDeclarationsTests(unittest.TestCase):
    def test_scan_finds_all_kinds(self):
        kinds = [k for k, _n, _d in _scan_dtd_declarations(SAMPLE_DTD)]
        self.assertEqual(kinds, ["ELEMENT", "ATTLIST", "ENTITY", "ENTITY", "NOTATION"])

    def test_scan_extracts_names(self):
        names = [n for _k, n, _d in _scan_dtd_declarations(SAMPLE_DTD)]
        self.assertEqual(names, ["book", "book", "copyright", "xhtml.list", "gif"])

    def test_scan_quoted_gt_does_not_split(self):
        decls = list(_scan_dtd_declarations(ENTITY_WITH_GT))
        self.assertEqual(len(decls), 2)
        self.assertEqual(decls[0][0], "ENTITY")
        self.assertIn("a > b < c", decls[0][2])

    def test_scan_empty_content(self):
        self.assertEqual(list(_scan_dtd_declarations("")), [])


class ChunkDtdTests(unittest.TestCase):
    def setUp(self):
        self.engine = MemoryEngine()
        self.tmp = Path(__file__).parent / "_dtd_chunk_sample.dtd"

    def tearDown(self):
        self.tmp.unlink(missing_ok=True)
        self.engine.close()

    def _write(self, content: str) -> Path:
        self.tmp.write_text(content, encoding="utf-8", newline="\n")
        return self.tmp

    def test_small_file_one_chunk_per_declaration(self):
        f = self._write(SAMPLE_DTD)
        chunks = self.engine.chunk_dtd(f, "sample.dtd")
        self.assertEqual(len(chunks), 5)
        self.assertEqual(
            [c["title"] for c in chunks],
            [
                "ELEMENT: book",
                "ATTLIST: book",
                "ENTITY: copyright",
                "ENTITY: xhtml.list",
                "NOTATION: gif",
            ],
        )

    def test_chunk_ids_stable(self):
        f = self._write(SAMPLE_DTD)
        chunks = self.engine.chunk_dtd(f, "sample.dtd")
        self.assertEqual(
            [c["chunk_id"] for c in chunks],
            [
                "sample.dtd#chunk_0",
                "sample.dtd#chunk_1",
                "sample.dtd#chunk_2",
                "sample.dtd#chunk_3",
                "sample.dtd#chunk_4",
            ],
        )

    def test_quoted_gt_stays_in_one_chunk(self):
        f = self._write(ENTITY_WITH_GT)
        chunks = self.engine.chunk_dtd(f, "gt.dtd")
        self.assertEqual(len(chunks), 2)
        self.assertIn("a > b < c", chunks[0]["text"])

    def test_empty_file_returns_empty(self):
        f = self._write("")
        self.assertEqual(self.engine.chunk_dtd(f, "empty.dtd"), [])

    def test_big_file_groups_into_bounded_chunks(self):
        f = self._write(BIG_FILE)
        chunks = self.engine.chunk_dtd(f, "big.dtd")
        self.assertGreater(len(chunks), 1)
        self.assertLess(len(chunks), 500)
        for c in chunks:
            tokens = len(c["raw_body"]) // 4
            self.assertLessEqual(tokens, 512 + 64)

    def test_chunk_boundaries_fall_between_declarations(self):
        f = self._write(BIG_FILE)
        chunks = self.engine.chunk_dtd(f, "big.dtd")
        for c in chunks:
            self.assertRegex(c["raw_body"].strip(), r"^<![A-Za-z]+ ")
            self.assertTrue(c["raw_body"].rstrip().endswith(">"))

    def test_env_budget_overrides_default(self):
        f = self._write(BIG_FILE)
        old = os.environ.get("OPENCODE_MEMORY_DTD_CHUNK_TOKENS")
        os.environ["OPENCODE_MEMORY_DTD_CHUNK_TOKENS"] = "64"
        try:
            chunks = self.engine.chunk_dtd(f, "big.dtd")
            for c in chunks:
                tokens = len(c["raw_body"]) // 4
                self.assertLessEqual(tokens, 64 + 64)
        finally:
            if old is None:
                os.environ.pop("OPENCODE_MEMORY_DTD_CHUNK_TOKENS", None)
            else:
                os.environ["OPENCODE_MEMORY_DTD_CHUNK_TOKENS"] = old

    def test_env_per_declaration_threshold_overrides_default(self):
        f = self._write(BIG_FILE)
        old = os.environ.get("OPENCODE_MEMORY_DTD_PER_DECLARATION_MAX")
        os.environ["OPENCODE_MEMORY_DTD_PER_DECLARATION_MAX"] = "1000"
        try:
            chunks = self.engine.chunk_dtd(f, "big.dtd")
            self.assertEqual(len(chunks), 500)
        finally:
            if old is None:
                os.environ.pop("OPENCODE_MEMORY_DTD_PER_DECLARATION_MAX", None)
            else:
                os.environ["OPENCODE_MEMORY_DTD_PER_DECLARATION_MAX"] = old


class ChunkDtdWholeTests(unittest.TestCase):
    def setUp(self):
        self.engine = MemoryEngine()
        self.tmp = Path(__file__).parent / "_dtd_whole_sample.dtd"

    def tearDown(self):
        self.tmp.unlink(missing_ok=True)
        self.engine.close()

    def _write(self, content: str) -> Path:
        self.tmp.write_text(content, encoding="utf-8", newline="\n")
        return self.tmp

    def test_one_chunk_per_file(self):
        f = self._write(SAMPLE_DTD)
        chunks = self.engine.chunk_dtd_whole(f, "sample.dtd")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["chunk_id"], "sample.dtd#chunk_0")

    def test_inventory_header_lists_kinds(self):
        f = self._write(SAMPLE_DTD)
        chunks = self.engine.chunk_dtd_whole(f, "sample.dtd")
        text = chunks[0]["text"]
        self.assertIn("ROOT: book", text)
        self.assertIn("ATTRIBUTES: book", text)
        self.assertIn("ENTITIES: copyright, xhtml.list", text)
        self.assertIn("NOTATIONS: gif", text)

    def test_no_element_list_in_header(self):
        f = self._write(SAMPLE_DTD)
        chunks = self.engine.chunk_dtd_whole(f, "sample.dtd")
        text = chunks[0]["text"]
        self.assertNotIn("ELEMENTS:", text)
        self.assertIn("<!ELEMENT book", text)

    def test_raw_content_follows_inventory(self):
        f = self._write(SAMPLE_DTD)
        chunks = self.engine.chunk_dtd_whole(f, "sample.dtd")
        self.assertIn("<!ELEMENT book", chunks[0]["text"])
        self.assertIn("<!NOTATION gif", chunks[0]["text"])

    def test_empty_file_returns_empty(self):
        f = self._write("")
        self.assertEqual(self.engine.chunk_dtd_whole(f, "empty.dtd"), [])


if __name__ == "__main__":
    unittest.main()
