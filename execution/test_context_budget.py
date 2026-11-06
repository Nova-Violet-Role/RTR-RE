# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))

from context_budget import (
    TARGET_TOKENS,
    TRIGGER_TOKENS,
    MAX_KEEP_MESSAGES,
    MAX_SUMMARY_CHARS,
    bounded_restore,
    enforce_summary_budget,
    estimate_tokens,
    plan_compression,
)


def msg(role, text, tool=None):
    m = {"role": role, "text": text}
    if tool:
        m["tool"] = tool
    return m


class TestContextBudget(unittest.TestCase):
    def test_constants_match_plan(self):
        # Public default is Symbiose-AH!: verbatim to 250k, 100k tail.
        self.assertEqual(TARGET_TOKENS, 100000)
        self.assertEqual(TRIGGER_TOKENS, 250000)
        self.assertEqual(MAX_KEEP_MESSAGES, 40)
        self.assertEqual(MAX_SUMMARY_CHARS, 20000)

    def test_below_trigger_is_noop(self):
        msgs = [msg("user", "hello"), msg("assistant", "hi")]
        plan = plan_compression(msgs)
        self.assertFalse(plan["compress"])
        self.assertEqual(plan["keep"], [0, 1])
        self.assertEqual(plan["evict"], [])

    def test_acceptance_keeps_bounded_tail(self):
        # 120 messages, each ~3000 tokens (12000 chars) = ~360k total > 320k.
        msgs = []
        for i in range(120):
            role = "user" if i % 2 == 0 else "assistant"
            msgs.append(msg(role, f"message {i} " + "x" * 12000))
        plan = plan_compression(msgs)
        self.assertTrue(plan["compress"])
        self.assertLessEqual(len(plan["keep"]), MAX_KEEP_MESSAGES)
        self.assertLessEqual(plan["keep_tokens"], TARGET_TOKENS)
        self.assertEqual(sorted(plan["keep"] + plan["evict"]), list(range(120)))
        # Last user message (index 118) and newest message survive.
        self.assertIn(119, plan["keep"])
        self.assertIn(118, plan["keep"])

    def test_protected_tool_never_evicted(self):
        msgs = [msg("assistant", "s" * 4000, tool="todowrite")]
        msgs += [msg("assistant", "y" * 12000) for _ in range(120)]
        msgs.append(msg("user", "latest question"))
        plan = plan_compression(msgs)
        self.assertTrue(plan["compress"])
        self.assertIn(0, plan["keep"])
        self.assertIn(len(msgs) - 1, plan["keep"])

    def test_ndata_masked_in_evict_payload(self):
        blob = "QUJD" * 40  # 160-char base64-like span
        msgs = [msg("assistant", f"data {blob} end " + "z" * 12000)]
        msgs += [msg("assistant", "w" * 12000) for _ in range(120)]
        msgs.append(msg("user", "go"))
        plan = plan_compression(msgs)
        evicted_text = " ".join(e["text"] for e in plan["evict_payload"])
        self.assertNotIn(blob, evicted_text)
        self.assertIn("[NDATA]", evicted_text)

    def test_tool_pairs_are_not_split_backwards(self):
        # tool result kept implies its call kept when adjacent pair straddles cut.
        msgs: list = [msg("assistant", "a" * 12000) for _ in range(120)]
        msgs.append(msg("assistant", "call", tool="read"))
        msgs.append({"role": "tool", "text": "result", "tool_call": True})
        msgs.append(msg("user", "next"))
        plan = plan_compression(msgs)
        keep = set(plan["keep"])
        if len(msgs) - 2 in keep:
            self.assertIn(len(msgs) - 3, keep)

    def test_planner_never_mutates_input(self):
        # Collision rule: one mutator per transport (vendored proxy or ACP
        # compress). The RE:Symbiose planner is advisory only.
        import copy

        msgs = [msg("assistant", "q" * 12000) for _ in range(120)]
        msgs.append(msg("user", "go"))
        before = copy.deepcopy(msgs)
        plan = plan_compression(msgs)
        self.assertTrue(plan["compress"])
        self.assertEqual(msgs, before)

    def test_evicted_substance_kept_verbatim_for_index(self):
        marker = "UNIQUE-DECISION-keep-me-exactly"
        msgs = [msg("assistant", marker + " " + "v" * 12000)]
        msgs += [msg("assistant", "u" * 12000) for _ in range(120)]
        msgs.append(msg("user", "go"))
        plan = plan_compression(msgs)
        payload = " ".join(e["text"] for e in plan["evict_payload"])
        self.assertIn(marker, payload)

    def test_tool_pair_chain_repaired_to_call(self):
        cfg = {"trigger_tokens": 250, "target_tokens": 150, "max_keep_messages": 40}
        msgs = [
            {"role": "assistant", "text": "call", "tool": "read", "tokens": 100},
            {"role": "tool", "text": "result-1", "tokens": 100},
            {"role": "tool", "text": "result-2", "tokens": 100},
        ]
        plan = plan_compression(msgs, config=cfg)
        self.assertEqual(plan["keep"], [0, 1, 2])

    def test_summary_budget_enforced(self):
        big = "line\n" * 10000
        out, shed = enforce_summary_budget(big)
        self.assertLessEqual(len(out), MAX_SUMMARY_CHARS)
        self.assertGreater(shed, 0)
        small = "short summary"
        out2, shed2 = enforce_summary_budget(small)
        self.assertEqual(out2, small)
        self.assertEqual(shed2, 0)

    def test_bounded_restore(self):
        text = "r" * 9000
        self.assertEqual(len(bounded_restore(text)), 4000)
        self.assertEqual(bounded_restore("ok"), "ok")
        self.assertEqual(bounded_restore(""), "")

    def test_estimate_tokens_monotonic(self):
        self.assertEqual(estimate_tokens(""), 0)
        self.assertGreater(estimate_tokens("x" * 400), estimate_tokens("x" * 40))


if __name__ == "__main__":
    unittest.main()
