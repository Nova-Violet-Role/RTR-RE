# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import tempfile
import time
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))

from context_budget import symbiose_config
from symbiose_worker import SessionSpanSink, SymbioseWorker, format_duration_ms


def big_messages(n=110):
    msgs = []
    for i in range(n):
        role = "assistant" if i % 3 else "user"
        msgs.append({"role": role, "text": f"span-{i} " + "x" * 16000})
    msgs.append({"role": "user", "text": "latest"})
    return msgs


class TestSymbioseConfig(unittest.TestCase):
    def test_defaults_are_mugen_public_profile(self):
        cfg = symbiose_config({})
        self.assertEqual(cfg["preset"], "re-symbiose-mugen")
        self.assertEqual(cfg["preset_display"], "Re-Symbiose-Mugen")
        self.assertEqual(cfg["compute_preset"], "rtr-full/t4/p60")
        self.assertEqual(cfg["modality"], "rtr-full")
        self.assertEqual(cfg["threads_per_model"], 4)
        self.assertEqual(cfg["parking_percent"], 60)
        self.assertEqual(
            cfg["profile_label"], "Re-Symbiose-Mugen · RTR-FULL · T4 · P60"
        )
        self.assertEqual(cfg["profile_code"], "re-symbiose-mugen/rtr-full/t4/p60")
        self.assertEqual(cfg["trigger_tokens"], 400000)
        self.assertEqual(cfg["target_tokens"], 200000)
        self.assertEqual(cfg["max_keep_messages"], 200)
        self.assertEqual(cfg["max_summary_chars"], 20000)
        self.assertEqual(cfg["max_restore_chars"], 4000)
        self.assertEqual(cfg["sources"]["trigger_tokens"], "preset:re-symbiose-mugen")

    def test_local_system_profile_uses_mugen_at_t8_p80(self):
        cfg = symbiose_config({"OPENCODE_MEMORY_RTR_PRESET_PROFILE": "local-system"})
        self.assertEqual(cfg["preset"], "re-symbiose-mugen")
        self.assertEqual(cfg["compute_preset"], "rtr-full/t8/p80")
        self.assertEqual(cfg["threads_per_model"], 8)
        self.assertEqual(cfg["parking_percent"], 80)
        self.assertEqual(
            cfg["profile_label"], "Re-Symbiose-Mugen · RTR-FULL · T8 · P80"
        )
        self.assertEqual(cfg["profile_code"], "re-symbiose-mugen/rtr-full/t8/p80")

    def test_env_overrides(self):
        cfg = symbiose_config(
            {
                "OPENCODE_MEMORY_RTRRE_TRIGGER": "210000",
                "OPENCODE_MEMORY_RTRRE_TARGET": "90000",
            }
        )
        self.assertEqual(cfg["trigger_tokens"], 210000)
        self.assertEqual(cfg["target_tokens"], 90000)
        self.assertEqual(cfg["sources"]["target_tokens"], "env")

    def test_invalid_refused_by_name(self):
        with self.assertRaises(ValueError) as cm:
            symbiose_config({"OPENCODE_MEMORY_RTRRE_TARGET": "450000"})
        self.assertIn("TARGET", str(cm.exception))
        with self.assertRaises(ValueError):
            symbiose_config({"OPENCODE_MEMORY_RTRRE_TRIGGER": "abc"})
        with self.assertRaises(ValueError):
            symbiose_config({"OPENCODE_MEMORY_RTRRE_MAX_KEEP": "0"})


