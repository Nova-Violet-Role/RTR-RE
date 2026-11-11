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


def wordy_messages(n=20, marker=""):
    msgs = []
    for i in range(n):
        role = "assistant" if i % 3 else "user"
        msgs.append({"role": role, "text": f"span-{i} {marker} " + "word " * 100})
    msgs.append({"role": "user", "text": f"latest {marker}"})
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
    def test_zero_max_queue_is_refused(self):
        with self.assertRaises(ValueError):
            SymbioseWorker(lambda spans: "ok", max_queue=0)

    def test_worker_sinks_thinking_parts_verbatim(self):
        with tempfile.TemporaryDirectory() as td:
            sink = SessionSpanSink(Path(td))
            w = SymbioseWorker(
                sink,
                config={
                    "trigger_tokens": 100,
                    "target_tokens": 50,
                    "max_keep_messages": 200,
                },
            )
            try:
                thinker = {
                    "role": "assistant",
                    "parts": [{"type": "reasoning", "reasoning": "deliberate " * 2000}],
                }
                ticket = w.submit([thinker, {"role": "user", "text": "hi"}])
                done = w.wait(ticket["id"], timeout=5)
                self.assertEqual(done["status"], "ready")
                body = Path(done["sink"]).read_text(encoding="utf-8")
                self.assertIn("deliberate", body)
                self.assertIn('lane="think"', body)
            finally:
                w.close()

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

    def test_ticket_plans_against_keeper_live_baseline(self):
        # RRD-108/116: saturated keeper window -> small ticket compresses
        # to floor. Wiring test: fail-open masks a broken read, so the
        # status-present path must prove the read happened.
        import json

        with tempfile.TemporaryDirectory() as td:
            opencode = Path(td) / ".opencode"
            opencode.mkdir(parents=True)
            (opencode / "rtr-re-keeper-status.json").write_text(
                json.dumps({"keepTokens": 350000}), encoding="utf-8"
            )
            seen = []
            w = SymbioseWorker(
                lambda spans: seen.extend(spans) or "ok",
                config={"trigger_tokens": 1000, "target_tokens": 400},
                cumulative_path=opencode / "rtr-re-cumulative.json",
            )
            try:
                msgs = [{"role": "user", "text": "x" * 40} for _ in range(50)]
                ticket = w.submit(msgs)
                done = w.wait(ticket["id"], timeout=5)
            finally:
                w.close()
            self.assertEqual(done["status"], "ready")
            self.assertEqual(len(seen), 49)

    def test_ticket_ignores_absent_keeper_status(self):
        with tempfile.TemporaryDirectory() as td:
            opencode = Path(td) / ".opencode"
            opencode.mkdir(parents=True)
            seen = []
            w = SymbioseWorker(
                lambda spans: seen.extend(spans) or "ok",
                config={"trigger_tokens": 1000, "target_tokens": 400},
                cumulative_path=opencode / "rtr-re-cumulative.json",
            )
            try:
                msgs = [{"role": "user", "text": "x" * 40} for _ in range(50)]
                ticket = w.submit(msgs)
                done = w.wait(ticket["id"], timeout=5)
            finally:
                w.close()
            self.assertEqual(done["status"], "ready")
            self.assertEqual(seen, [])

    def test_ticket_ignores_corrupt_keeper_status(self):
        with tempfile.TemporaryDirectory() as td:
            opencode = Path(td) / ".opencode"
            opencode.mkdir(parents=True)
            (opencode / "rtr-re-keeper-status.json").write_text(
                "{not json", encoding="utf-8"
            )
            seen = []
            w = SymbioseWorker(
                lambda spans: seen.extend(spans) or "ok",
                config={"trigger_tokens": 1000, "target_tokens": 400},
                cumulative_path=opencode / "rtr-re-cumulative.json",
            )
            try:
                msgs = [{"role": "user", "text": "x" * 40} for _ in range(50)]
                ticket = w.submit(msgs)
                done = w.wait(ticket["id"], timeout=5)
            finally:
                w.close()
            self.assertEqual(done["status"], "ready")
            self.assertEqual(seen, [])

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

    def test_overflow_submit_does_not_inflate_cumulative(self):
        # R2: rejected work must not advance the protection counter that
        # drives recency gating (weaker protection if inflated).
        import threading

        release = threading.Event()

        def blocking_sink(spans):
            release.wait(timeout=10)
            return "ok"

        w = SymbioseWorker(
            blocking_sink,
            max_queue=1,
            config={
                "trigger_tokens": 100,
                "target_tokens": 50,
                "max_keep_messages": 200,
            },
        )
        try:
            msgs = lambda tag: [
                {"role": "user", "text": f"{tag} " + "x" * 400} for _ in range(3)
            ]
            w.submit(msgs("a"))
            time.sleep(0.5)  # worker grabs A, blocks in the sink
            b = w.submit(msgs("b"))
            self.assertEqual(b["status"], "pending")
            before = w._cumulative_messages
            c = w.submit(msgs("c"))
            self.assertEqual(c["status"], "overflow")
            self.assertEqual(w._cumulative_messages, before)
        finally:
            release.set()
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
            self.assertIn("role (user|assistant|tool|system|unknown) #REQUIRED", body)
            self.assertIn("lane (read|written|think|plan|unknown) #IMPLIED", body)
            self.assertIn("dtype (PCDATA|CDATA|NDATA) #IMPLIED", body)
            # verbatim content survives
            self.assertIn("read this exactly", body)
            self.assertIn("`code_token` stays", body)
            # architectural attributes on the span element
            self.assertIn('<span id="span-0" role="user" lane="read"', body)
            self.assertIn('<span id="span-1" role="assistant" lane="written"', body)
            self.assertIn('dtype="CDATA"', body)
            self.assertIn('dtype="NDATA"', body)
            self.assertIn("</span>", body)

    def test_sink_escapes_attributes_and_covers_producer_values(self):
        with tempfile.TemporaryDirectory() as td:
            sink = SessionSpanSink(Path(td))
            spans = [
                {
                    "index": 0,
                    "role": "system",
                    "lane": "written",
                    "dtype": "PCDATA",
                    "text": 'say "hi" now',
                    "ts": 'a"b',
                    "source": "s",
                    "session": "x",
                },
            ]
            path = sink(spans, "abc123")
            body = Path(path).read_text(encoding="utf-8")
            self.assertIn("role (user|assistant|tool|system|unknown) #REQUIRED", body)
            self.assertIn("lane (read|written|think|plan|unknown) #IMPLIED", body)
            self.assertIn("dtype (PCDATA|CDATA|NDATA) #IMPLIED", body)
            self.assertIn('role="system"', body)
            self.assertIn("ts='a\"b'", body)
            self.assertNotIn('ts="a"b"', body)
            summary = Path(td) / "rtrre-summary-abc123.dtd"
            self.assertIn("text='say \"hi\" now'", summary.read_text(encoding="utf-8"))

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


