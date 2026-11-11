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
    CPU_PROFILE_ENV,
    bounded_restore,
    estimate_tokens,
    plan_compression,
    resolve_retrieval_profile,
    span_lane,
)


def msg(role, text, tool=None):
    m = {"role": role, "text": text}
    if tool:
        m["tool"] = tool
    return m


class TestContextBudget(unittest.TestCase):
    def test_constants_match_plan(self):
        # Public default is Re-Symbiose-Mugen: verbatim to 400k, 200k tail.
        self.assertEqual(TARGET_TOKENS, 200000)
        self.assertEqual(TRIGGER_TOKENS, 400000)
        self.assertEqual(MAX_KEEP_MESSAGES, 200)
        self.assertEqual(MAX_SUMMARY_CHARS, 20000)

    def test_cpu_profile_source_reports_env_when_explicit(self):
        profile = resolve_retrieval_profile({CPU_PROFILE_ENV: "local-system"})
        self.assertEqual(profile["cpu_profile"], "local-system")
        self.assertEqual(profile["sources"]["cpu_profile"], "env")
        defaulted = resolve_retrieval_profile({})
        self.assertEqual(
            defaulted["sources"]["cpu_profile"],
            f"cpu-profile:{defaulted['cpu_profile']}",
        )

    def test_thinking_parts_count_and_sink(self):
        thinker = {
            "role": "assistant",
            "parts": [{"type": "reasoning", "reasoning": "deliberate " * 2000}],
        }
        msgs = [thinker, msg("user", "hi")]
        plan = plan_compression(
            msgs, trigger_tokens=100, target_tokens=50, max_keep_messages=200
        )
        self.assertGreater(plan["total_tokens"], 1000)
        self.assertTrue(plan["compress"])
        self.assertEqual(plan["evict_payload"][0]["lane"], "think")
        self.assertIn("deliberate", plan["evict_payload"][0]["text"])

    def test_think_lane_for_thinking_only_messages(self):
        only = {
            "role": "assistant",
            "parts": [{"type": "reasoning", "reasoning": "hmm"}],
        }
        mixed = {
            "role": "assistant",
            "text": "answer",
            "parts": [{"type": "reasoning", "reasoning": "hmm"}],
        }
        plain = {"role": "assistant", "text": "answer"}
        self.assertEqual(span_lane(only), "think")
        self.assertEqual(span_lane(mixed), "written")
        self.assertEqual(span_lane(plain), "written")

    def test_below_trigger_is_noop(self):
        msgs = [msg("user", "hello"), msg("assistant", "hi")]
        plan = plan_compression(msgs)
        self.assertFalse(plan["compress"])
        self.assertEqual(plan["keep"], [0, 1])
        self.assertEqual(plan["evict"], [])

    def test_plan_reports_loop_bound_target_with_zero_overrun(self):
        msgs = [msg("user", "x" * 400) for _ in range(11)]
        plan = plan_compression(
            msgs, trigger_tokens=1000, target_tokens=400, max_keep_messages=40
        )
        self.assertEqual(plan["loop_bound"], "target")
        self.assertEqual(plan["overrun_tokens"], 0)
        self.assertEqual(plan["overrun_by"], "none")

    def test_plan_reports_loop_bound_max_keep(self):
        msgs = [msg("user", "x" * 40) for _ in range(120)]
        plan = plan_compression(
            msgs, trigger_tokens=1000, target_tokens=400, max_keep_messages=40
        )
        self.assertEqual(plan["loop_bound"], "maxKeep")
        self.assertEqual(plan["overrun_tokens"], 0)
        self.assertEqual(plan["overrun_by"], "none")

    def test_plan_reports_protection_overrun_in_protect_all_mode(self):
        # Unbounded overrun accounting lives here (young session, nothing
        # archived yet); gated-mode capping is pinned by the budget tests.
        msgs = []
        for i in range(40):
            if 25 <= i <= 35:
                msgs.append(msg("tool", "x" * 40, tool="todowrite"))
            else:
                msgs.append(msg("user", "x" * 40))
        for _ in range(20):
            msgs.append(msg("user", "x" * 1200))
        plan = plan_compression(
            msgs,
            trigger_tokens=1000,
            target_tokens=400,
            max_keep_messages=40,
            config={"cumulative_messages": 500},
        )
        self.assertEqual(plan["loop_bound"], "target")
        # 11 todowrite pulls x 10 tokens (40 chars, no envelope on
        # top-level text) = 110.
        self.assertEqual(plan["overrun_tokens"], 110)
        self.assertEqual(plan["overrun_by"], "protection")

    def test_protection_budget_caps_gap_pulls_newest_first(self):
        msgs = []
        for i in range(60):
            if 20 <= i < 50:
                msgs.append(msg("tool", "x" * 40, tool="todowrite"))
            elif i < 20:
                msgs.append(msg("user", "x" * 40))
            else:
                msgs.append(msg("user", "x" * 1200))
        plan = plan_compression(
            msgs,
            trigger_tokens=2000,
            target_tokens=400,
            max_keep_messages=40,
            config={"cumulative_messages": 5000},
        )
        # Budget 100 (25% of 400); each pull 10 tokens -> 10 newest kept.
        self.assertEqual(plan["overrun_tokens"], 100)
        self.assertEqual(plan["overrun_by"], "protection")
        for i in range(40, 50):
            self.assertIn(i, plan["keep"])
        for i in range(20, 40):
            self.assertNotIn(i, plan["keep"])

    def test_protection_budget_keeps_newest_protected_as_floor(self):
        msgs = [msg("user", "x" * 40) for _ in range(20)]
        msgs.append(msg("tool", "x" * 4000, tool="todowrite"))
        msgs.extend(msg("user", "x" * 40) for _ in range(21, 40))
        msgs.extend(msg("user", "x" * 1200) for _ in range(20))
        plan = plan_compression(
            msgs,
            trigger_tokens=2000,
            target_tokens=400,
            max_keep_messages=40,
            config={"cumulative_messages": 5000},
        )
        self.assertIn(20, plan["keep"])
        # (4000 + 3) // 4 = 1000 tokens, kept over the 100 budget as floor.
        self.assertEqual(plan["overrun_tokens"], 1000)
        self.assertEqual(plan["overrun_by"], "protection")

    def test_under_trigger_plan_reports_loop_bound_none(self):
        msgs = [msg("user", "hi"), msg("assistant", "hello")]
        plan = plan_compression(msgs)
        self.assertFalse(plan["compress"])
        self.assertEqual(plan["loop_bound"], "none")
        self.assertEqual(plan["overrun_tokens"], 0)
        self.assertEqual(plan["overrun_by"], "none")

    def test_live_baseline_triggers_ticket_floor_relief(self):
        # RRD-108: saturated window + small ticket -> compress to floor.
        msgs = [msg("user", "x" * 40) for _ in range(50)]
        plan = plan_compression(
            msgs,
            trigger_tokens=1000,
            target_tokens=400,
            config={"live_tokens": 2000},
        )
        self.assertTrue(plan["compress"])
        self.assertEqual(plan["keep"], [49])
        self.assertEqual(plan["evict"], list(range(49)))

    def test_live_baseline_shifts_ticket_budget(self):
        # Combined 1050 > trigger 1000; ticket keeps 300 of its own 950.
        msgs = [msg("user", "x" * 40) for _ in range(95)]
        plan = plan_compression(
            msgs,
            trigger_tokens=1000,
            target_tokens=400,
            config={"live_tokens": 100},
        )
        self.assertTrue(plan["compress"])
        self.assertEqual(len(plan["keep"]), 30)
        self.assertEqual(plan["keep_tokens"], 300)

    def test_absent_live_baseline_keeps_today_behavior(self):
        msgs = [msg("user", "x" * 40) for _ in range(50)]
        plan = plan_compression(msgs, trigger_tokens=1000, target_tokens=400)
        self.assertFalse(plan["compress"])
        self.assertEqual(plan["keep"], list(range(50)))

    def test_acceptance_keeps_bounded_tail(self):
        # 120 messages, each ~4500 tokens (18000 chars) = ~540k total > 400k.
        msgs = []
        for i in range(120):
            role = "user" if i % 2 == 0 else "assistant"
            msgs.append(msg(role, f"message {i} " + "x" * 18000))
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
        msgs += [msg("assistant", "y" * 18000) for _ in range(120)]
        msgs.append(msg("user", "latest question"))
        plan = plan_compression(msgs)
        self.assertTrue(plan["compress"])
        self.assertIn(0, plan["keep"])
        self.assertIn(len(msgs) - 1, plan["keep"])

    def test_ndata_masked_in_evict_payload(self):
        blob = "QUJD" * 40  # 160-char base64-like span
        msgs = [msg("assistant", f"data {blob} end " + "z" * 18000)]
        msgs += [msg("assistant", "w" * 18000) for _ in range(120)]
        msgs.append(msg("user", "go"))
        plan = plan_compression(msgs)
        evicted_text = " ".join(e["text"] for e in plan["evict_payload"])
        self.assertNotIn(blob, evicted_text)
        self.assertIn("[NDATA]", evicted_text)

    def test_tool_pairs_are_not_split_backwards(self):
        # tool result kept implies its call kept when adjacent pair straddles cut.
        msgs: list = [msg("assistant", "a" * 18000) for _ in range(120)]
        msgs.append(msg("assistant", "call", tool="read"))
        msgs.append({"role": "tool", "text": "result", "tool_call": True})
        msgs.append(msg("user", "next"))
        plan = plan_compression(msgs)
        keep = set(plan["keep"])
        if len(msgs) - 2 in keep:
            self.assertIn(len(msgs) - 3, keep)

    def test_planner_never_mutates_input(self):
        # Collision rule: one mutator per transport. The RE:Symbiose
        # planner is advisory only.
        import copy

        msgs = [msg("assistant", "q" * 18000) for _ in range(120)]
        msgs.append(msg("user", "go"))
        before = copy.deepcopy(msgs)
        plan = plan_compression(msgs)
        self.assertTrue(plan["compress"])
        self.assertEqual(msgs, before)

    def test_evicted_substance_kept_verbatim_for_index(self):
        marker = "UNIQUE-DECISION-keep-me-exactly"
        msgs = [msg("assistant", marker + " " + "v" * 18000)]
        msgs += [msg("assistant", "u" * 18000) for _ in range(120)]
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

    def test_bounded_restore(self):
        text = "r" * 9000
        self.assertEqual(len(bounded_restore(text)), 4000)
        self.assertEqual(bounded_restore("ok"), "ok")
        self.assertEqual(bounded_restore(""), "")

    def test_estimate_tokens_monotonic(self):
        self.assertEqual(estimate_tokens(""), 0)
        self.assertGreater(estimate_tokens("x" * 400), estimate_tokens("x" * 40))


class TestEvictionOrder(unittest.TestCase):
    def test_compressor_evicts_oldest_first(self):
        import context_budget

        messages = [{"role": "assistant", "text": "y" * 400} for _ in range(10)] + [
            {"role": "user", "text": "go"}
        ]
        plan = context_budget.plan_compression(
            messages,
            config={
                "trigger_tokens": 500,
                "target_tokens": 200,
                "max_keep_messages": 40,
                "cumulative_messages": 0,
            },
        )
        self.assertTrue(plan["compress"])
        evict = plan["evict"]
        self.assertEqual(sorted(evict), evict)
        self.assertEqual(evict[0], 0)
        for i in range(1, len(evict)):
            self.assertEqual(evict[i], evict[i - 1] + 1)


if __name__ == "__main__":
    unittest.main()
