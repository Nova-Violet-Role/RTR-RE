# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))

import memory_engine
import memory_mcp_server as mcp_server


class TestRtrStatusViewport(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.test_projects = self.test_dir / "projects"
        self.test_db = self.test_dir / "db"
        memory_engine.PROJECTS_DIR = self.test_projects
        memory_engine.PROJECT_ROOTS = [self.test_projects]
        memory_engine.DB_DIR = self.test_db
        memory_engine.REGISTRY_FILE = self.test_dir / "registry.json"
        memory_engine.EXTRA_ROOTS_FILE = self.test_dir / "extra_roots.json"
        (self.test_projects / "demoproj" / ".opencode").mkdir(parents=True)
        self.proj = str(self.test_projects / "demoproj")

    def tearDown(self):
        import shutil

        mcp_server.engine.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_absent_keeper_file_reports_absent_never_active(self):
        payload = mcp_server.rtr_status_payload(self.proj)
        self.assertFalse(payload["keeper"]["active"])
        self.assertIn("absent", payload["keeper"]["detail"])

    def test_present_status_file_reports_bounds_and_decision(self):
        status = {
            "keeper": "rtr-re-keeper",
            "version": "0.3.0",
            "enabled": True,
            "triggerTokens": 40000,
            "targetTokens": 20000,
            "maxKeepMessages": 40,
            "decision": "evicted",
            "time": "2026-10-27T00:00:00",
            "evicted": 21,
            "sinkPath": "/tmp/x.md",
        }
        (Path(self.proj) / ".opencode" / "rtr-re-keeper-status.json").write_text(
            json.dumps(status), encoding="utf-8"
        )
        payload = mcp_server.rtr_status_payload(self.proj)
        self.assertTrue(payload["keeper"]["active"])
        self.assertEqual(payload["keeper"]["trigger_tokens"], 40000)
        self.assertEqual(payload["keeper"]["last_decision"], "evicted")
        panel = mcp_server.memory_rtr_status(self.proj)
        self.assertIn("ACTIVE", panel)
        self.assertIn("40000", panel)

    def test_corrupt_status_file_reports_parse_error(self):
        (Path(self.proj) / ".opencode" / "rtr-re-keeper-status.json").write_text(
            "{oops", encoding="utf-8"
        )
        payload = mcp_server.rtr_status_payload(self.proj)
        self.assertTrue(payload["keeper"]["active"])
        self.assertIn("parse_error", json.dumps(payload["keeper"]))

    def test_worker_stats_shape(self):
        from symbiose_worker import SymbioseWorker

        w = SymbioseWorker(lambda spans: "ok")
        try:
            st = w.stats()
            self.assertEqual(st["tickets"], 0)
            self.assertEqual(st["queued"], 0)
            self.assertFalse(st["closed"])
            self.assertEqual(st["max_retained"], 512)
        finally:
            w.close()


if __name__ == "__main__":
    unittest.main()