class TestSymbioseWorker(unittest.TestCase):
    def test_submit_never_pauses_live_turn(self):
        seen = []

        def slow_sink(spans):
            time.sleep(0.6)
            seen.extend(spans)
            return "ok"

        w = SymbioseWorker(slow_sink)
        try:
            t0 = time.perf_counter()
            ticket = w.submit(big_messages())
            elapsed = time.perf_counter() - t0
            self.assertLess(elapsed, 0.25, f"submit blocked {elapsed:.3f}s")
            done = w.wait(ticket["id"], timeout=5)
            self.assertEqual(done["status"], "ready")
            self.assertTrue(seen)
            lanes = {s["lane"] for s in seen}
            self.assertEqual(lanes, {"read", "written"})
        finally:
            w.close()

    def test_hash_cache_sinks_once(self):
        calls = []
        w = SymbioseWorker(lambda spans: calls.append(spans) or "ok")
        try:
            msgs = big_messages()
            a = w.submit(msgs)
            w.wait(a["id"], timeout=5)
            b = w.submit(msgs)
            self.assertEqual(b["status"], "cached")
            self.assertEqual(len(calls), 1)
        finally:
            w.close()

    def test_failure_enters_cooldown(self):
        def boom(spans):
            raise RuntimeError("sink down")

        w = SymbioseWorker(boom, cooldown_seconds=60)
        try:
            a = w.submit(big_messages())
            done = w.wait(a["id"], timeout=5)
            self.assertEqual(done["status"], "failed")
            b = w.submit(big_messages(95))
            self.assertEqual(b["status"], "cooldown")
        finally:
            w.close()

    def test_ready_ticket_reports_calibration_timing(self):
        def slow_sink(spans):
            time.sleep(0.12)
            return "ok"

        w = SymbioseWorker(slow_sink)
        try:
            ticket = w.submit(big_messages())
            self.assertIn("submit_ms", ticket)
            self.assertGreaterEqual(ticket["submit_ms"], 0.0)
            done = w.wait(ticket["id"], timeout=5)
            self.assertEqual(done["status"], "ready")
            for field in (
                "queue_ms",
                "plan_ms",
                "sink_ms",
                "elapsed_ms",
                "duration",
                "total_tokens",
                "keep_tokens",
                "evicted_tokens",
                "input_chars",
                "evict_chars",
                "tokens_per_second",
            ):
                self.assertIn(field, done, field)
            self.assertGreaterEqual(done["sink_ms"], 100.0)
            self.assertGreaterEqual(done["elapsed_ms"], done["sink_ms"])
            self.assertGreater(done["tokens_per_second"], 0.0)
            self.assertEqual(
                done["evicted_tokens"], done["total_tokens"] - done["keep_tokens"]
            )
        finally:
            w.close()

    def test_duration_formats_ms_seconds_and_minutes(self):
        self.assertEqual(format_duration_ms(12.345), "12.3 ms")
        self.assertEqual(format_duration_ms(1500), "1.500 s")
        self.assertEqual(format_duration_ms(65_000), "1 min 5.000 s")
        self.assertEqual(format_duration_ms(3_661_000), "61 min 1.000 s")

    def test_completed_ticket_store_is_bounded(self):
        w = SymbioseWorker(lambda spans: "ok", max_retained_tickets=3)
        try:
            ids = []
            for i in range(6):
                t = w.submit([{"role": "user", "text": f"distinct-{i}"}])
                done = w.wait(t["id"], timeout=5)
                self.assertEqual(done["status"], "ready")
                ids.append(t["id"])
            # Oldest completed tickets are evicted, newest retained.
            self.assertEqual(w.poll(ids[0])["status"], "unknown")
            self.assertEqual(w.poll(ids[-1])["status"], "ready")
            # Cache eviction rides along: resubmitting evicted content is
            # fresh work under a new id, never a stale cache hit.
            again = w.submit([{"role": "user", "text": "distinct-0"}])
            self.assertNotEqual(again["status"], "cached")
            self.assertNotEqual(again["id"], ids[0])
            w.wait(again["id"], timeout=5)
        finally:
            w.close()

    def test_close_fails_queued_tickets_instead_of_leaving_pending(self):
        import threading

        release = threading.Event()

        def blocking_sink(spans):
            release.wait(timeout=5)
            return "ok"

        w = SymbioseWorker(blocking_sink)
        first = w.submit(big_messages())
        second = w.submit(big_messages(95))
        threading.Timer(0.3, release.set).start()
        w.close()
        self.assertEqual(w.poll(first["id"])["status"], "ready")
        queued = w.poll(second["id"])
        self.assertEqual(queued["status"], "failed")
        self.assertIn("closed", queued["error"])

    def test_submit_after_close_reports_failed_not_pending(self):
        w = SymbioseWorker(lambda spans: "ok")
        w.close()
        ticket = w.submit([{"role": "user", "text": "too late"}])
        self.assertEqual(ticket["status"], "failed")
        self.assertIn("closed", ticket["error"])
        self.assertEqual(w.poll(ticket["id"])["status"], "failed")

    def test_input_never_mutated(self):
        import copy

        msgs = big_messages()
        before = copy.deepcopy(msgs)
        w = SymbioseWorker(lambda spans: "ok")
        try:
            t = w.submit(msgs)
            w.wait(t["id"], timeout=5)
            self.assertEqual(msgs, before)
        finally:
            w.close()


