# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Byte-exact verbatim: span bytes equal message bytes (masking aside).

Substring assertions prove presence; these prove identity. The span file
carries the message text byte-for-byte when no base64 run trips NDATA
masking; when masking trips, the blob is gone and [NDATA] stands in its
place; the Chroma chunk carries the full message contiguously (wrapping
is by design, fragmentation is not).
"""

import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))


def _span_text(body: str, idx: int = 0) -> str:
    m = re.search(rf'<span id="span-{idx}"[^>]*>\n(.*?)\n</span>', body, re.DOTALL)
    assert m, "span block not found"
    return m.group(1)


class TestVerbatim(unittest.TestCase):
    def test_span_bytes_equal_message_bytes(self):
        from symbiose_worker import SessionSpanSink, SymbioseWorker

        exact = "VERBATIM-EXACT-77Q pouch quokka router nocturnal dispatch seven"
        with tempfile.TemporaryDirectory() as td:
            memdir = Path(td) / "memory"
            memdir.mkdir()
            worker = SymbioseWorker(
                SessionSpanSink(memdir),
                config={
                    "trigger_tokens": 100,
                    "target_tokens": 50,
                    "max_keep_messages": 200,
                },
            )
            try:
                ticket = worker.submit(
                    [
                        {"role": "user", "text": exact},
                        {"role": "assistant", "text": "filler " * 300},
                        {"role": "user", "text": "latest"},
                    ]
                )
                done = worker.wait(ticket["id"], timeout=30)
            finally:
                worker.close()
            self.assertEqual(done["status"], "ready")
            spans = sorted(memdir.glob("rtrre-*.dtd"))
            spans = [p for p in spans if "summary" not in p.name]
            self.assertEqual(len(spans), 1)
            body = spans[0].read_text(encoding="utf-8")
            self.assertEqual(_span_text(body, 0), exact)

    def test_ndata_blob_masked_not_stored(self):
        from symbiose_worker import SessionSpanSink, SymbioseWorker

        blob = "QUJD" * 40
        with tempfile.TemporaryDirectory() as td:
            memdir = Path(td) / "memory"
            memdir.mkdir()
            worker = SymbioseWorker(
                SessionSpanSink(memdir),
                config={
                    "trigger_tokens": 100,
                    "target_tokens": 50,
                    "max_keep_messages": 200,
                },
            )
            try:
                ticket = worker.submit(
                    [
                        {"role": "user", "text": f"UNIQUE {blob} tail"},
                        {"role": "assistant", "text": "filler " * 300},
                        {"role": "user", "text": "latest"},
                    ]
                )
                done = worker.wait(ticket["id"], timeout=30)
            finally:
                worker.close()
            self.assertEqual(done["status"], "ready")
            spans = sorted(memdir.glob("rtrre-*.dtd"))
            spans = [p for p in spans if "summary" not in p.name]
            body = spans[0].read_text(encoding="utf-8")
            stored = _span_text(body, 0)
            self.assertNotIn(blob, stored)
            self.assertIn("[NDATA]", stored)
            self.assertTrue(stored.startswith("UNIQUE "))

    def test_chroma_chunk_carries_message_contiguously(self):
        import memory_engine
        from memory_engine import MemoryEngine

        exact = "VERBATIM-CHROMA-88Q badger arbiter midnight bridge ledger nine"
        with tempfile.TemporaryDirectory() as td:
            test_dir = Path(td)
            memory_engine.PROJECT_ROOTS = [test_dir / "projects"]
            memory_engine.PROJECTS_DIR = test_dir / "projects"
            memory_engine.DB_DIR = test_dir / "db"
            memory_engine.REGISTRY_FILE = test_dir / "registry.json"
            memory_engine.EXTRA_ROOTS_FILE = test_dir / "extra.json"
            memory_engine.LEXIKON_GLOBAL_FILE = test_dir / "lex.json"
            proj = test_dir / "projects" / "verbproj"
            memdir = proj / ".opencode" / "memory"
            memdir.mkdir(parents=True)
            (memdir / "rtrre-v.dtd").write_text(
                f"<!-- spans -->\n"
                f'<span id="span-0" role="user" lane="read" dtype="PCDATA">\n'
                f"{exact}\n"
                f"</span>\n",
                encoding="utf-8",
            )
            engine = MemoryEngine()
            try:
                stats = engine.index_all()
                self.assertGreaterEqual(stats["new"], 1)
                results = engine.search("badger arbiter midnight", project="verbproj")
            finally:
                engine.close()
            self.assertTrue(results)
            self.assertIn(exact, results[0]["document"])


if __name__ == "__main__":
    unittest.main()
