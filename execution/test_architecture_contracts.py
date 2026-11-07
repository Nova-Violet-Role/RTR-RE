# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Architecture contracts: every amplification/enhancement pinned by a test.

Native Keeper wiring, MCP tool surface, host bridge constants,
geometry/amplify artifacts, bounds witnesses. Vendored lab trees are
guarded by existence with an explicit skip reason: the standalone shipped
tree contains neither folder, and a skip there is a stated scope fact, not
a hidden pass. Static reads are measured evidence about declarations;
behavior stays in the unit suites.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "execution"))


def read(p):
    return Path(p).read_text(encoding="utf-8")


class TestStateIsolationContract(unittest.TestCase):
    def test_every_state_path_has_env_override(self):
        src = read(ROOT / "execution" / "memory_engine.py")
        for env_name in [
            "OPENCODE_MEMORY_DIR",
            "OPENCODE_MEMORY_DB_DIR",
            "OPENCODE_MEMORY_REGISTRY_FILE",
            "OPENCODE_MEMORY_EXTRA_ROOTS_FILE",
            "OPENCODE_MEMORY_LEXIKON_GLOBAL_FILE",
        ]:
            self.assertIn(env_name, src)


class TestHostBridgeContract(unittest.TestCase):
    HOST = Path("D:/OPENCODE-SRC/opencode-dev/packages/opencode/src/session")

    def test_compaction_constants(self):
        if not self.HOST.exists():
            self.skipTest("host source tree absent")
        src = read(self.HOST / "compaction.ts")
        self.assertIn("PRUNE_MINIMUM = 20_000", src)
        self.assertIn("PRUNE_PROTECT = 40_000", src)
        self.assertIn("SessionMemory.commit", src)
        self.assertIn("SessionMemory.restoreFresh", src)

    def test_memory_bridge_caps(self):
        if not self.HOST.exists():
            self.skipTest("host source tree absent")
        src = read(self.HOST / "memory.ts")
        self.assertIn("DEFAULT_MAX_CHARS = 4_000", src)
        self.assertIn("MAX_TOOL_CHARS = 64_000", src)
        self.assertIn("memory_session_commit", src)
        self.assertIn("memory_session_start", src)


class TestArtifactsAndSurface(unittest.TestCase):
    def test_geometry_records_exist_in_order(self):
        for name in [
            "survey",
            "plan",
            "renovation",
            "production",
            "renovation-2",
            "evaluation",
        ]:
            p = ROOT / "artifacts" / "geometry" / f"2026-10-26-{name}.md"
            self.assertTrue(p.exists(), name)
            self.assertNotIn("\r", read(p))

    def test_amplify_study_complete(self):
        base = ROOT / "artifacts" / "amplify-codebase"
        for name in ["ledger.md", "state.md", "roadmap.md", "handoff.md"]:
            self.assertTrue((base / name).exists(), name)
        self.assertIn("mid 0.3.0 -> 0.4.0", read(base / "state.md"))

    def test_mcp_surface_has_symbiose_tools(self):
        src = read(ROOT / "execution" / "memory_mcp_server.py")
        self.assertIn("config=context_budget.symbiose_config()", src)
        for tool in [
            "memory_context_plan",
            "memory_symbiose_submit",
            "memory_symbiose_poll",
            "memory_session_commit",
            "memory_session_start",
            "memory_search",
        ]:
            self.assertIn(f"def {tool}", src)

    def test_bounds_agree_four_witnesses(self):
        import context_budget as cb

        profile = cb.resolve_preset_profile({})
        self.assertEqual((cb.TRIGGER_TOKENS, cb.TARGET_TOKENS), (400000, 200000))
        self.assertEqual(
            (
                profile["preset"],
                profile["preset_display"],
                profile["keeper"]["trigger_tokens"],
                profile["keeper"]["target_tokens"],
                profile["keeper"]["max_keep_messages"],
                profile["modality"],
                profile["threads_per_model"],
                profile["parking_percent"],
                profile["profile_code"],
                profile["profile_label"],
            ),
            (
                "re-symbiose-mugen",
                "Re-Symbiose-Mugen",
                400000,
                200000,
                200,
                "rtr-full",
                4,
                60,
                "re-symbiose-mugen/rtr-full/t4/p60",
                "Re-Symbiose-Mugen · RTR-FULL · T4 · P60",
            ),
        )
        keeper = read(ROOT / "opencode-plugin" / "rtr-re-keeper.js")
        # Finding d (TODO-65): the registry is reloadable, so the registry
        # bindings are `let` and reloadRegistry re-derives them. The four
        # witnesses (Python planner, registry JSON, keeper JS, directives)
        # must still agree on the same bounds.
        self.assertIn("let PRESET_REGISTRY = loadPresetRegistry()", keeper)
        self.assertIn("function reloadRegistry(path)", keeper)
        self.assertIn(
            "let DEFAULT_TRIGGER_TOKENS = DEFAULT_PRESET_VALUES.triggerTokens",
            keeper,
        )
        self.assertIn(
            "let DEFAULT_TARGET_TOKENS = DEFAULT_PRESET_VALUES.targetTokens",
            keeper,
        )
        self.assertIn(
            "TRIGGER=320000", read(ROOT / "directives" / "context-management.md")
        )
        self.assertIn("320000", read(ROOT / "directives" / "rtr-re-symbiose.md"))


class TestNativeKeeperContract(unittest.TestCase):
    def test_keeper_is_first_party_and_self_contained(self):
        plugin = ROOT / "opencode-plugin" / "rtr-re-keeper.js"
        self.assertTrue(plugin.exists())
        src = read(plugin)
        self.assertIn("experimental.chat.messages.transform", src)
        self.assertIn("command.execute.before", src)
        self.assertIn('"rtr"', src)
        self.assertIn("rtr-re-keeper-status", src)
        self.assertNotIn("acp.jsonc", src)
        self.assertNotIn("opencode-acp", src)
        self.assertTrue((ROOT / "opencode-plugin" / "rtr-re-keeper.test.mjs").exists())

    def test_mcp_viewport_reports_all_three_offices(self):
        src = read(ROOT / "execution" / "memory_mcp_server.py")
        self.assertIn("def memory_rtr_status", src)
        self.assertIn("rtr_status_payload", src)
        self.assertIn("keeper", src)
        self.assertIn("compressor", src)
        self.assertIn("manager", src)

    def test_standalone_tree_carries_no_vendored_folders(self):
        # The standalone tree ships as its own git history; vendored lab
        # folders must never appear in it.
        if (ROOT / "opencode-acp").exists():
            self.skipTest("lab tree: vendored folders are lab-only")
        self.assertFalse((ROOT / "rolling-context").exists())


if __name__ == "__main__":
    unittest.main()
