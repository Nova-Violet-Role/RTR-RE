# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""RTR-RE:Rolling boundary matrix: every knob, edge and lane, many tests."""

import json
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))

from context_budget import (
    bounded_restore,
    enforce_summary_budget,
    estimate_tokens,
    mask_ndata,
    plan_compression,
    symbiose_config,
    span_dtype,
    span_lane,
)
from symbiose_worker import SymbioseWorker, content_hash, submit_json


def sized(tokens, role="assistant", tool=None):
    m = {"role": role, "text": "x" * (tokens * 4), "tokens": tokens}
    if tool:
        m["tool"] = tool
    return m


class TestConfigMatrix(unittest.TestCase):
    def test_each_knob_env(self):
        cases = [
            ("OPENCODE_MEMORY_RTRRE_TRIGGER", "trigger_tokens", 450001),
            ("OPENCODE_MEMORY_RTRRE_TARGET", "target_tokens", 150001),
            ("OPENCODE_MEMORY_RTRRE_MAX_KEEP", "max_keep_messages", 7),
            ("OPENCODE_MEMORY_RTRRE_MAX_SUMMARY", "max_summary_chars", 9001),
            ("OPENCODE_MEMORY_RTRRE_MAX_RESTORE", "max_restore_chars", 1234),
        ]
        for env, key, val in cases:
            with self.subTest(env=env):
                cfg = symbiose_config({env: str(val)})
                self.assertEqual(cfg[key], val)
                self.assertEqual(cfg["sources"][key], "env")

    def test_each_knob_refuses_garbage(self):
        for env in [
            "OPENCODE_MEMORY_RTRRE_TRIGGER",
            "OPENCODE_MEMORY_RTRRE_TARGET",
            "OPENCODE_MEMORY_RTRRE_MAX_KEEP",
            "OPENCODE_MEMORY_RTRRE_MAX_SUMMARY",
            "OPENCODE_MEMORY_RTRRE_MAX_RESTORE",
        ]:
            for bad in ["abc", "0", "-3", "1.5"]:
                with self.subTest(env=env, bad=bad):
                    with self.assertRaises(ValueError):
                        symbiose_config({env: bad})

    def test_target_equal_trigger_refused(self):
        with self.assertRaises(ValueError):
            symbiose_config(
                {
                    "OPENCODE_MEMORY_RTRRE_TRIGGER": "1000",
                    "OPENCODE_MEMORY_RTRRE_TARGET": "1000",
                }
            )

    def test_whitespace_env_is_preset_default(self):
        cfg = symbiose_config({"OPENCODE_MEMORY_RTRRE_TARGET": "  "})
        self.assertEqual(cfg["target_tokens"], 200000)
        self.assertEqual(cfg["sources"]["target_tokens"], "preset:re-symbiose-mugen")


class TestPlanBoundaries(unittest.TestCase):
    CFG = {"trigger_tokens": 1000, "target_tokens": 400, "max_keep_messages": 3}

    def test_at_trigger_no_compress(self):
        plan = plan_compression([sized(1000)], config=self.CFG)
        self.assertFalse(plan["compress"])

    def test_one_over_trigger_compresses(self):
        msgs = [sized(600), sized(401), sized(10, role="user")]
        plan = plan_compression(msgs, config=self.CFG)
        self.assertTrue(plan["compress"])
        self.assertIn(2, plan["keep"])

    def test_message_cap_binds_before_tokens(self):
        msgs = [sized(300) for _ in range(10)] + [sized(10, role="user")]
        plan = plan_compression(msgs, config=self.CFG)
        # cap 3 + protected/last-user already inside tail walk
        self.assertLessEqual(len(plan["keep"]), 4)

    def test_single_huge_message_kept_not_lost(self):
        msgs = [sized(5000, role="user")]
        plan = plan_compression(msgs, config=self.CFG)
        self.assertEqual(plan["keep"], [0])

    def test_empty_and_tiny(self):
        self.assertFalse(plan_compression([], config=self.CFG)["compress"])
        self.assertFalse(plan_compression([sized(1)], config=self.CFG)["compress"])

    def test_every_protected_tool_kept(self):
        for tool in ["todowrite"]:
            with self.subTest(tool=tool):
                msgs = [sized(50, tool=tool)] + [sized(300) for _ in range(10)]
                msgs.append(sized(5, role="user"))
                plan = plan_compression(msgs, config=self.CFG)
                self.assertIn(0, plan["keep"])

    def test_unprotected_tool_evictable(self):
        msgs = [sized(300, tool="bash")] + [sized(300) for _ in range(10)]
        msgs.append(sized(5, role="user"))
        plan = plan_compression(msgs, config=self.CFG)
        self.assertIn(0, plan["evict"])

    def test_keep_evict_partition(self):
        msgs = [sized(250) for _ in range(20)]
        plan = plan_compression(msgs, config=self.CFG)
        self.assertEqual(sorted(plan["keep"] + plan["evict"]), list(range(20)))
        self.assertEqual(len(plan["evict_payload"]), len(plan["evict"]))