class TestDrainSubmitSidecars(unittest.TestCase):
    def _keeper_messages(self, marker=""):
        return [
            {
                "info": {"id": "m0", "role": "user", "sessionID": "s1"},
                "parts": [
                    {"id": "p0", "type": "text", "text": f"old question {marker}"}
                ],
            },
            {
                "info": {"id": "m1", "role": "assistant", "sessionID": "s1"},
                "parts": [
                    {
                        "id": "p1",
                        "type": "reasoning",
                        "text": "deliberate " * 600 + marker,
                    },
                    {"id": "p2", "type": "text", "text": f"plain answer {marker}"},
                ],
            },
            {
                "info": {"id": "m2", "role": "user", "sessionID": "s1"},
                "parts": [{"id": "p3", "type": "text", "text": f"latest {marker}"}],
            },
        ]

    def _write_sidecar(self, mem, name, payload, mtime):
        import json
        import os

        path = mem / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        os.utime(path, (mtime, mtime))
        return path

    def test_drain_relays_when_spans_already_sunk(self):
        # RRD-107: keeper already sunk these spans; the drain must ack and
        # unlink WITHOUT a ticket or re-sink (no duplicates, no re-plan).
        from symbiose_worker import (
            SessionSpanSink,
            SymbioseWorker,
            drain_submit_sidecars,
        )

        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / ".opencode" / "memory"
            mem.mkdir(parents=True)
            self._write_sidecar(
                mem,
                "rtrre-aaa.submit.json",
                {"digest": "aaa", "messages": [{"a": 1}, {"b": 2}]},
                1000,
            )
            (mem / "rtrre-aaa.dtd").write_text(
                '<!-- schema -->\n<span id="span-0">\ntext\n<span id="span-1">\nmore\n',
                encoding="utf-8",
            )
            w = SymbioseWorker(SessionSpanSink(mem))
            try:
                report = drain_submit_sidecars(w, mem)
            finally:
                w.close()
            self.assertEqual(len(report["drained"]), 1)
            entry = report["drained"][0]
            self.assertTrue(entry["relayed"])
            self.assertIsNone(entry["ticket"])
            self.assertFalse((mem / "rtrre-aaa.submit.json").exists())
            self.assertTrue((mem / "rtrre-aaa.dtd").exists())
            self.assertEqual(report["left"], [])
            self.assertEqual(report["quarantined"], [])

    def test_drain_falls_back_on_span_count_mismatch(self):
        # Guard (passes pre/post): spans present but count disagrees ->
        # ticket path, never relay (fail-safe direction).
        from symbiose_worker import (
            SessionSpanSink,
            SymbioseWorker,
            drain_submit_sidecars,
        )

        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / ".opencode" / "memory"
            mem.mkdir(parents=True)
            self._write_sidecar(
                mem,
                "rtrre-aaa.submit.json",
                {"digest": "aaa", "messages": [{"a": 1}, {"b": 2}]},
                1000,
            )
            (mem / "rtrre-aaa.dtd").write_text(
                '<!-- schema -->\n<span id="span-0">\ntext\n',
                encoding="utf-8",
            )
            w = SymbioseWorker(SessionSpanSink(mem))
            try:
                report = drain_submit_sidecars(w, mem)
            finally:
                w.close()
            self.assertEqual(len(report["drained"]), 1)
            self.assertNotIn("relayed", report["drained"][0])
            self.assertIsInstance(report["drained"][0]["ticket"], int)

    def test_drain_quarantines_empty_sidecar(self):
        from symbiose_worker import (
            SessionSpanSink,
            SymbioseWorker,
            drain_submit_sidecars,
        )

        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / ".opencode" / "memory"
            mem.mkdir(parents=True)
            self._write_sidecar(
                mem, "rtrre-aaa.submit.json", {"digest": "aaa", "messages": []}, 1000
            )
            w = SymbioseWorker(SessionSpanSink(mem))
            try:
                report = drain_submit_sidecars(w, mem)
            finally:
                w.close()
            self.assertEqual(len(report["quarantined"]), 1)
            self.assertEqual(report["drained"], [])

    def test_drain_submits_sidecars_and_removes_consumed(self):
        from symbiose_worker import (
            SessionSpanSink,
            SymbioseWorker,
            drain_submit_sidecars,
        )

        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / ".opencode" / "memory"
            mem.mkdir(parents=True)
            self._write_sidecar(
                mem,
                "rtrre-aaa.submit.json",
                {
                    "digest": "aaa",
                    "ts": "2026-11-09T00:00:00Z",
                    "messages": self._keeper_messages(),
                },
                1000,
            )
            self._write_sidecar(
                mem,
                "rtrre-bbb.submit.json",
                {
                    "digest": "bbb",
                    "ts": "2026-11-09T00:00:01Z",
                    "messages": self._keeper_messages(),
                },
                2000,
            )
            w = SymbioseWorker(SessionSpanSink(mem))
            try:
                report = drain_submit_sidecars(w, mem)
            finally:
                w.close()
            self.assertEqual(len(report["drained"]), 2)
            self.assertEqual(
                [d["status"] for d in report["drained"]], ["ready", "ready"]
            )
            self.assertEqual(report["quarantined"], [])
            self.assertFalse((mem / "rtrre-aaa.submit.json").exists())
            self.assertFalse((mem / "rtrre-bbb.submit.json").exists())

    def test_drain_quarantines_invalid_sidecar_and_keeps_going(self):
        from symbiose_worker import (
            SessionSpanSink,
            SymbioseWorker,
            drain_submit_sidecars,
        )

        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / ".opencode" / "memory"
            mem.mkdir(parents=True)
            bad = mem / "rtrre-bad.submit.json"
            bad.write_text("{not json", encoding="utf-8")
            self._write_sidecar(
                mem,
                "rtrre-good.submit.json",
                {
                    "digest": "good",
                    "ts": "2026-11-09T00:00:00Z",
                    "messages": self._keeper_messages(),
                },
                2000,
            )
            w = SymbioseWorker(SessionSpanSink(mem))
            try:
                report = drain_submit_sidecars(w, mem)
            finally:
                w.close()
            self.assertEqual(len(report["quarantined"]), 1)
            self.assertIn("rtrre-bad.submit.json", report["quarantined"][0]["file"])
            self.assertTrue((mem / "rtrre-bad.submit.broken.json").exists())
            self.assertFalse(bad.exists())
            self.assertEqual(len(report["drained"]), 1)
            self.assertEqual(report["drained"][0]["status"], "ready")

    def test_drain_respects_limit_oldest_first(self):
        from symbiose_worker import (
            SessionSpanSink,
            SymbioseWorker,
            drain_submit_sidecars,
        )

        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / ".opencode" / "memory"
            mem.mkdir(parents=True)
            self._write_sidecar(
                mem,
                "rtrre-old.submit.json",
                {
                    "digest": "old",
                    "ts": "2026-11-09T00:00:00Z",
                    "messages": self._keeper_messages(),
                },
                1000,
            )
            self._write_sidecar(
                mem,
                "rtrre-mid.submit.json",
                {
                    "digest": "mid",
                    "ts": "2026-11-09T00:00:01Z",
                    "messages": self._keeper_messages(),
                },
                2000,
            )
            self._write_sidecar(
                mem,
                "rtrre-new.submit.json",
                {
                    "digest": "new",
                    "ts": "2026-11-09T00:00:02Z",
                    "messages": self._keeper_messages(),
                },
                3000,
            )
            w = SymbioseWorker(SessionSpanSink(mem))
            try:
                report = drain_submit_sidecars(w, mem, limit=2)
            finally:
                w.close()
            drained_files = sorted(d["file"] for d in report["drained"])
            self.assertEqual(
                drained_files, ["rtrre-mid.submit.json", "rtrre-old.submit.json"]
            )
            self.assertTrue((mem / "rtrre-new.submit.json").exists())
            self.assertIn("rtrre-new.submit.json", [e["file"] for e in report["left"]])

    def test_drain_stops_on_overflow_and_leaves_sidecars(self):
        import threading

        from symbiose_worker import SymbioseWorker, drain_submit_sidecars

        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / ".opencode" / "memory"
            mem.mkdir(parents=True)
            for name in ("rtrre-one.submit.json", "rtrre-two.submit.json"):
                self._write_sidecar(
                    mem,
                    name,
                    {
                        "digest": name,
                        "ts": "2026-11-09T00:00:00Z",
                        "messages": self._keeper_messages("side"),
                    },
                    1000,
                )
            release = threading.Event()

            def blocking_sink(spans):
                release.wait(timeout=10)
                return "ok"

            w = SymbioseWorker(
                blocking_sink,
                max_queue=1,
                config={
                    "trigger_tokens": 100,
                    "target_tokens": 50,
                    "max_keep_messages": 200,
                },
            )
            try:
                first = w.submit(self._keeper_messages("a"))
                self.assertEqual(first["status"], "pending")
                time.sleep(0.3)  # let the worker grab #1 and block in the sink
                second = w.submit(self._keeper_messages("b"))
                self.assertEqual(second["status"], "pending")
                report = drain_submit_sidecars(w, mem)
                self.assertEqual(report["drained"], [])
                self.assertEqual(len(report["left"]), 2)
                self.assertIn("overflow", report["left"][0]["reason"])
            finally:
                release.set()
                w.close()

    def test_drain_leaves_sidecar_on_wait_timeout(self):
        import threading

        from symbiose_worker import SymbioseWorker, drain_submit_sidecars

        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / ".opencode" / "memory"
            mem.mkdir(parents=True)
            self._write_sidecar(
                mem,
                "rtrre-slow.submit.json",
                {
                    "digest": "slow",
                    "ts": "2026-11-09T00:00:00Z",
                    "messages": self._keeper_messages(),
                },
                1000,
            )
            release = threading.Event()

            def blocking_sink(spans):
                release.wait(timeout=10)
                return "ok"

            w = SymbioseWorker(
                blocking_sink,
                config={
                    "trigger_tokens": 100,
                    "target_tokens": 50,
                    "max_keep_messages": 200,
                },
            )
            try:
                report = drain_submit_sidecars(w, mem, wait_timeout=0.2)
                self.assertEqual(report["drained"], [])
                self.assertEqual(len(report["left"]), 1)
                self.assertEqual(report["left"][0]["reason"], "timeout")
                self.assertTrue((mem / "rtrre-slow.submit.json").exists())
            finally:
                release.set()
                w.close()

    def test_drain_on_closed_worker_leaves_sidecars(self):
        from symbiose_worker import SymbioseWorker, drain_submit_sidecars

        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / ".opencode" / "memory"
            mem.mkdir(parents=True)
            self._write_sidecar(
                mem,
                "rtrre-late.submit.json",
                {
                    "digest": "late",
                    "ts": "2026-11-09T00:00:00Z",
                    "messages": self._keeper_messages(),
                },
                1000,
            )
            w = SymbioseWorker(lambda spans: "ok")
            w.close()
            report = drain_submit_sidecars(w, mem)
            self.assertEqual(report["drained"], [])
            self.assertEqual(len(report["left"]), 1)
            self.assertIn("closed", report["left"][0]["reason"])
            self.assertTrue((mem / "rtrre-late.submit.json").exists())

    def test_drain_stops_when_ticket_fails(self):
        from symbiose_worker import SymbioseWorker, drain_submit_sidecars

        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / ".opencode" / "memory"
            mem.mkdir(parents=True)
            self._write_sidecar(
                mem,
                "rtrre-boom.submit.json",
                {
                    "digest": "boom",
                    "ts": "2026-11-09T00:00:00Z",
                    "messages": self._keeper_messages("boom"),
                },
                1000,
            )
            self._write_sidecar(
                mem,
                "rtrre-next.submit.json",
                {
                    "digest": "next",
                    "ts": "2026-11-09T00:00:01Z",
                    "messages": self._keeper_messages("next"),
                },
                2000,
            )

            def boom(spans):
                raise RuntimeError("sink down")

            w = SymbioseWorker(
                boom,
                config={
                    "trigger_tokens": 100,
                    "target_tokens": 50,
                    "max_keep_messages": 200,
                },
            )
            try:
                report = drain_submit_sidecars(w, mem)
                self.assertEqual(report["drained"], [])
                self.assertEqual(len(report["left"]), 2)
                self.assertIn("failed", report["left"][0]["reason"])
                self.assertIn("sink down", report["left"][0]["reason"])
                self.assertTrue((mem / "rtrre-boom.submit.json").exists())
                self.assertTrue((mem / "rtrre-next.submit.json").exists())
            finally:
                w.close()

    def test_multi_sweep_pipeline_sinks_verbatim_and_advances_cumulative(self):
        import json

        from symbiose_worker import (
            SessionSpanSink,
            SymbioseWorker,
            drain_submit_sidecars,
        )

        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / ".opencode" / "memory"
            mem.mkdir(parents=True)
            for pos, marker in enumerate(("s1", "s2", "s3")):
                self._write_sidecar(
                    mem,
                    f"rtrre-{marker}.submit.json",
                    {
                        "digest": marker,
                        "ts": "2026-11-09T00:00:00Z",
                        "messages": self._keeper_messages(marker),
                    },
                    1000 + pos,
                )
            cumulative = Path(td) / ".opencode" / "rtr-re-cumulative.json"
            w = SymbioseWorker(
                SessionSpanSink(mem),
                config={
                    "trigger_tokens": 100,
                    "target_tokens": 50,
                    "max_keep_messages": 200,
                },
                cumulative_path=cumulative,
            )
            try:
                first = drain_submit_sidecars(w, mem, limit=1)
                self.assertEqual(len(first["drained"]), 1)
                self.assertEqual(first["drained"][0]["file"], "rtrre-s1.submit.json")
                self.assertEqual(len(first["left"]), 2)
                second = drain_submit_sidecars(w, mem)
                self.assertEqual(len(second["drained"]), 2)
                self.assertEqual(second["quarantined"], [])
                self.assertEqual(list(mem.glob("rtrre-*.submit.json")), [])
                state = json.loads(cumulative.read_text(encoding="utf-8"))
                self.assertEqual(state["cumulative_messages"], 9)
                bodies = [
                    p.read_text(encoding="utf-8")
                    for p in mem.glob("rtrre-*.dtd")
                    if "summary" not in p.name
                ]
                self.assertEqual(len(bodies), 3)
                joined = "\n".join(bodies)
                for marker in ("s1", "s2", "s3"):
                    self.assertIn(f"old question {marker}", joined)
            finally:
                w.close()

    def test_drain_relays_despite_literal_tag_text_in_spans(self):
        # E-T38C phase 1 (measured live 2026-11-10: sidecar 1cb8575a,
        # loose count 202 vs strict 195 — verbatim content quoting span
        # tags overcounts the loose substring and defeats relay into a
        # duplicate ticket). Only real span opens must count.
        from symbiose_worker import (
            SessionSpanSink,
            SymbioseWorker,
            drain_submit_sidecars,
        )

        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / ".opencode" / "memory"
            mem.mkdir(parents=True)
            self._write_sidecar(
                mem,
                "rtrre-aaa.submit.json",
                {"digest": "aaa", "messages": [{"a": 1}, {"b": 2}]},
                1000,
            )
            (mem / "rtrre-aaa.dtd").write_text(
                '<!-- schema -->\n<span id="span-0">\n'
                'text quoting <span id="x"> tags\n'
                '<span id="span-1">\nmore\n',
                encoding="utf-8",
            )
            w = SymbioseWorker(SessionSpanSink(mem))
            try:
                report = drain_submit_sidecars(w, mem)
            finally:
                w.close()
            self.assertEqual(len(report["drained"]), 1)
            self.assertTrue(report["drained"][0].get("relayed"))