class TestSessionSpanSink(unittest.TestCase):
    def test_both_lanes_written_verbatim_typed(self):
        with tempfile.TemporaryDirectory() as td:
            sink = SessionSpanSink(Path(td))
            spans = [
                {
                    "index": 0,
                    "role": "user",
                    "lane": "read",
                    "dtype": "PCDATA",
                    "text": "read this exactly",
                },
                {
                    "index": 1,
                    "role": "assistant",
                    "lane": "written",
                    "dtype": "CDATA",
                    "text": "`code_token` stays",
                },
                {
                    "index": 2,
                    "role": "assistant",
                    "lane": "written",
                    "dtype": "NDATA",
                    "text": "[NDATA]",
                },
            ]
            path = sink(spans)
            self.assertTrue(str(path).endswith(".dtd"))
            raw = Path(path).read_bytes()
            self.assertNotIn(b"\r", raw)
            body = raw.decode("utf-8")
            # DTD-shaped schema (architectural form, TODO-70)
            self.assertIn("<!ELEMENT span EMPTY>", body)
            self.assertIn("role (user|assistant|tool) #REQUIRED", body)
            self.assertIn("lane (read|write|think|plan|unknown) #IMPLIED", body)
            self.assertIn("dtype (CDATA|NDATA) #IMPLIED", body)
            # verbatim content survives
            self.assertIn("read this exactly", body)
            self.assertIn("`code_token` stays", body)
            # architectural attributes on the span element
            self.assertIn('<span id="span-0" role="user" lane="read"', body)
            self.assertIn('<span id="span-1" role="assistant" lane="written"', body)
            self.assertIn('dtype="CDATA"', body)
            self.assertIn('dtype="NDATA"', body)
            self.assertIn("</span>", body)

    def test_sink_writes_dtd_extension_and_schema_first(self):
        with tempfile.TemporaryDirectory() as td:
            sink = SessionSpanSink(Path(td))
            path = sink([{"index": 0, "role": "user", "text": "hi"}])
            body = Path(path).read_text(encoding="utf-8")
            # schema block precedes content
            self.assertLess(body.index("<!ELEMENT span"), body.index("<span id="))

    def test_sink_writes_paraphrase_companion_with_anchors(self):
        with tempfile.TemporaryDirectory() as td:
            sink = SessionSpanSink(Path(td))
            path = sink(
                [
                    {
                        "index": 0,
                        "role": "assistant",
                        "lane": "written",
                        "dtype": "CDATA",
                        "text": "First line anchor.\nSecond line.",
                    },
                    {
                        "index": 1,
                        "role": "user",
                        "lane": "read",
                        "dtype": "CDATA",
                        "text": "x" * 300,
                    },
                ],
                digest="abcd",
            )
            summary = Path(td) / "rtrre-summary-abcd.dtd"
            self.assertTrue(summary.exists())
            body = summary.read_text(encoding="utf-8")
            self.assertIn("<!ELEMENT paraphrase EMPTY>", body)
            self.assertIn("spanref IDREF #REQUIRED", body)
            self.assertIn(
                '<paraphrase spanref="span-0" text="First line anchor."', body
            )
            self.assertIn("…", body)  # truncated long anchor

    def test_glossary_dtd_written_by_lexikon_build(self):
        import sys

        sys.path.insert(0, str(Path(__file__).parent))
        from memory_engine import MemoryEngine

        engine = MemoryEngine()
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "proj"
            project.mkdir()
            (project / "state").mkdir()
            (project / "state" / "lexikon.json").write_text(
                '{"terms": {}}', encoding="utf-8"
            )
            res = engine.build_lexikon(str(project))
            glossary = project / ".opencode" / "memory" / "rtrre-glossary.dtd"
            self.assertTrue(glossary.exists(), res)
            body = glossary.read_text(encoding="utf-8")
            self.assertIn("<!ELEMENT glossaryentry EMPTY>", body)

    def test_engine_chunks_dtd_span_with_inventory_header(self):
        import sys

        sys.path.insert(0, str(Path(__file__).parent))
        from memory_engine import MemoryEngine

        engine = MemoryEngine()
        with tempfile.TemporaryDirectory() as td:
            sink = SessionSpanSink(Path(td))
            path = sink(
                [
                    {
                        "index": 0,
                        "role": "assistant",
                        "lane": "written",
                        "dtype": "CDATA",
                        "text": "the keeper memory is infinite",
                    }
                ],
                digest="abc123",
            )
            chunks = engine.chunk_dtd_whole(Path(path), "rtrre-abc123.dtd")
            self.assertTrue(chunks)
            text = chunks[0]["text"]
            self.assertIn("ATTLIST", text)
            self.assertIn("role", text)
            self.assertIn("the keeper memory is infinite", text)


if __name__ == "__main__":
    unittest.main()
