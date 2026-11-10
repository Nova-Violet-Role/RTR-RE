# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""MCP wrapper coverage: every untested tool's happy path plus the shared
refusal shape. Deep logic lives in the engine (covered); these pin the
resolve-call-panel wiring of each tool."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))

import memory_engine
from memory_engine import MemoryEngine
import memory_mcp_server as mcp_server


class TestMcpWrappers(unittest.TestCase):
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
        (self.test_projects / "wrapproj" / "directives").mkdir(parents=True)
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

    def test_discover_reports_convention(self):
        panel = mcp_server.memory_discover("wrapproj")
        self.assertIn("Discover: wrapproj", panel)
        self.assertIn("Convention variant:", panel)

    def test_inbox_read_empty_and_filled(self):
        panel = mcp_server.memory_inbox_read("wrapproj")
        self.assertIn("Inbox Empty", panel)
        mcp_server.memory_inbox_write("wrapproj", "WRAPMARKER learning block")
        panel2 = mcp_server.memory_inbox_read("wrapproj")
        self.assertIn("WRAPMARKER", panel2)

    def test_stats_reports_counts(self):
        panel = mcp_server.memory_stats()
        self.assertIn("Total Files Indexed:", panel)
        self.assertIn("Total Vector Chunks:", panel)

    def test_index_and_list_and_search_roundtrip(self):
        f = self.test_projects / "wrapproj" / "directives" / "wrap.md"
        f.write_text(
            "# Wrap\n\nquokka router nocturnal dispatch notes", encoding="utf-8"
        )
        panel = mcp_server.memory_index()
        self.assertIn("Incremental Indexing", panel)
        self.assertIn("Files Scanned:", panel)
        listed = mcp_server.memory_list("wrapproj")
        self.assertIn("Indexed Files List", listed)
        self.assertIn("wrap.md", listed)
        found = mcp_server.memory_search("quokka router", k=2, project="wrapproj")
        self.assertIn("Semantic Search Results", found)
        self.assertIn("quokka router", found)

    def test_init_project_bootstraps(self):
        panel = mcp_server.memory_init_project("freshproj")
        self.assertIn("Harness Bootstrapping", panel)
        self.assertTrue((self.test_projects / "freshproj" / "directives").exists())

    def test_consolidate_reports(self):
        (self.test_projects / "wrapproj" / "directives" / "wiki_concepts").mkdir(
            parents=True
        )
        panel = mcp_server.memory_consolidate("wrapproj")
        self.assertIn("Corpus Consolidation", panel)

    def test_session_start_restores(self):
        mcp_server.memory_init_project("wrapproj")
        panel = mcp_server.memory_session_start("wrapproj")
        self.assertIn("Session Start: wrapproj", panel)
        self.assertIn("Active Goals:", panel)

    def test_reflect_session_writes_report(self):
        panel = mcp_server.memory_reflect_session("wrapproj", "did the thing")
        self.assertIn("Session Reflection Logged", panel)
        reports = list(
            (self.test_projects / "wrapproj" / "directives" / "sessions").glob("*.md")
        )
        self.assertTrue(reports)

    def test_materialize_concepts_runs(self):
        panel = mcp_server.memory_materialize_concepts("wrapproj")
        self.assertIn("Concept Materialization", panel)

    def test_update_graph_runs(self):
        panel = mcp_server.memory_update_graph("wrapproj")
        self.assertIn("Bidirectional Graph Auto-Linker", panel)

    def test_reference_add_embeds(self):
        panel = mcp_server.memory_reference_add("wrapproj", "WRAPREF compact text here")
        self.assertIn("Memory Reference Added", panel)
        self.assertIn("Chunks added:", panel)

    def test_lexikon_add_show_build(self):
        added = mcp_server.memory_lexikon_add(
            "wrapproj", "wrapterm", "a wrap definition", "wrapsyn"
        )
        self.assertIn("Lexikon Updated", added)
        shown = mcp_server.memory_lexikon_show("wrapproj")
        self.assertIn("wrapterm", shown)
        built = mcp_server.memory_lexikon_build("wrapproj")
        self.assertIn("Lexikon Built", built)

    def test_janitor_reports(self):
        panel = mcp_server.memory_janitor(dry_run=True)
        self.assertIn("Janitor", panel)
        self.assertIn("Total chunks freed:", panel)

    def test_symbiose_submit_tickets(self):
        panel = mcp_server.memory_symbiose_submit(
            "wrapproj",
            json.dumps([{"role": "user", "text": "hello " + "x" * 5000}]),
        )
        self.assertIn("RE:Symbiose Submitted", panel)
        self.assertIn("Ticket:", panel)

    def test_context_plan_decides(self):
        panel = mcp_server.memory_context_plan(10, 2)
        self.assertIn("RE:Symbiose Plan", panel)
        self.assertIn("Decision: keep verbatim", panel)

    def test_rtr_status_viewport(self):
        panel = mcp_server.memory_rtr_status("wrapproj")
        self.assertIn("RE:Symbiose Status", panel)
        self.assertIn("Keeper:", panel)
        self.assertIn("Compressor:", panel)
        self.assertIn("Manager:", panel)

    def test_bad_project_refuses_by_name(self):
        panel = mcp_server.memory_inbox_read("no-such-proj-zzz")
        self.assertIn("Inbox Read Failure", panel)

    def test_keeper_evict_now_arms_flag_file(self):
        panel = mcp_server.memory_keeper_evict_now("wrapproj", "tokens", 200000)
        self.assertIn("One-Shot Armed", panel)
        cfg = json.loads(
            (
                self.test_projects / "wrapproj" / ".opencode" / "rtr-re-keeper.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(cfg["evictTokensNow"], 200000)
        refused = mcp_server.memory_keeper_evict_now("wrapproj", "bogus", 5)
        self.assertIn("Evict Refused", refused)

    def test_index_repair_relinks_without_reembed(self):
        f = self.test_projects / "wrapproj" / "directives" / "rep.md"
        f.write_text("# Rep\n\nrelink me please", encoding="utf-8")
        self.engine.index_all()
        self.engine.save_registry({})
        panel = mcp_server.memory_index(repair=True)
        self.assertIn("Registry Repaired", panel)
        self.assertIn(str(f), self.engine.load_registry())

    def test_doctor_reports_rss_and_threads(self):
        panel = mcp_server.memory_doctor()
        self.assertIn("Process Doctor", panel)
        self.assertIn("RSS:", panel)
        self.assertIn("Threads:", panel)
        self.assertIn("MainThread", panel)


if __name__ == "__main__":
    unittest.main()
