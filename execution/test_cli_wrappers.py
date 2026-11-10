# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""CLI wrapper coverage: every untested verb's happy path. CLI handlers
build their own engine, so each test patches MemoryEngine to the
isolated fixture engine and reads the printed panel."""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.absolute()))

import memory_engine
from memory_engine import MemoryEngine
import memory_cli


class TestCliWrappers(unittest.TestCase):
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
        (self.test_projects / "cliproj" / "directives").mkdir(parents=True)
        self.engine = MemoryEngine()
        self._patch = patch.object(memory_cli, "MemoryEngine", return_value=self.engine)
        self._patch.start()

    def tearDown(self):
        import shutil

        self._patch.stop()
        self.engine.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _run(self, func, *args, **kwargs):
        buf = io.StringIO()
        with redirect_stdout(buf):
            func(*args, **kwargs)
        return buf.getvalue()

    def test_search_finds_indexed_term(self):
        f = self.test_projects / "cliproj" / "directives" / "cli.md"
        f.write_text(
            "# Cli\n\nquokka router nocturnal dispatch notes", encoding="utf-8"
        )
        self.engine.index_all()
        out = self._run(memory_cli.format_search, "quokka router", "cliproj")
        self.assertIn("Semantic Search Results", out)
        self.assertIn("quokka router", out)

    def test_write_saves_concept(self):
        out = self._run(
            memory_cli.format_write, "cliproj", "cli_note", "a cli note body here"
        )
        self.assertIn("Direct Wiki Write", out)
        self.assertIn("Saved to:", out)

    def test_stats_reports_counts(self):
        out = self._run(memory_cli.format_stats)
        self.assertIn("Memory Database Status", out)
        self.assertIn("Total Files Indexed:", out)

    def test_init_bootstraps(self):
        out = self._run(memory_cli.format_init, "brandnew")
        self.assertIn("Harness Bootstrapping", out)
        self.assertTrue((self.test_projects / "brandnew" / "directives").exists())

    def test_consolidate_reports(self):
        (self.test_projects / "cliproj" / "directives" / "wiki_concepts").mkdir(
            parents=True
        )
        out = self._run(memory_cli.format_consolidate, "cliproj")
        self.assertIn("Corpus Consolidation", out)

    def test_session_start_restores(self):
        self._run(memory_cli.format_init, "cliproj")
        out = self._run(memory_cli.format_session_start, "cliproj")
        self.assertIn("Session Start: cliproj", out)
        self.assertIn("Active Goals:", out)

    def test_reflect_writes_report(self):
        out = self._run(memory_cli.format_reflect, "cliproj", "did the thing")
        self.assertIn("Session Reflection", out)
        reports = list(
            (self.test_projects / "cliproj" / "directives" / "sessions").glob("*.md")
        )
        self.assertTrue(reports)

    def test_materialize_runs(self):
        out = self._run(memory_cli.format_materialize, "cliproj")
        self.assertIn("Concept Materialization", out)

    def test_update_graph_runs(self):
        out = self._run(memory_cli.format_update_graph, "cliproj")
        self.assertIn("Bidirectional Concept Graph Builder", out)

    def test_lexikon_show_empty_then_filled(self):
        out = self._run(memory_cli.format_lexikon_show, "cliproj")
        self.assertIn("No terms yet.", out)
        self.engine.add_lexikon_term("cliproj", "cliterm", "a def", [])
        out2 = self._run(memory_cli.format_lexikon_show, "cliproj")
        self.assertIn("cliterm", out2)

    def test_janitor_reports(self):
        out = self._run(memory_cli.format_janitor, dry_run=True)
        self.assertIn("Janitor", out)
        self.assertIn("Total chunks freed:", out)

    def test_context_plan_decides(self):
        out = self._run(memory_cli.format_context_plan, 10, 2)
        self.assertIn("RE:Symbiose Plan", out)
        self.assertIn("Decision: keep verbatim", out)

    def test_keeper_evict_now_arms_flag_file(self):
        import json

        out = self._run(memory_cli.format_keeper_evict_now, "cliproj", messages=500)
        self.assertIn("One-Shot Armed", out)
        cfg = json.loads(
            (
                self.test_projects / "cliproj" / ".opencode" / "rtr-re-keeper.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(cfg["evictMessagesNow"], 500)


if __name__ == "__main__":
    unittest.main()
