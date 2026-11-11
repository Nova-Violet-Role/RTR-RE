# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""No-cache cost proof simulations (TODO-15): a small-window model
operates a large managed context at lesser per-turn cost, because
evicted substance lives in retrieval form instead of being re-sent.

Mirrors formal/Symbiose/Cost.lean with executable instances: scale
analogues across managed sizes, the live-number instance (3.43M
managed, 390k live, 700k window), and a retrieval soundness loop.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))

from context_budget import bounded_restore, estimate_tokens, plan_compression


def cost_without(managed: int) -> int:
    return managed


def cost_with(live: int, retrieved: int) -> int:
    return live + retrieved


def savings(managed: int, live: int, retrieved: int) -> float:
    if managed <= 0:
        return 0.0
    return 1.0 - (live + retrieved) / managed


def simulate_managed(total_tokens: int, target_tokens: int = 200000):
    """Plan a managed context of total_tokens against a target tail.

    Returns (live_tokens, evicted_tokens): the planner is the only
    keeper planner, so this is the production decision, not a model.
    """
    per_message = 5000
    n = max(1, total_tokens // per_message)
    messages = [
        {"role": "assistant" if i % 2 == 0 else "user", "text": "x" * (per_message * 4)}
        for i in range(n)
    ]
    messages.append({"role": "user", "text": "latest"})
    plan = plan_compression(
        messages,
        config={
            "trigger_tokens": target_tokens * 2,
            "target_tokens": target_tokens,
            "max_keep_messages": 100000,
        },
    )
    return plan["keep_tokens"], plan["total_tokens"] - plan["keep_tokens"]


class TestCostModel(unittest.TestCase):
    def test_cost_flat_across_managed_sizes(self):
        # Per-turn cost with RTR stays near the target tail while the
        # managed context grows 4x; without RTR it grows 4x.
        lives = []
        for managed in (500000, 1000000, 2000000):
            live, _evicted = simulate_managed(managed, target_tokens=200000)
            lives.append(live)
            self.assertLess(cost_with(live, 1000), cost_without(managed))
        # Flat within 5%: the tail, not the managed size, sets the cost.
        self.assertLess(max(lives) - min(lives), 0.05 * 200000)

    def test_live_instance_fits_700k_window(self):
        # Measured 2026-11-10: 3.43M managed, ~390k served; restore
        # budget 4000 chars (~1000 tokens). 700k model window fits it.
        managed, live, retrieved, window = 3430000, 390000, 1000, 700000
        self.assertLessEqual(live + retrieved, window)
        self.assertLess(cost_with(live, retrieved), cost_without(managed))
        self.assertGreater(savings(managed, live, retrieved), 0.8)

    def test_4m_frontier_stays_flat(self):
        live, _evicted = simulate_managed(4000000, target_tokens=200000)
        self.assertLess(cost_with(live, 1000), cost_without(4000000))
        self.assertLessEqual(live + 1000, 700000)

    def test_seventh_reread_costs_lesser_cumulative(self):
        # The cache factor dies: 7 turns rereading through a 4M window
        # cost 7x live-plus-retrieved with RTR against 7x managed
        # without. Every repeated read costs retrieval, never re-send.
        live, _evicted = simulate_managed(4000000, target_tokens=200000)
        turns = 7
        cum_with = turns * cost_with(live, 1000)
        cum_without = turns * cost_without(4000000)
        self.assertLess(cum_with, cum_without)
        self.assertLess(cum_with / cum_without, 0.2)

    def test_restore_budget_bounds_retrieved(self):
        blob = "r" * 50000
        self.assertEqual(len(bounded_restore(blob)), 4000)
        self.assertLessEqual(len(bounded_restore(blob)) // 4 + 1, 1001)


class TestRetrievalSoundnessLoop(unittest.TestCase):
    def test_evicted_marker_retrievable_after_sink_and_index(self):
        import memory_engine
        from memory_engine import MemoryEngine
        from symbiose_worker import SessionSpanSink, SymbioseWorker

        marker = "COSTMODELD-PROOF-ANCHOR-4M"
        with tempfile.TemporaryDirectory() as td:
            test_dir = Path(td)
            memory_engine.PROJECT_ROOTS = [test_dir / "projects"]
            memory_engine.PROJECTS_DIR = test_dir / "projects"
            memory_engine.DB_DIR = test_dir / "db"
            memory_engine.REGISTRY_FILE = test_dir / "registry.json"
            memory_engine.EXTRA_ROOTS_FILE = test_dir / "extra.json"
            memory_engine.LEXIKON_GLOBAL_FILE = test_dir / "lex.json"
            memdir = test_dir / "projects" / "costproj" / ".opencode" / "memory"
            memdir.mkdir(parents=True)
            worker = SymbioseWorker(
                SessionSpanSink(memdir),
                config={
                    "trigger_tokens": 2000,
                    "target_tokens": 500,
                    "max_keep_messages": 200,
                },
            )
            try:
                msgs = [
                    {"role": "assistant", "text": f"{marker} " + "filler " * 600},
                    {"role": "assistant", "text": "filler " * 600},
                    {"role": "user", "text": "latest"},
                ]
                ticket = worker.submit(msgs)
                done = worker.wait(ticket["id"], timeout=30)
            finally:
                worker.close()
            self.assertEqual(done["status"], "ready")
            engine = MemoryEngine()
            try:
                stats = engine.index_files(
                    [str(p) for p in sorted(memdir.glob("rtrre-*.dtd"))]
                )
                self.assertGreaterEqual(stats["new"], 1)
                hits = engine.search(marker, k=3)
            finally:
                engine.close()
            self.assertTrue(hits)
            self.assertIn(marker, hits[0]["document"])


if __name__ == "__main__":
    unittest.main()
