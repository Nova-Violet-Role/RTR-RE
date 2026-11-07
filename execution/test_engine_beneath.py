# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Acceptance: Engine Beneath produces a non-mutating lineage record."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "eval"))

from engine_beneath import (  # noqa: E402
    build_lineage,
    evaluate_conversation,
    evaluate_retrieval,
)


def msg(role, text, tool=None):
    value = {"role": role, "text": text}
    if tool:
        value["tool"] = tool
    return value


class TestEngineBeneath(unittest.TestCase):
    def test_lineage_records_each_message_without_mutating_input(self):
        messages = [msg("assistant", "early " + "x" * 12000) for _ in range(3)]
        messages.append(msg("user", "latest question"))
        before = [dict(m) for m in messages]

        lineage = build_lineage(
            messages,
            config={
                "trigger_tokens": 100,
                "target_tokens": 40,
                "max_keep_messages": 2,
            },
        )

        self.assertEqual(messages, before)
        self.assertEqual([m["index"] for m in lineage["messages"]], [0, 1, 2, 3])
        self.assertEqual(lineage["summary"]["total_messages"], 4)
        self.assertTrue(all("text" not in m for m in lineage["messages"]))
        self.assertTrue(all("sha256" in m for m in lineage["messages"]))
        self.assertEqual(
            {m["disposition"] for m in lineage["messages"]},
            {"retained", "evicted"},
        )

    def test_evaluation_traces_messages_into_the_real_sink(self):
        marker = "ENGINE-BENEATH-HARBOR-731"
        # Long but CDATA (spaces break the 64+ unbroken-run NDATA regex), so
        # the marker survives verbatim in the DTD-shaped sink (TODO-70).
        long_cdata = (marker + " the keeper memory is infinite and retrievable. ") * 60
        messages = [
            msg("assistant", long_cdata),
            msg("assistant", "protected skill record", tool="skill"),
            msg("assistant", "recent " + "y" * 12000),
            msg("user", "latest question"),
        ]
        before = [dict(m) for m in messages]

        result = evaluate_conversation(
            messages,
            config={
                "trigger_tokens": 100,
                "target_tokens": 40,
                "max_keep_messages": 3,
            },
            markers=[marker],
        )

        self.assertEqual(messages, before)
        self.assertEqual(result["schema"], "rtr-re.engine-beneath/v1")
        self.assertEqual(result["checks"]["all_messages_accounted"], 1.0)
        self.assertEqual(result["checks"]["protected_retained"], 1.0)
        self.assertEqual(result["checks"]["sink_contains_evicted_spans"], 1.0)
        self.assertEqual(result["checks"]["marker_in_evicted_sink"], 1.0)
        self.assertEqual(result["checks"]["marker_absent_from_kept_tail"], 1.0)
        self.assertEqual(result["verdict"], "pass")

    def test_below_trigger_is_identity_without_an_artificial_pass(self):
        messages = [
            msg("user", "small"),
            msg("assistant", "still small"),
        ]

        result = evaluate_conversation(messages)

        self.assertEqual(result["lineage"]["summary"]["compress"], False)
        self.assertEqual(result["lineage"]["summary"]["evicted_messages"], 0)
        self.assertEqual(result["checks"]["context_reduction"], 0.0)
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["sink"]["span_markers"], 0)

    def test_tool_pair_stays_together_across_the_cut(self):
        messages = [
            msg("assistant", "old " + "x" * 12000),
            msg("assistant", "old " + "x" * 12000),
            {"role": "assistant", "text": "call", "tool": "read", "tokens": 10},
            {"role": "tool", "text": "result", "tool_call": True, "tokens": 10},
            msg("user", "latest question"),
        ]

        lineage = build_lineage(
            messages,
            config={
                "trigger_tokens": 100,
                "target_tokens": 30,
                "max_keep_messages": 3,
            },
        )

        kept = set(lineage["plan"]["keep"])
        self.assertIn(2, kept)
        self.assertIn(3, kept)
        self.assertEqual(lineage["messages"][2]["disposition"], "retained")
        self.assertEqual(lineage["messages"][3]["disposition"], "retained")

    def test_ndata_is_masked_before_the_sink_verbatim_judgment(self):
        blob = "QUJD" * 40
        messages = [
            msg("assistant", f"payload {blob} " + "x" * 12000),
            msg("assistant", "recent " + "y" * 12000),
            msg("user", "latest question"),
        ]

        result = evaluate_conversation(
            messages,
            config={
                "trigger_tokens": 100,
                "target_tokens": 30,
                "max_keep_messages": 2,
            },
        )

        self.assertEqual(result["checks"]["evicted_verbatim_after_ndata_masking"], 1.0)
        self.assertEqual(result["lineage"]["messages"][0]["dtype"], "NDATA")

    def test_retrieval_ranks_returned_documents_without_keeping_query_results(self):
        queries = [
            {
                "id": "harbor-marker",
                "text": "which harbor marker was preserved?",
                "expected_terms": ["ENGINE-BENEATH-HARBOR-731"],
            },
            {
                "id": "missing-marker",
                "text": "which absent marker was preserved?",
                "expected_terms": ["ENGINE-BENEATH-ABSENT-000"],
            },
        ]
        documents = [
            {
                "id": "chunk-2",
                "document": "ENGINE-BENEATH-HARBOR-731",
                "metadata": {"rel_path": "directives/sessions/rtrre-test.md"},
                "score": 0.91,
            },
            {
                "id": "chunk-1",
                "document": "ordinary project note",
                "metadata": {"rel_path": "directives/note.md"},
                "score": 0.42,
            },
        ]

        def search(query, k):
            if "harbor" in query:
                return list(reversed(documents))[:k]
            return documents[1:]

        result = evaluate_retrieval(search, queries, depths=[1, 5])

        self.assertEqual(result["schema"], "rtr-re.engine-beneath.retrieval/v1")
        self.assertEqual(result["summary"]["recall_at"][1], 0.0)
        self.assertEqual(result["summary"]["recall_at"][5], 0.5)
        self.assertEqual(result["summary"]["mean_reciprocal_rank"], 0.25)
        first = result["queries"][0]
        self.assertEqual(first["first_hit_rank"], 2)
        self.assertEqual(first["returned_ids"], ["chunk-1", "chunk-2"])
        self.assertNotIn("document", first)


if __name__ == "__main__":
    unittest.main()
