# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Tool-surface tests for the MCP server (guards, errors, isolation)."""

import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.absolute()))

import memory_engine
from memory_engine import MemoryEngine
import memory_mcp_server as mcp_server


class TestMcpServerTools(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.test_projects = self.test_dir / "projects"
        self.test_db = self.test_dir / "db"
        memory_engine.PROJECTS_DIR = self.test_projects
        memory_engine.PROJECT_ROOTS = [self.test_projects]
        memory_engine.DB_DIR = self.test_db
        memory_engine.REGISTRY_FILE = self.test_dir / "registry.json"
        memory_engine.EXTRA_ROOTS_FILE = self.test_dir / "extra_roots.json"
        memory_engine.LEXIKON_GLOBAL_FILE = self.test_dir / "lexikon_global.json"
        (self.test_projects / "raceproj" / "directives").mkdir(parents=True)
        self._old_engine = mcp_server.engine
        self.engine = MemoryEngine()
        mcp_server.engine = self.engine

    def tearDown(self):
        import shutil

        try:
            self.engine.close()
        finally:
            mcp_server.engine = self._old_engine
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_inbox_concurrent_appends_keep_everything(self):
        n, errs = 24, []
        pad = "x" * 2048

        def worker(i):
            try:
                mcp_server.memory_inbox_write("raceproj", f"BLOCK-{i:02d} {pad}")
            except Exception as e:  # noqa: BLE001
                errs.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errs, [])
        text = (
            self.test_projects / "raceproj" / "directives" / "wiki_inbox.md"
        ).read_text(encoding="utf-8")
        missing = [i for i in range(n) if f"BLOCK-{i:02d}" not in text]
        self.assertEqual(missing, [])

    def test_write_refuses_path_traversal(self):
        panel = mcp_server.memory_write("raceproj", "../../escape.md", "evil")
        self.assertIn("Refusing", panel)
        self.assertFalse((self.test_projects / "escape.md").exists())
        panel2 = mcp_server.memory_write("raceproj", "/abs/escape.md", "evil")
        self.assertIn("Refusing", panel2)

    def test_delete_refuses_when_read_only(self):
        victim = self.test_projects / "raceproj" / "directives" / "victim.md"
        victim.write_text("# Victim\n", encoding="utf-8")
        old = mcp_server.engine
        reader = MemoryEngine()
        try:
            self.assertTrue(reader.read_only)
            mcp_server.engine = reader
            panel = mcp_server.memory_delete(str(victim))
        finally:
            mcp_server.engine = old
            reader.close()
        self.assertIn("lock", panel.lower())
        self.assertTrue(victim.exists())

    def test_delete_refuses_unindexed_path(self):
        stray = self.test_projects / "raceproj" / "directives" / "stray.md"
        stray.write_text("# Stray\n", encoding="utf-8")
        panel = mcp_server.memory_delete(str(stray))
        self.assertIn("not indexed", panel)
        self.assertTrue(stray.exists())

    def test_delete_removes_indexed_file(self):
        target = self.test_projects / "raceproj" / "directives" / "doomed.md"
        target.write_text("# Doomed\n\nSome content here.", encoding="utf-8")

        class FakeModel:
            def embed(self, texts):
                return [[0.0] * 4 for _ in texts]

        with patch.dict(
            os.environ, {"OPENCODE_MEMORY_EMBED_MODELS": "BAAI/bge-base-en-v1.5"}
        ):
            self.engine._models = {"baai_bge_base_en_v1_5": FakeModel()}
            self.engine.index_all()
        panel = mcp_server.memory_delete(str(target))
        self.assertIn("Memory Deleted", panel)
        self.assertFalse(target.exists())
        self.assertNotIn(str(target), self.engine.load_registry())

    def test_organize_refuses_when_read_only(self):
        inbox = self.test_projects / "raceproj" / "directives" / "wiki_inbox.md"
        inbox.write_text(
            "# Wiki Inbox\n\n## Topic One\n\nSome body text here.\n",
            encoding="utf-8",
        )
        old = mcp_server.engine
        reader = MemoryEngine()
        try:
            self.assertTrue(reader.read_only)
            mcp_server.engine = reader
            panel = mcp_server.memory_organize("raceproj")
        finally:
            mcp_server.engine = old
            reader.close()
        self.assertIn("refus", panel.lower())
        self.assertFalse(
            (self.test_projects / "raceproj" / "directives" / "wiki_concepts").exists()
        )

    def test_write_refuses_when_read_only(self):
        old = mcp_server.engine
        reader = MemoryEngine()
        try:
            self.assertTrue(reader.read_only)
            mcp_server.engine = reader
            panel = mcp_server.memory_write("raceproj", "locked_note.md", "hello")
        finally:
            mcp_server.engine = old
            reader.close()
        self.assertIn("refus", panel.lower())
        self.assertFalse(
            (
                self.test_projects
                / "raceproj"
                / "directives"
                / "wiki_concepts"
                / "locked_note.md"
            ).exists()
        )

    def test_session_commit_refusal_renders_error(self):
        old = mcp_server.engine
        reader = MemoryEngine()
        try:
            self.assertTrue(reader.read_only)
            mcp_server.engine = reader
            panel = mcp_server.memory_session_commit("raceproj")
        finally:
            mcp_server.engine = old
            reader.close()
        self.assertIn("Refus", panel)

    def test_organize_preserves_skipped_sections(self):
        inbox = self.test_projects / "raceproj" / "directives" / "wiki_inbox.md"
        inbox.write_text(
            "# Wiki Inbox\n\n## Good Topic\n\nSome body text here.\n\n## EmptyTitle\n",
            encoding="utf-8",
        )
        panel = mcp_server.memory_organize("raceproj")
        self.assertIn("Filed concepts (1)", panel)
        self.assertIn("kept", panel)
        rest = inbox.read_text(encoding="utf-8")
        self.assertIn("EmptyTitle", rest)

    def test_explain_panel_shows_actual_weights(self):
        canned = [
            {
                "rel_path": "p/d.md",
                "title": "T",
                "dense": 0.9,
                "bm25": 0.8,
                "recency": 0.5,
                "importance": 0.5,
                "final": 0.7,
                "weights": {
                    "dense": 0.15,
                    "bm25": 0.60,
                    "recency": 0.15,
                    "importance": 0.10,
                },
            }
        ]

        class StubEngine:
            def explain_search(self, query, k=3, project=None):
                return canned

        old = mcp_server.engine
        mcp_server.engine = StubEngine()
        try:
            panel = mcp_server.memory_explain_search("q")
        finally:
            mcp_server.engine = old
        self.assertIn("x0.60", panel)
        self.assertIn("x0.15", panel)
        self.assertNotIn("x0.45", panel)

    def test_server_file_io_pins_utf8(self):
        # This box runs UTF-8 mode, so a locale crash cannot show here;
        # pin the contract instead: every server file read/write names
        # encoding="utf-8" (stock Windows py3.10-3.14 defaults to cp1252).
        seen = []
        real_read = Path.read_text
        real_write = Path.write_text

        def spy_read(self, *a, **k):
            seen.append(("read", k.get("encoding")))
            return real_read(self, *a, **k)

        def spy_write(self, *a, **k):
            seen.append(("write", k.get("encoding")))
            return real_write(self, *a, **k)

        with patch.object(Path, "read_text", spy_read):
            with patch.object(Path, "write_text", spy_write):
                mcp_server.memory_inbox_write("raceproj", "héllo 🌱")
                mcp_server.memory_inbox_read("raceproj")
                mcp_server.memory_discover("raceproj")
        self.assertTrue(seen)
        for kind, enc in seen:
            self.assertEqual(enc, "utf-8", kind)

    def test_symbiose_poll_failure_renders_panel(self):
        with patch.object(
            mcp_server, "_symbiose_for", side_effect=RuntimeError("worker boom")
        ):
            panel = mcp_server.memory_symbiose_poll("raceproj", 1)
        self.assertIn("Failure", panel)

    def _real_worker(self, trigger=100, target=50):
        from symbiose_worker import SymbioseWorker

        return SymbioseWorker(
            lambda spans: "ok",
            config={
                "trigger_tokens": trigger,
                "target_tokens": target,
                "max_keep_messages": 200,
            },
        )

    def _write_sidecar(self, name, messages):
        import json

        mem = self.test_projects / "raceproj" / ".opencode" / "memory"
        mem.mkdir(parents=True, exist_ok=True)
        path = mem / name
        path.write_text(
            json.dumps(
                {
                    "digest": "t",
                    "ts": "2026-11-09T00:00:00Z",
                    "messages": messages,
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_poll_drains_backlog_before_polling(self):
        mem = self.test_projects / "raceproj" / ".opencode" / "memory"
        sidecar = self._write_sidecar(
            "rtrre-aa.submit.json", [{"role": "user", "text": "hi"}]
        )
        worker = self._real_worker()
        try:
            with patch.object(mcp_server, "_symbiose_for", return_value=worker):
                panel = mcp_server.memory_symbiose_poll("raceproj", 1)
        finally:
            worker.close()
        self.assertIn("Drain: 1 consumed, 0 left, 0 quarantined", panel)
        self.assertIn("rtrre-aa.submit.json", panel)
        self.assertIn("status: ready", panel)
        self.assertFalse(sidecar.exists())
        self.assertFalse((mem / "rtrre-aa.submit.json").exists())

    def test_poll_piggyback_drains_deep_backlog(self):
        # RRD-107: relay-ack makes per-sidecar drain ~free, so the poll
        # piggyback sweeps 25 per poll instead of 2.
        mem = self.test_projects / "raceproj" / ".opencode" / "memory"
        for i in range(5):
            name = f"rtrre-p{i:02d}.submit.json"
            self._write_sidecar(name, [{"role": "user", "text": "hi"}])
            (mem / name.replace(".submit.json", ".dtd")).write_text(
                '<span id="span-0">\nhi\n', encoding="utf-8"
            )
        worker = self._real_worker()
        try:
            with patch.object(mcp_server, "_symbiose_for", return_value=worker):
                panel = mcp_server.memory_symbiose_poll("raceproj", 1)
        finally:
            worker.close()
        self.assertIn("Drain: 5 consumed, 0 left, 0 quarantined", panel)

    def test_poll_survives_drain_failure(self):
        worker = self._real_worker()
        try:
            with (
                patch.object(mcp_server, "_symbiose_for", return_value=worker),
                patch.object(
                    mcp_server.sw,
                    "drain_submit_sidecars",
                    side_effect=RuntimeError("drain boom"),
                ),
            ):
                panel = mcp_server.memory_symbiose_poll("raceproj", 1)
        finally:
            worker.close()
        self.assertIn("status: unknown", panel)
        self.assertIn("Drain error: drain boom", panel)

    def test_drain_tool_consumes_and_reports(self):
        first = self._write_sidecar(
            "rtrre-aa.submit.json", [{"role": "user", "text": "hi"}]
        )
        second = self._write_sidecar(
            "rtrre-bb.submit.json", [{"role": "user", "text": "yo"}]
        )
        worker = self._real_worker()
        try:
            with patch.object(mcp_server, "_symbiose_for", return_value=worker):
                panel = mcp_server.memory_symbiose_drain("raceproj")
        finally:
            worker.close()
        self.assertIn("Drain: 2 consumed, 0 left, 0 quarantined", panel)
        self.assertIn("rtrre-aa.submit.json", panel)
        self.assertIn("rtrre-bb.submit.json", panel)
        self.assertIn("memory_index", panel)
        self.assertFalse(first.exists())
        self.assertFalse(second.exists())

    def test_drain_panel_caps_long_lists(self):
        for i in range(12):
            self._write_sidecar(
                f"rtrre-{i:02d}.submit.json", [{"role": "user", "text": "hi"}]
            )
        worker = self._real_worker()
        try:
            with patch.object(mcp_server, "_symbiose_for", return_value=worker):
                panel = mcp_server.memory_symbiose_drain("raceproj", limit=1)
        finally:
            worker.close()
        self.assertIn("Drain: 1 consumed, 11 left, 0 quarantined", panel)
        self.assertIn("+1 more", panel)

    def test_compress_tool_fires_with_target_override(self):
        import json

        worker = self._real_worker(trigger=100, target=5000)
        try:
            with patch.object(mcp_server, "_symbiose_for", return_value=worker):
                panel = mcp_server.memory_symbiose_compress(
                    "raceproj", json.dumps([{"role": "user", "text": "hi"}]), 50
                )
            self.assertIn("Target: 50", panel)
            self.assertIn("Status: pending", panel)
            self.assertEqual(worker.poll(1)["plan_overrides"], {"target_tokens": 50})
        finally:
            worker.close()

    def test_compress_tool_refuses_bad_target_and_json(self):
        worker = self._real_worker(trigger=100, target=5000)
        try:
            with patch.object(mcp_server, "_symbiose_for", return_value=worker):
                panel = mcp_server.memory_symbiose_compress(
                    "raceproj", '[{"role": "user", "text": "hi"}]', 500
                )
            self.assertIn("Refused", panel)
            self.assertIn("below trigger", panel)
            with patch.object(mcp_server, "_symbiose_for", return_value=worker):
                panel = mcp_server.memory_symbiose_compress("raceproj", "{not json", 50)
            self.assertIn("Refused", panel)
            self.assertIn("not valid JSON", panel)
        finally:
            worker.close()


class TestErrorText(unittest.TestCase):
    def test_bare_exceptions_render_non_blank(self):
        # Live incident 2026-11-10: MemoryError stringifies empty and the
        # Indexing Failure panel rendered a blank 'Error: '.
        self.assertEqual(mcp_server._error_text(MemoryError()), "MemoryError()")
        self.assertEqual(mcp_server._error_text(ValueError("bad")), "bad")


class TestAutoindexSwitch(unittest.TestCase):
    def test_switch_defaults_on_explicit_off(self):
        import span_indexer

        self.assertTrue(span_indexer.autoindex_enabled({}))
        self.assertFalse(
            span_indexer.autoindex_enabled({"OPENCODE_MEMORY_AUTOINDEX": "0"})
        )
        self.assertFalse(
            span_indexer.autoindex_enabled({"OPENCODE_MEMORY_AUTOINDEX": "off"})
        )

    def test_interval_defaults_and_guards(self):
        import span_indexer

        self.assertEqual(span_indexer.autoindex_interval({}), 30.0)
        self.assertEqual(
            span_indexer.autoindex_interval(
                {"OPENCODE_MEMORY_AUTOINDEX_INTERVAL": "5"}
            ),
            5.0,
        )
        self.assertEqual(
            span_indexer.autoindex_interval(
                {"OPENCODE_MEMORY_AUTOINDEX_INTERVAL": "junk"}
            ),
            30.0,
        )


if __name__ == "__main__":
    unittest.main()
