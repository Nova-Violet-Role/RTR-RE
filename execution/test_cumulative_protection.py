# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Acceptance: cumulative counter persistence, fail-closed corrupt state, recency-aware protection."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "execution"))

from context_budget import plan_compression  # noqa: E402
from symbiose_worker import SessionSpanSink, SymbioseWorker  # noqa: E402


def _msg(role, text, tool=None):
    m = {"role": role, "text": text}
    if tool:
        m["tool"] = tool
    return m


class TestCumulativeCounter(unittest.TestCase):
    def test_counter_persists_across_sessions(self):
        with tempfile.TemporaryDirectory(prefix="rtrre-test-cum-") as td:
            td = Path(td)
            state = td / "cumulative.json"
            sink_dir = td / "sink"
            w1 = SymbioseWorker(
                SessionSpanSink(sink_dir), cooldown_seconds=0, cumulative_path=state
            )
            t = w1.submit([_msg("assistant", "a"), _msg("assistant", "b")])
            w1.wait(int(t["id"]), timeout=10)
            w1.close()
            self.assertEqual(json.loads(state.read_text())["cumulative_messages"], 2)
            w2 = SymbioseWorker(
                SessionSpanSink(sink_dir), cooldown_seconds=0, cumulative_path=state
            )
            self.assertEqual(w2._cumulative_messages, 2)
            t = w2.submit([_msg("user", "q")])
            w2.wait(int(t["id"]), timeout=10)
            w2.close()
            self.assertEqual(json.loads(state.read_text())["cumulative_messages"], 3)

    def test_cache_hit_does_not_double_count(self):
        with tempfile.TemporaryDirectory(prefix="rtrre-test-cum-") as td:
            td = Path(td)
            state = td / "cumulative.json"
            sink_dir = td / "sink"
            cfg = {"trigger_tokens": 100, "target_tokens": 30, "max_keep_messages": 2}
            worker = SymbioseWorker(
                SessionSpanSink(sink_dir),
                cooldown_seconds=0,
                cumulative_path=state,
                config=cfg,
            )
            msgs = [_msg("assistant", "x" * 12000), _msg("user", "q")]
            t1 = worker.submit(msgs)
            worker.wait(int(t1["id"]), timeout=10)
            before = worker._cumulative_messages
            t2 = worker.submit(msgs)
            after = worker._cumulative_messages
            worker.close()
            self.assertEqual(t2.get("status"), "cached")
            self.assertEqual(after, before)

    def test_corrupt_state_refuses_to_start(self):
        with tempfile.TemporaryDirectory(prefix="rtrre-test-cum-") as td:
            td = Path(td)
            state = td / "cumulative.json"
            state.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                SymbioseWorker(
                    SessionSpanSink(td / "sink"),
                    cooldown_seconds=0,
                    cumulative_path=state,
                )

    def test_no_tmp_leftovers_after_writes(self):
        with tempfile.TemporaryDirectory(prefix="rtrre-test-cum-") as td:
            td = Path(td)
            state = td / "cumulative.json"
            worker = SymbioseWorker(
                SessionSpanSink(td / "sink"),
                cooldown_seconds=0,
                cumulative_path=state,
            )
            t = worker.submit([_msg("assistant", "a")])
            worker.wait(int(t["id"]), timeout=10)
            worker.close()
            self.assertEqual(list(td.glob("*.tmp")), [])


class TestRecencyAwareProtection(unittest.TestCase):
    def setUp(self):
        self.messages = [_msg("assistant", "x" * 12000)] * 10
        self.messages[0]["tool"] = "todowrite"  # old
        self.messages[9]["tool"] = "todowrite"  # recent
        self.messages.append(_msg("user", "latest question"))
        self.cfg = {"trigger_tokens": 100, "target_tokens": 30, "max_keep_messages": 3}

    def test_below_threshold_protects_all(self):
        plan = plan_compression(
            self.messages, config={**self.cfg, "cumulative_messages": 999}
        )
        keep = {int(i) for i in plan["keep"]}
        self.assertIn(0, keep)
        self.assertIn(9, keep)

    def test_at_threshold_evicts_old_keeps_recent(self):
        plan = plan_compression(
            self.messages, config={**self.cfg, "cumulative_messages": 1000}
        )
        keep = {int(i) for i in plan["keep"]}
        self.assertNotIn(0, keep)
        self.assertIn(9, keep)

    def test_above_threshold_same_contract(self):
        plan = plan_compression(
            self.messages, config={**self.cfg, "cumulative_messages": 5000}
        )
        keep = {int(i) for i in plan["keep"]}
        self.assertNotIn(0, keep)
        self.assertIn(9, keep)

    def test_no_cumulative_key_backward_compatible(self):
        plan = plan_compression(self.messages, config=self.cfg)
        keep = {int(i) for i in plan["keep"]}
        self.assertIn(0, keep)
        self.assertIn(9, keep)


if __name__ == "__main__":
    unittest.main()
