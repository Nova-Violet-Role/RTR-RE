# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Architecture contracts: every amplification/enhancement pinned by a test.

Native Keeper wiring, MCP tool surface, host bridge constants,
geometry/amplify artifacts, bounds witnesses. Lab-only vendored trees
(Rolling proxy, ACP template) are guarded by existence with an explicit
skip reason: the standalone shipped tree contains neither folder, and a
skip there is a stated scope fact, not a hidden pass. Static reads are
measured evidence about declarations; behavior stays in the unit suites.
"""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "execution"))
ROLLING_PROXY = ROOT / "rolling-context" / "1.8.0" / "proxy"
if ROLLING_PROXY.exists():
    sys.path.insert(0, str(ROLLING_PROXY))
ACP_TEMPLATE = ROOT / ".opencode" / "acp.jsonc"


def read(p):
    return Path(p).read_text(encoding="utf-8")


class TestRollingProxyCaps(unittest.TestCase):
    def setUp(self):
        if not ROLLING_PROXY.exists():
            self.skipTest("vendored Rolling proxy is lab-only; absent in standalone")

    def test_cap_defaults_and_shed(self):
        import compressor

        self.assertEqual(compressor.MAX_SUMMARY_CHARS, 20000)
        self.assertEqual(compressor.MAX_KEEP_MESSAGES, 40)
        big = "\n".join(f"step {i}" for i in range(5000))
        out = compressor.cap_summary(big)
        self.assertLessEqual(len(out), 20000)
        self.assertIn("step 4999", out)
        self.assertEqual(compressor.cap_summary("tiny"), "tiny")
        self.assertEqual(compressor.cap_summary(big, max_chars=0), big)

    def test_safe_cut_never_ends_on_tool_use(self):
        import compressor

        c = compressor.RollingCompressor(trigger_tokens=10, target_tokens=5)
        msgs = [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "name": "x", "input": {}}],
            },
            {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]},
            {"role": "assistant", "content": "done"},
            {"role": "user", "content": "next"},
        ]
        cut = c._safe_cut(msgs, 2, 0)
        self.assertFalse(c._has_tool_use(msgs[cut - 1]) if cut > 0 else False)

    def test_summary_marker_roundtrip(self):
        import compressor

        c = compressor.RollingCompressor()
        msgs = [
            {
                "role": "user",
                "content": f"{compressor.SUMMARY_MARKER}\nOLD\n{compressor.SUMMARY_END_MARKER}",
            }
        ]
        self.assertTrue(c._has_summary(msgs))
        self.assertEqual(c._extract_summary(msgs), "OLD")


class TestAcpWiring(unittest.TestCase):
    def setUp(self):
        if not ACP_TEMPLATE.exists():
            self.skipTest("ACP template is lab-only; standalone keeper is native")

    def _load(self, path):
        raw = read(path)
        stripped = "\n".join(
            line for line in raw.splitlines() if not line.strip().startswith("//")
        )
        return json.loads(stripped)

    def test_project_template_matches_plan(self):
        cfg = self._load(ROOT / ".opencode" / "acp.jsonc")
        c = cfg["compress"]
        self.assertIs(cfg["enabled"], True)
        # Three offices: ACP is Keeper only — deny means no ACP compression
        # tools and no nudges (inject.ts deny guards). Rolling compresses.
        self.assertEqual(c["permission"], "deny")
        self.assertEqual(c["maxContextLimit"], 200000)
        self.assertEqual(c["preserveRecentTokens"], 100000)
        self.assertEqual(c["preserveRecentMessages"], 40)
        self.assertEqual(c["protectedTools"], ["todowrite"])
        self.assertIs(c["reasoning"]["drop"], True)
        self.assertEqual(c["completionReserveTokens"], 32768)
        self.assertEqual(c["maxSummaryLengthHard"], 20000)

    def test_live_and_project_agree(self):
        live = Path.home() / ".config" / "opencode" / "acp.jsonc"
        if not live.exists():
            self.skipTest("no live acp.jsonc on this machine")
        a = self._load(live)["compress"]
        b = self._load(ROOT / ".opencode" / "acp.jsonc")["compress"]
        for key in [
            "maxContextLimit",
            "preserveRecentTokens",
            "preserveRecentMessages",
            "protectedTools",
            "completionReserveTokens",
        ]:
            self.assertEqual(a[key], b[key], key)

    def test_backup_exists(self):
        bak = Path.home() / ".config" / "opencode" / "acp.jsonc.bak.20261026"
        if not bak.exists():
            self.skipTest("backup only on the operator machine")
        self.assertGreater(bak.stat().st_size, 1000)
        self.assertIn('"enabled": false', read(bak))


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
        self.assertEqual((cb.TRIGGER_TOKENS, cb.TARGET_TOKENS), (250000, 100000))
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
                "symbiose-ah",
                "Symbiose-AH!",
                250000,
                100000,
                40,
                "rtr-full",
                4,
                60,
                "symbiose-ah/rtr-full/t4/p60",
                "Symbiose-AH! · RTR-FULL · T4 · P60",
            ),
        )
        keeper = read(ROOT / "opencode-plugin" / "rtr-re-keeper.js")
        self.assertIn("const PRESET_REGISTRY = loadPresetRegistry()", keeper)
        self.assertIn(
            "const DEFAULT_TRIGGER_TOKENS = DEFAULT_PRESET_VALUES.triggerTokens",
            keeper,
        )
        self.assertIn(
            "const DEFAULT_TARGET_TOKENS = DEFAULT_PRESET_VALUES.targetTokens",
            keeper,
        )
        self.assertIn(
            "TRIGGER=320000", read(ROOT / "directives" / "context-management.md")
        )
        self.assertIn("320000", read(ROOT / "directives" / "rtr-re-symbiose.md"))
        if ACP_TEMPLATE.exists():
            # Lab deployment profile: Keeper limits bound to the current
            # model's 200k input cap — a different layer, kept explicit.
            self.assertIn("200000", read(ACP_TEMPLATE))


class TestNativeKeeperContract(unittest.TestCase):
    def test_keeper_is_first_party_and_acp_free(self):
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
        # Lab-only predecessors (opencode-acp, rolling-context) exist only in
        # the lab tree; the standalone tree ships as its own git history.
        if (ROOT / "opencode-acp").exists():
            self.skipTest("lab tree: vendored predecessors are lab-only")
        self.assertFalse((ROOT / "rolling-context").exists())


if __name__ == "__main__":
    unittest.main()