class TestSubmitPlanOverrides(unittest.TestCase):
    def _ovr_worker(self, trigger=100, target=5000):
        from symbiose_worker import SymbioseWorker

        return SymbioseWorker(
            lambda spans: "ok",
            config={
                "trigger_tokens": trigger,
                "target_tokens": target,
                "max_keep_messages": 200,
            },
        )

    def test_override_target_is_honored_and_echoed(self):
        w = self._ovr_worker()
        try:
            base = w.submit(wordy_messages(marker="base"))
            ovr = w.submit(wordy_messages(marker="ovr"), {"target_tokens": 50})
            self.assertEqual(ovr["plan_overrides"], {"target_tokens": 50})
            self.assertEqual(base["plan_overrides"], {})
            done_base = w.wait(base["id"], timeout=5)
            done_ovr = w.wait(ovr["id"], timeout=5)
            self.assertEqual(done_base["status"], "ready")
            self.assertEqual(done_ovr["status"], "ready")
            self.assertLess(done_ovr["keep_tokens"], done_base["keep_tokens"] / 5)
        finally:
            w.close()

    def test_override_gate_refuses_by_name(self):
        w = self._ovr_worker()
        try:
            msgs = wordy_messages(marker="gate")
            with self.assertRaises(ValueError):
                w.submit(msgs, {"target_tokens": 6000})
            with self.assertRaises(ValueError):
                w.submit(msgs, {"target_tokens": 100})
            with self.assertRaises(ValueError):
                w.submit(msgs, {"target_tokens": 0})
            with self.assertRaises(ValueError):
                w.submit(msgs, {"target_tokens": -5})
            with self.assertRaises(ValueError):
                w.submit(msgs, {"target_tokens": "50"})
            with self.assertRaises(ValueError):
                w.submit(msgs, {"target_tokens": True})
            with self.assertRaises(ValueError):
                w.submit(msgs, {"trigger_tokens": 10})
        finally:
            w.close()

    def test_compress_json_carries_thinking_into_the_budget(self):
        import json

        from symbiose_worker import compress_json

        msgs = [
            {"role": "user", "parts": [{"type": "text", "text": "q"}]},
            {
                "role": "assistant",
                "parts": [
                    {"type": "reasoning", "reasoning": "deliberate " * 600},
                    {"type": "text", "text": "a"},
                ],
            },
            {"role": "user", "parts": [{"type": "text", "text": "latest"}]},
        ]
        w = self._ovr_worker()
        try:
            ticket = compress_json(w, json.dumps(msgs), 50)
            self.assertEqual(ticket["plan_overrides"], {"target_tokens": 50})
            done = w.wait(ticket["id"], timeout=5)
            self.assertEqual(done["status"], "ready")
            self.assertGreater(done["total_tokens"], 500)
            self.assertLess(done["keep_tokens"], done["total_tokens"] / 5)
        finally:
            w.close()

    def test_concurrent_targets_stay_independent(self):
        w = self._ovr_worker(trigger=1000, target=500)
        try:
            tiny = w.submit(wordy_messages(marker="tiny"), {"target_tokens": 50})
            wide = w.submit(wordy_messages(marker="wide"), {"target_tokens": 900})
            done_tiny = w.wait(tiny["id"], timeout=5)
            done_wide = w.wait(wide["id"], timeout=5)
            self.assertEqual(done_tiny["status"], "ready")
            self.assertEqual(done_wide["status"], "ready")
            self.assertEqual(done_tiny["plan_overrides"], {"target_tokens": 50})
            self.assertEqual(done_wide["plan_overrides"], {"target_tokens": 900})
            self.assertLess(done_tiny["keep_tokens"], done_wide["keep_tokens"] / 5)
        finally:
            w.close()

    def test_same_messages_different_targets_are_distinct_tickets(self):
        w = self._ovr_worker(trigger=1000, target=500)
        try:
            first = w.submit(wordy_messages(marker="same"), {"target_tokens": 50})
            second = w.submit(wordy_messages(marker="same"), {"target_tokens": 900})
            self.assertNotEqual(first["id"], second["id"])
            done_first = w.wait(first["id"], timeout=5)
            done_second = w.wait(second["id"], timeout=5)
            self.assertLess(done_first["keep_tokens"], done_second["keep_tokens"] / 5)
        finally:
            w.close()


