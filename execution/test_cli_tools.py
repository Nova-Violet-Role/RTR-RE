# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""CLI surface tests (panels, exits, refusal shapes)."""

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


class TestCliTools(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.test_projects = self.test_dir / "projects"
        self.test_db = self.test_dir / "db"
        memory_engine.PROJECTS_DIR = self.test_projects
        memory_engine.PROJECT_ROOTS = [self.test_projects]
        memory_engine.DB_DIR = self.test_db
        memory_engine.REGISTRY_FILE = self.test_dir / "registry.json"
        memory_engine.EXTRA_ROOTS_FILE = self.test_dir / "extra_roots.json"
        self.engine = MemoryEngine()

    def tearDown(self):
        import shutil

        self.engine.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_index_renders_refusal_and_exits_1_when_read_only(self):
        reader = MemoryEngine()
        self.assertTrue(reader.read_only)
        try:
            buf = io.StringIO()
            with patch.object(memory_cli, "MemoryEngine", return_value=reader):
                with redirect_stdout(buf):
                    with self.assertRaises(SystemExit) as cm:
                        memory_cli.format_index()
            self.assertEqual(cm.exception.code, 1)
            self.assertIn("Refus", buf.getvalue())
        finally:
            reader.close()

    def test_session_commit_refusal_renders_error_and_exits_1(self):
        reader = MemoryEngine()
        self.assertTrue(reader.read_only)
        try:
            buf = io.StringIO()
            with patch.object(memory_cli, "MemoryEngine", return_value=reader):
                with redirect_stdout(buf):
                    with self.assertRaises(SystemExit) as cm:
                        memory_cli.format_session_commit("raceproj", chat="")
            self.assertEqual(cm.exception.code, 1)
            self.assertIn("Refus", buf.getvalue())
        finally:
            reader.close()

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

        buf = io.StringIO()
        with patch.object(memory_cli, "MemoryEngine", return_value=StubEngine()):
            with redirect_stdout(buf):
                memory_cli.format_explain("q")
        out = buf.getvalue()
        self.assertIn("x0.60", out)
        self.assertNotIn("x0.45", out)

    def _raceproj_mem(self):
        proj = self.test_projects / "raceproj"
        (proj / "directives").mkdir(parents=True, exist_ok=True)
        mem = proj / ".opencode" / "memory"
        mem.mkdir(parents=True, exist_ok=True)
        return mem

    def _write_cli_sidecar(self, mem, name, messages):
        import json

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

    def _tiny_worker(self, trigger=100, target=50):
        from symbiose_worker import SymbioseWorker

        return SymbioseWorker(
            lambda spans: "ok",
            config={
                "trigger_tokens": trigger,
                "target_tokens": target,
                "max_keep_messages": 200,
            },
        )

    def test_symbiose_submit_compresses_and_reports(self):
        import json

        self._raceproj_mem()
        worker = self._tiny_worker()
        try:
            msgs = json.dumps(
                [
                    {"role": "user", "text": "hi"},
                    {"role": "assistant", "text": "word " * 300},
                    {"role": "assistant", "text": "word " * 300},
                ]
            )
            buf = io.StringIO()
            with patch.object(
                memory_cli.sw, "open_project_worker", return_value=worker
            ):
                with redirect_stdout(buf):
                    memory_cli.format_symbiose_submit("raceproj", msgs)
            out = buf.getvalue()
            self.assertIn("RE:Symbiose Compressed", out)
            self.assertIn("Status: ready", out)
            self.assertIn("Sink: ok", out)
        finally:
            worker.close()

    def test_symbiose_submit_refuses_bad_input(self):
        self._raceproj_mem()
        worker = self._tiny_worker()
        try:
            with patch.object(
                memory_cli.sw, "open_project_worker", return_value=worker
            ):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    with self.assertRaises(SystemExit) as cm:
                        memory_cli.format_symbiose_submit("raceproj", None, None)
                self.assertEqual(cm.exception.code, 1)
                self.assertIn("exactly one", buf.getvalue())
                buf = io.StringIO()
                with redirect_stdout(buf):
                    with self.assertRaises(SystemExit) as cm:
                        memory_cli.format_symbiose_submit(
                            "raceproj", "[]", "/tmp/x.json"
                        )
                self.assertEqual(cm.exception.code, 1)
                self.assertIn("only one", buf.getvalue())
                buf = io.StringIO()
                with redirect_stdout(buf):
                    with self.assertRaises(SystemExit) as cm:
                        memory_cli.format_symbiose_submit("raceproj", "{nope", None)
                self.assertEqual(cm.exception.code, 1)
                self.assertIn("not valid JSON", buf.getvalue())
                buf = io.StringIO()
                with redirect_stdout(buf):
                    with self.assertRaises(SystemExit) as cm:
                        memory_cli.format_symbiose_submit(
                            "raceproj", None, str(self.test_dir / "nope.json")
                        )
                self.assertEqual(cm.exception.code, 1)
                self.assertIn("Refused", buf.getvalue())
        finally:
            worker.close()

    def test_symbiose_submit_reads_messages_file(self):
        import json

        self._raceproj_mem()
        worker = self._tiny_worker()
        try:
            f = self.test_dir / "msgs.json"
            f.write_text(json.dumps([{"role": "user", "text": "hi"}]), encoding="utf-8")
            buf = io.StringIO()
            with patch.object(
                memory_cli.sw, "open_project_worker", return_value=worker
            ):
                with redirect_stdout(buf):
                    memory_cli.format_symbiose_submit("raceproj", None, str(f))
            self.assertIn("RE:Symbiose Compressed", buf.getvalue())
        finally:
            worker.close()

    def test_symbiose_drain_consumes_sidecars(self):
        mem = self._raceproj_mem()
        first = self._write_cli_sidecar(
            mem, "rtrre-aa.submit.json", [{"role": "user", "text": "hi"}]
        )
        second = self._write_cli_sidecar(
            mem, "rtrre-bb.submit.json", [{"role": "user", "text": "yo"}]
        )
        worker = self._tiny_worker()
        try:
            buf = io.StringIO()
            with patch.object(
                memory_cli.sw, "open_project_worker", return_value=worker
            ):
                with redirect_stdout(buf):
                    memory_cli.format_symbiose_drain("raceproj")
            out = buf.getvalue()
            self.assertIn("Drain: 2 consumed, 0 left, 0 quarantined", out)
            self.assertFalse(first.exists())
            self.assertFalse(second.exists())
        finally:
            worker.close()

    def test_symbiose_compress_fires_with_direct_target(self):
        import json

        self._raceproj_mem()
        worker = self._tiny_worker(trigger=1000, target=500)
        try:
            msgs = json.dumps(
                [
                    {"role": "user", "text": "hi"},
                    {"role": "assistant", "text": "word " * 600},
                ]
            )
            buf = io.StringIO()
            with patch.object(
                memory_cli.sw, "open_project_worker", return_value=worker
            ):
                with redirect_stdout(buf):
                    memory_cli.format_symbiose_compress("raceproj", msgs, 50)
            out = buf.getvalue()
            self.assertIn("Target: 50", out)
            self.assertIn("Status: ready", out)
            self.assertEqual(worker.poll(1)["plan_overrides"], {"target_tokens": 50})
        finally:
            worker.close()

    def test_symbiose_compress_refuses_bad_target(self):
        import json

        self._raceproj_mem()
        worker = self._tiny_worker()
        try:
            msgs = json.dumps([{"role": "user", "text": "hi"}])
            buf = io.StringIO()
            with patch.object(
                memory_cli.sw, "open_project_worker", return_value=worker
            ):
                with redirect_stdout(buf):
                    with self.assertRaises(SystemExit) as cm:
                        memory_cli.format_symbiose_compress("raceproj", msgs, 500)
            self.assertEqual(cm.exception.code, 1)
            self.assertIn("below trigger", buf.getvalue())
        finally:
            worker.close()

    def test_lexikon_build_refusal_exits_1(self):
        reader = MemoryEngine()
        buf = io.StringIO()
        try:
            with patch.object(memory_cli, "MemoryEngine", return_value=reader):
                with redirect_stdout(buf):
                    with self.assertRaises(SystemExit) as cm:
                        memory_cli.format_lexikon_build("_global")
            self.assertEqual(cm.exception.code, 1)
            self.assertIn("hand-curated", buf.getvalue())
        finally:
            reader.close()

    def test_lexikon_add_error_exits_1(self):
        class StubEngine:
            def add_lexikon_term(self, project, term, definition="", aliases=None):
                return {"status": "error", "message": "Empty term."}

        buf = io.StringIO()
        with patch.object(memory_cli, "MemoryEngine", return_value=StubEngine()):
            with redirect_stdout(buf):
                with self.assertRaises(SystemExit) as cm:
                    memory_cli.format_lexikon_add("raceproj", "")
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Empty term", buf.getvalue())


class TestErrorText(unittest.TestCase):
    def test_bare_exceptions_render_non_blank(self):
        self.assertEqual(memory_cli._error_text(MemoryError()), "MemoryError()")
        self.assertEqual(memory_cli._error_text(ValueError("bad")), "bad")


class DrainFailureTests(unittest.TestCase):
    def test_drain_failure_renders_panel_and_exits_1(self):
        # E-T15-2b: every CLI sibling renders a Failure panel with
        # exit 1; drain had try/finally with no except (traceback).
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "proj"
            (proj / ".opencode" / "memory").mkdir(parents=True)
            with patch.object(
                memory_cli.sw,
                "drain_submit_sidecars",
                side_effect=OSError("drain boom"),
            ):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    with self.assertRaises(SystemExit) as cm:
                        memory_cli.format_symbiose_drain(str(proj))
                self.assertEqual(cm.exception.code, 1)
                self.assertIn("Symbiose Drain Failure", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