class TestLanesAndTypes(unittest.TestCase):
    def test_lane_table(self):
        self.assertEqual(span_lane({"role": "user"}), "read")
        self.assertEqual(span_lane({"role": "tool"}), "read")
        self.assertEqual(span_lane({"role": "assistant"}), "written")
        self.assertEqual(span_lane({"role": "assistant", "tool": "read"}), "read")
        self.assertEqual(span_lane({"role": "system"}), "read")

    def test_dtype_table(self):
        self.assertEqual(span_dtype("plain prose here"), "PCDATA")
        self.assertEqual(span_dtype("run `make check` now"), "CDATA")
        self.assertEqual(span_dtype("see https://example.com/x"), "CDATA")
        self.assertEqual(span_dtype("path C:/a/b/c.txt end"), "CDATA")
        self.assertEqual(span_dtype("QUJD" * 40), "NDATA")

    def test_mask_ndata_edges(self):
        self.assertEqual(mask_ndata(""), "")
        self.assertEqual(mask_ndata("short"), "short")
        self.assertIn("[NDATA]", mask_ndata("a " + "QUJD" * 40 + " b"))


class TestSummaryAndRestore(unittest.TestCase):
    def test_summary_exact_cap_unchanged(self):
        s = "y" * 20000
        out, shed = enforce_summary_budget(s)
        self.assertEqual(out, s)
        self.assertEqual(shed, 0)

    def test_summary_one_over_sheds(self):
        s = "head\n" + "y" * 20000
        out, shed = enforce_summary_budget(s)
        self.assertLessEqual(len(out), 20000)
        self.assertGreater(shed, 0)

    def test_summary_keeps_newest(self):
        s = "\n".join(f"line-{i}" for i in range(10000))
        out, _ = enforce_summary_budget(s)
        self.assertIn("line-9999", out)
        self.assertNotIn("line-0\n", out)

    def test_restore_edges(self):
        self.assertEqual(bounded_restore("x" * 4000), "x" * 4000)
        self.assertEqual(len(bounded_restore("x" * 4001)), 4000)
        self.assertEqual(bounded_restore("", max_chars=5), "")

    def test_estimate_edges(self):
        self.assertEqual(estimate_tokens(""), 0)
        self.assertEqual(estimate_tokens("a"), 1)
        self.assertEqual(estimate_tokens("abcd"), 1)
        self.assertEqual(estimate_tokens("abcde"), 2)


class TestWorkerMatrix(unittest.TestCase):
    def test_hash_stable_and_sensitive(self):
        a = [{"role": "user", "text": "hi"}]
        self.assertEqual(content_hash(a), content_hash(list(a)))
        self.assertNotEqual(
            content_hash(a), content_hash([{"role": "user", "text": "ho"}])
        )
        self.assertNotEqual(
            content_hash(a), content_hash([{"role": "assistant", "text": "hi"}])
        )

    def test_hash_sensitive_to_tokens_and_tool(self):
        a = [{"role": "assistant", "text": "same", "tokens": 10}]
        b = [{"role": "assistant", "text": "same", "tokens": 9999}]
        c = [{"role": "assistant", "text": "same", "tokens": 10, "tool": "todowrite"}]
        self.assertNotEqual(content_hash(a), content_hash(b))
        self.assertNotEqual(content_hash(a), content_hash(c))

    def test_poll_unknown_ticket(self):
        w = SymbioseWorker(lambda spans: "ok")
        try:
            self.assertEqual(w.poll(4242)["status"], "unknown")
        finally:
            w.close()

    def test_below_trigger_ready_without_sink(self):
        calls = []
        w = SymbioseWorker(lambda spans: calls.append(spans))
        try:
            t = w.submit([{"role": "user", "text": "tiny"}])
            done = w.wait(t["id"], timeout=5)
            self.assertEqual(done["status"], "ready")
            self.assertEqual(done["evicted"], 0)
            self.assertEqual(calls, [])
        finally:
            w.close()

    def test_submit_json_roundtrip_and_refusals(self):
        seen = []
        w = SymbioseWorker(lambda spans: seen.extend(spans) or "ok")
        try:
            msgs = [
                {"role": "assistant", "text": "z" * 900000},
                {"role": "user", "text": "latest"},
            ]
            ticket = submit_json(w, json.dumps(msgs))
            done = w.wait(ticket["id"], timeout=5)
            self.assertEqual(done["status"], "ready")
            with self.assertRaises(ValueError):
                submit_json(w, "not json")
            with self.assertRaises(ValueError):
                submit_json(w, '{"role": "user"}')
            with self.assertRaises(ValueError):
                submit_json(w, '[{"text": 3}]')
        finally:
            w.close()


if __name__ == "__main__":
    unittest.main()