class TestOpenProjectWorker(unittest.TestCase):
    def test_open_project_worker_sinks_to_project_memory_root(self):
        import json

        from symbiose_worker import open_project_worker

        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "proj"
            w = open_project_worker(
                proj,
                config={
                    "trigger_tokens": 100,
                    "target_tokens": 50,
                    "max_keep_messages": 200,
                },
            )
            try:
                ticket = w.submit(wordy_messages(marker="fac"))
                done = w.wait(ticket["id"], timeout=5)
                self.assertEqual(done["status"], "ready")
                sink = Path(done["sink"])
                self.assertEqual(sink.parent, proj / ".opencode" / "memory")
                self.assertIn("span-", sink.read_text(encoding="utf-8"))
                state = json.loads(
                    (proj / ".opencode" / "rtr-re-cumulative.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(state["cumulative_messages"], 21)
            finally:
                w.close()


def v2_message(role, parts, mid="m1"):
    return {"info": {"id": mid, "role": role, "sessionID": "s1"}, "parts": parts}


class TestRealMessageShapes(unittest.TestCase):
    def test_lane_classifies_real_shapes(self):
        from context_budget import span_lane

        thinking_only = v2_message(
            "assistant",
            [{"id": "p1", "type": "reasoning", "text": "deliberate " * 60}],
        )
        written = v2_message(
            "assistant", [{"id": "p1", "type": "text", "text": "plain answer"}]
        )
        read = v2_message("user", [{"id": "p1", "type": "text", "text": "question"}])
        with_tools = v2_message(
            "assistant",
            [
                {"id": "p1", "type": "text", "text": "calling"},
                {"id": "p2", "type": "tool", "tool": "bash", "state": {}},
            ],
        )
        tool_role = v2_message("tool", [{"id": "p1", "type": "text", "text": "output"}])
        self.assertEqual(span_lane(thinking_only), "think")
        self.assertEqual(span_lane(written), "written")
        self.assertEqual(span_lane(read), "read")
        self.assertEqual(span_lane(with_tools), "read")
        self.assertEqual(span_lane(tool_role), "read")

    def test_tool_part_text_counts_in_budget(self):
        import context_budget

        def msgs(words):
            return [
                v2_message("user", [{"id": "p", "type": "text", "text": "go"}]),
                v2_message(
                    "assistant",
                    [
                        {
                            "id": "t",
                            "type": "tool",
                            "tool": "bash",
                            "state": {
                                "input": {"q": "word " * words},
                                "output": "word " * words,
                            },
                        }
                    ],
                ),
            ]

        narrow = context_budget.plan_compression(msgs(100))
        wide = context_budget.plan_compression(msgs(300))
        self.assertGreater(wide["total_tokens"] - narrow["total_tokens"], 100)

    def test_protected_tool_part_survives_eviction(self):
        import context_budget

        cfg = {
            "trigger_tokens": 100,
            "target_tokens": 50,
            "max_keep_messages": 200,
            "cumulative_messages": 0,
        }
        old = v2_message(
            "assistant",
            [
                {
                    "id": "t",
                    "type": "tool",
                    "tool": "todowrite",
                    "state": {"input": {"plan": 1}, "output": "saved"},
                }
            ],
            mid="old",
        )
        new = v2_message(
            "assistant",
            [{"id": "p", "type": "text", "text": "word " * 300}],
            mid="new",
        )
        middle = v2_message(
            "assistant",
            [{"id": "p", "type": "text", "text": "word " * 300}],
            mid="mid",
        )
        plan = context_budget.plan_compression([old, middle, new], config=cfg)
        self.assertTrue(plan["compress"])
        self.assertIn(0, plan["keep"])
        mundane = v2_message(
            "assistant",
            [
                {
                    "id": "t",
                    "type": "tool",
                    "tool": "bash",
                    "state": {"input": {}, "output": "ok"},
                }
            ],
            mid="old",
        )
        plan2 = context_budget.plan_compression([mundane, middle, new], config=cfg)
        self.assertTrue(plan2["compress"])
        self.assertNotIn(0, plan2["keep"])

    def test_last_user_found_in_nested_info(self):
        import context_budget

        cfg = {
            "trigger_tokens": 100,
            "target_tokens": 50,
            "max_keep_messages": 200,
        }
        old_user = v2_message(
            "user", [{"id": "p", "type": "text", "text": "first question"}], mid="u0"
        )
        big1 = v2_message(
            "assistant",
            [{"id": "p", "type": "text", "text": "word " * 300}],
            mid="a1",
        )
        big2 = v2_message(
            "assistant",
            [{"id": "p", "type": "text", "text": "word " * 300}],
            mid="a2",
        )
        plan = context_budget.plan_compression([old_user, big1, big2], config=cfg)
        self.assertTrue(plan["compress"])
        self.assertIn(0, plan["keep"])

    def test_payload_roles_use_nested_info(self):
        import context_budget

        cfg = {
            "trigger_tokens": 100,
            "target_tokens": 50,
            "max_keep_messages": 200,
        }
        msgs = [
            v2_message("user", [{"id": "p", "type": "text", "text": "old"}], mid="u0"),
            v2_message(
                "assistant",
                [{"id": "p", "type": "text", "text": "word " * 300}],
                mid="a1",
            ),
            v2_message(
                "assistant",
                [{"id": "p", "type": "text", "text": "word " * 300}],
                mid="a2",
            ),
        ]
        plan = context_budget.plan_compression(msgs, config=cfg)
        self.assertTrue(plan["compress"])
        self.assertEqual(plan["evict"], [1])
        roles = {s["role"] for s in plan["evict_payload"]}
        self.assertNotIn("unknown", roles)


class TestDetachmentProof(unittest.TestCase):
    def test_evicted_markers_leave_the_kept_window_and_survive_in_payload(self):
        import context_budget
        from context_budget import _text_of  # production extractor, not a test twin

        cfg = {
            "trigger_tokens": 100,
            "target_tokens": 50,
            "max_keep_messages": 200,
        }
        old = v2_message(
            "user",
            [{"id": "p", "type": "text", "text": "READ-OLD question"}],
            mid="u0",
        )
        big1 = {
            "info": {"id": "a1", "role": "assistant", "sessionID": "s1"},
            "parts": [
                {"id": "p1", "type": "text", "text": "WROTE-1 " + "word " * 100},
                {
                    "id": "p2",
                    "type": "reasoning",
                    "text": "THINK-1 " + "deliberate " * 100,
                },
                {
                    "id": "p3",
                    "type": "tool",
                    "tool": "bash",
                    "state": {"input": {"q": "TOOLSTATE-1"}, "output": "done"},
                },
            ],
        }
        flat_tool = {"role": "tool", "text": "FLATTOOL-1 output"}
        mid = v2_message(
            "user",
            [{"id": "p", "type": "text", "text": "READ-MID question"}],
            mid="u1",
        )
        big2 = v2_message(
            "assistant",
            [{"id": "p", "type": "text", "text": "WROTE-2 " + "word " * 150}],
            mid="a2",
        )
        latest = v2_message(
            "user", [{"id": "p", "type": "text", "text": "READ-NEW latest"}], mid="u3"
        )
        msgs = [old, big1, flat_tool, mid, big2, latest]
        plan = context_budget.plan_compression(msgs, config=cfg)
        self.assertTrue(plan["compress"])
        # Partition: every index kept or evicted, never both.
        self.assertEqual(sorted(plan["keep"] + plan["evict"]), list(range(len(msgs))))
        self.assertEqual(set(plan["keep"]).intersection(plan["evict"]), set())
        kept_texts = [_text_of(msgs[i]) for i in plan["keep"]]
        payload_text = "\n".join(s["text"] for s in plan["evict_payload"])
        for marker in (
            "READ-OLD",
            "WROTE-1",
            "THINK-1",
            "TOOLSTATE-1",
            "FLATTOOL-1",
            "READ-MID",
            "WROTE-2",
        ):
            for kept in kept_texts:
                self.assertNotIn(marker, kept)
            self.assertIn(marker, payload_text)
        self.assertIn("READ-NEW", "\n".join(kept_texts))


class WaitClockTests(unittest.TestCase):
    def test_wait_uses_injected_clock(self):
        # E-T16-5: wait() hardcoded time.monotonic() while the worker
        # honors an injected clock everywhere else — timeouts untestable.
        state = {"now": 0.0, "calls": 0}

        def fake_clock():
            state["calls"] += 1
            state["now"] += 1.0
            return state["now"]

        w = SymbioseWorker(lambda spans: "ok", clock=fake_clock)
        try:
            calls_before = state["calls"]
            start = time.monotonic()
            out = w.wait(424242, timeout=8)
            wall = time.monotonic() - start
        finally:
            w.close()
        self.assertGreater(state["calls"], calls_before)
        self.assertLess(wall, 5.0)
        self.assertEqual(out["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
