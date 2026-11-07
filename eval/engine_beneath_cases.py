# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Engine Beneath — extensible case registry (RE edition, full architecture).

This module is the *open* instrument for the Engine Beneath evaluation. It is
deliberately a registry of named cases, so later TODOs (DTD amplification,
new presets, new functions) can register additional cases without rewriting
the runner.

Every case is a callable returning a verdict record:

    {
        "case": <name>,
        "description": <one line>,
        "checks": {<check name>: 0.0 or 1.0, ...},
        "required": [<check names that must be 1.0>],
        "verdict": "pass" | "fail",
        "evidence": {<free-form machine-readable evidence>},
    }

The scoreboard aggregates cases and can go red: any required check that is
0.0 makes the case fail, and any failed case makes the run fail. An
aggregate never hides a zero.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "execution"))
sys.path.insert(0, str(Path(__file__).parent))

from context_budget import (  # noqa: E402
    PROTECTED_TOOLS,
    estimate_tokens,
    keeper_preset,
    mask_ndata,
    plan_compression,
    span_dtype,
    span_lane,
)
from engine_beneath import evaluate_conversation  # noqa: E402
from symbiose_worker import SessionSpanSink, SymbioseWorker  # noqa: E402

Case = Callable[[], Dict[str, Any]]
_CASES: Dict[str, Case] = {}


def register_case(name: str) -> Callable[[Case], Case]:
    """Decorator: register a named case in the registry."""

    def decorator(fn: Case) -> Case:
        _CASES[name] = fn
        return fn

    return decorator


def all_cases() -> List[str]:
    return sorted(_CASES)


def _msg(
    role: str, text: str, tool: str | None = None, tokens: int | None = None
) -> Dict[str, Any]:
    value: Dict[str, Any] = {"role": role, "text": text}
    if tool:
        value["tool"] = tool
    if tokens is not None:
        value["tokens"] = tokens
    return value


def _blob(size: int) -> str:
    return "x" * size


def _cdata_long(size: int) -> str:
    """Long but CDATA text: spaces break the 64+ unbroken-run NDATA regex,
    so markers survive verbatim in the DTD-shaped sink (TODO-70)."""
    unit = "the keeper memory is infinite and retrievable. "
    return unit * max(1, size // len(unit))


def _verdict(
    checks: Dict[str, float],
    required: Sequence[str],
    evidence: Dict[str, Any],
    case: str,
    description: str,
) -> Dict[str, Any]:
    failed = [name for name in required if checks.get(name, 0.0) != 1.0]
    return {
        "case": case,
        "description": description,
        "checks": checks,
        "required": list(required),
        "verdict": "fail" if failed else "pass",
        "failed_required": failed,
        "evidence": evidence,
    }


@register_case("corrupted-sink-reports-failed")
def case_corrupted_sink() -> Dict[str, Any]:
    """A sink that raises mid-write must surface as worker status 'failed', not silent pass."""

    class ExplodingSink:
        def __call__(self, spans, digest=""):
            raise OSError("simulated sink failure")

    messages = [
        _msg("assistant", _blob(12000)),
        _msg("assistant", _blob(12000)),
        _msg("user", "latest question"),
    ]
    with tempfile.TemporaryDirectory(prefix="rtrre-eb-corrupt-") as temporary:
        worker = SymbioseWorker(
            ExplodingSink(),
            cooldown_seconds=0,
            config={"trigger_tokens": 100, "target_tokens": 30, "max_keep_messages": 2},
        )
        try:
            ticket = worker.submit(messages)
            completed = worker.wait(int(ticket["id"]), timeout=10.0)
        finally:
            worker.close()

    status = completed.get("status")
    checks = {
        "worker_reports_failed": 1.0 if status == "failed" else 0.0,
        "error_recorded": 1.0 if completed.get("error") else 0.0,
    }
    return _verdict(
        checks,
        ["worker_reports_failed", "error_recorded"],
        {"status": status, "error": completed.get("error")},
        "corrupted-sink-reports-failed",
        "Corrupted sink surfaces as failed, never silent pass",
    )


@register_case("duplicate-submission-deterministic")
def case_duplicate() -> Dict[str, Any]:
    """Submitting identical message lists twice yields identical hashes and plans."""
    messages = [
        _msg("assistant", _blob(12000)),
        _msg("user", "question"),
    ]
    cfg = {"trigger_tokens": 100, "target_tokens": 30, "max_keep_messages": 2}
    first = plan_compression(messages, config=cfg)
    second = plan_compression(messages, config=cfg)
    checks = {
        "same_keep": 1.0 if first.get("keep") == second.get("keep") else 0.0,
        "same_evict": 1.0 if first.get("evict") == second.get("evict") else 0.0,
        "same_total_tokens": 1.0
        if first.get("total_tokens") == second.get("total_tokens")
        else 0.0,
    }
    return _verdict(
        checks,
        ["same_keep", "same_evict", "same_total_tokens"],
        {
            "keep_first": first.get("keep"),
            "keep_second": second.get("keep"),
            "evict_first": first.get("evict"),
            "evict_second": second.get("evict"),
        },
        "duplicate-submission-deterministic",
        "Identical submissions produce identical plans",
    )


@register_case("worker-cache-deduplicates")
def case_worker_cache_deduplicates() -> Dict[str, Any]:
    """The worker returns status 'cached' for a second identical submission."""
    messages = [
        _msg("assistant", _blob(12000)),
        _msg("user", "question"),
    ]
    cfg = {"trigger_tokens": 100, "target_tokens": 30, "max_keep_messages": 2}
    with tempfile.TemporaryDirectory(prefix="rtrre-eb-cache-") as temporary:
        worker = SymbioseWorker(
            SessionSpanSink(Path(temporary)),
            cooldown_seconds=0,
            config=cfg,
        )
        try:
            first = worker.submit(messages)
            first_completed = worker.wait(int(first["id"]), timeout=10.0)
            second = worker.submit(messages)
        finally:
            worker.close()
    checks = {
        "second_is_cached": 1.0 if second.get("status") == "cached" else 0.0,
        "same_digest": 1.0 if second.get("hash") == first.get("hash") else 0.0,
        "first_ready": 1.0 if first_completed.get("status") == "ready" else 0.0,
    }
    return _verdict(
        checks,
        ["second_is_cached", "same_digest", "first_ready"],
        {
            "first_status": first_completed.get("status"),
            "second_status": second.get("status"),
            "hash": first.get("hash"),
        },
        "worker-cache-deduplicates",
        "Worker cache deduplicates identical submissions",
    )


@register_case("corrupted-sink-mid-batch")
def case_corrupted_sink_mid_batch() -> Dict[str, Any]:
    """A sink that fails after writing the first span must surface as failed."""

    class MidBatchExplodingSink:
        def __init__(self, directory: Path):
            self.directory = Path(directory)
            self.writes = 0
            self.partial_bytes = 0

        def __call__(self, spans, digest=""):
            path = self.directory / f"rtrre-midbatch-{digest or 'spans'}.md"
            lines = [f"# RE:Symbiose evicted spans {digest}", ""]
            for index, span in enumerate(spans):
                if index >= 1:
                    # Simulate a mid-batch failure: the first span is already
                    # written, the second one fails.
                    raise OSError("simulated mid-batch sink failure")
                self.writes += 1
                lines.append(f"## span {span.get('index', '?')}")
                lines.append(str(span.get("text") or ""))
                lines.append("")
            path.write_bytes(("\n".join(lines)).encode("utf-8"))
            self.partial_bytes = path.stat().st_size
            return str(path)

    messages = [
        _msg("assistant", _blob(12000)),
        _msg("assistant", _blob(12000)),
        _msg("assistant", _blob(12000)),
        _msg("user", "latest question"),
    ]
    with tempfile.TemporaryDirectory(prefix="rtrre-eb-midbatch-") as temporary:
        sink = MidBatchExplodingSink(Path(temporary))
        worker = SymbioseWorker(
            sink,
            cooldown_seconds=0,
            config={"trigger_tokens": 100, "target_tokens": 30, "max_keep_messages": 2},
        )
        try:
            ticket = worker.submit(messages)
            completed = worker.wait(int(ticket["id"]), timeout=10.0)
        finally:
            worker.close()

    status = completed.get("status")
    checks = {
        "worker_reports_failed": 1.0 if status == "failed" else 0.0,
        "error_recorded": 1.0 if completed.get("error") else 0.0,
        "sink_attempted_write": 1.0 if sink.writes >= 1 else 0.0,
    }
    return _verdict(
        checks,
        ["worker_reports_failed", "error_recorded", "sink_attempted_write"],
        {"status": status, "error": completed.get("error"), "sink_writes": sink.writes},
        "corrupted-sink-mid-batch",
        "Mid-batch sink failure surfaces as failed, never silent pass",
    )


@register_case("protected-tool-todowrite-retained")
def case_protected_tool() -> Dict[str, Any]:
    """todowrite messages are always retained, even when old and large."""
    messages = [
        _msg("assistant", _blob(12000), tool="todowrite"),
        _msg("assistant", _blob(12000)),
        _msg("user", "latest question"),
    ]
    cfg = {"trigger_tokens": 100, "target_tokens": 30, "max_keep_messages": 2}
    plan = plan_compression(messages, config=cfg)
    kept = {int(i) for i in plan.get("keep", [])}
    checks = {
        "todowrite_retained": 1.0 if 0 in kept else 0.0,
    }
    return _verdict(
        checks,
        ["todowrite_retained"],
        {"keep": sorted(kept), "protected_tools": sorted(PROTECTED_TOOLS)},
        "protected-tool-todowrite-retained",
        "Protected tool survives eviction",
    )


@register_case("tool-pair-fixpoint")
def case_tool_pair() -> Dict[str, Any]:
    """A tool call and its result stay together across the cut."""
    messages = [
        _msg("assistant", _blob(12000)),
        _msg("assistant", _blob(12000)),
        {"role": "assistant", "text": "call", "tool": "read", "tokens": 10},
        {"role": "tool", "text": "result", "tool_call": True, "tokens": 10},
        _msg("user", "latest question"),
    ]
    cfg = {"trigger_tokens": 100, "target_tokens": 30, "max_keep_messages": 3}
    plan = plan_compression(messages, config=cfg)
    kept = {int(i) for i in plan.get("keep", [])}
    checks = {
        "call_retained": 1.0 if 2 in kept else 0.0,
        "result_retained": 1.0 if 3 in kept else 0.0,
    }
    return _verdict(
        checks,
        ["call_retained", "result_retained"],
        {"keep": sorted(kept)},
        "tool-pair-fixpoint",
        "Tool call + result stay together",
    )


@register_case("preset-axis-all-six")
def case_preset_axis() -> Dict[str, Any]:
    """All six keeper presets resolve and plan with their declared bounds."""
    preset_names = [
        "standard",
        "calibrated",
        "wide",
        "fusion-ah",
        "symbiose-ah",
        "re-symbiose",
    ]
    results: Dict[str, Any] = {}
    checks: Dict[str, float] = {}
    for name in preset_names:
        try:
            resolved, bounds = keeper_preset(name)
            trigger = int(bounds.get("triggerTokens", 0))
            target = int(bounds.get("targetTokens", 0))
            maxkeep = int(bounds.get("maxKeepMessages", 0))
            messages = [_msg("assistant", _blob(12000)) for _ in range(maxkeep + 2)]
            messages.append(_msg("user", "latest question"))
            plan = plan_compression(
                messages,
                config={
                    "trigger_tokens": trigger,
                    "target_tokens": target,
                    "max_keep_messages": maxkeep,
                },
            )
            results[name] = {
                "resolved": resolved,
                "trigger": trigger,
                "target": target,
                "maxKeep": maxkeep,
                "plan_compress": bool(plan.get("compress", False)),
                "plan_keep_count": len(plan.get("keep", [])),
            }
            checks[f"{name}_resolves"] = 1.0
        except Exception as exc:  # noqa: BLE001
            results[name] = {"error": str(exc)}
            checks[f"{name}_resolves"] = 0.0
    return _verdict(
        checks,
        [f"{name}_resolves" for name in preset_names],
        {"presets": results},
        "preset-axis-all-six",
        "All six keeper presets resolve and plan",
    )


@register_case("preset-axis-full")
def case_preset_axis_full() -> Dict[str, Any]:
    """Full preset × thread-mode × parking × profile axis matrix verifies the parking arithmetic."""
    from context_budget import effective_threads_for_model, resolve_retrieval_profile

    checks: Dict[str, float] = {}
    evidence: Dict[str, Any] = {}

    # 1. Every keeper preset resolves its declared bounds exactly.
    presets = [
        "standard",
        "calibrated",
        "wide",
        "fusion-ah",
        "symbiose-ah",
        "re-symbiose",
        "re-symbiose-mugen",
    ]
    expected_bounds = {
        "standard": (320000, 128000, 40),
        "calibrated": (40000, 20000, 40),
        "wide": (640000, 256000, 40),
        "fusion-ah": (200000, 100000, 30),
        "symbiose-ah": (250000, 100000, 40),
        "re-symbiose": (320000, 128000, 50),
        "re-symbiose-mugen": (400000, 200000, 200),
    }
    for name in presets:
        _, bounds = keeper_preset(name)
        trig = int(bounds.get("triggerTokens", 0))
        tgt = int(bounds.get("targetTokens", 0))
        mk = int(bounds.get("maxKeepMessages", 0))
        exp_trig, exp_tgt, exp_mk = expected_bounds[name]
        ok = trig == exp_trig and tgt == exp_tgt and mk == exp_mk
        checks[f"{name}_bounds_exact"] = 1.0 if ok else 0.0
        evidence[f"{name}_bounds"] = {
            "resolved": [trig, tgt, mk],
            "expected": [exp_trig, exp_tgt, exp_mk],
        }

    # 2. Parking arithmetic verified across the full axis matrix (deterministic, 32 logical processors).
    thread_modes = [2, 4, 6, 8, 12, 16]
    parking_percents = [20, 30, 40, 50, 60, 70, 80]
    processors = 32
    rows: List[Dict[str, Any]] = []
    mismatches = 0
    cells = 0
    for model_count in (1, 2):
        for t in thread_modes:
            for p in parking_percents:
                got = effective_threads_for_model(
                    t, p, model_count=model_count, logical_processors=processors
                )
                parked_budget = int(processors * p / 100)
                per_model = max(1, parked_budget // model_count)
                expected_val = max(1, min(t, per_model))
                cells += 1
                if got != expected_val:
                    mismatches += 1
                rows.append(
                    {
                        "models": model_count,
                        "threads": t,
                        "parking": p,
                        "effective": got,
                        "expected": expected_val,
                    }
                )
    checks["parking_arithmetic_all_cells"] = 1.0 if mismatches == 0 else 0.0
    evidence["parking_matrix"] = {
        "cells": cells,
        "mismatches": mismatches,
        "rows": rows,
    }

    # 3. Profile defaults resolve on this machine (32 logical processors, rtr-full = 2 models).
    pub = resolve_retrieval_profile({})
    pub_ok = (
        pub["cpu_profile"] == "public-default"
        and pub["threads_per_model"] == 4
        and pub["parking_percent"] == 60
        and pub["modality"] == "rtr-full"
        and len(pub["models"]) == 2
    )
    checks["public_default_profile"] = 1.0 if pub_ok else 0.0
    evidence["public_default"] = {
        k: pub[k]
        for k in (
            "cpu_profile",
            "threads_per_model",
            "effective_threads_per_model",
            "parking_percent",
            "modality",
            "logical_processors",
            "parking_budget_threads",
            "planned_threads_per_engine",
        )
    }

    loc = resolve_retrieval_profile(
        {"OPENCODE_MEMORY_RTR_PRESET_PROFILE": "local-system"}
    )
    loc_ok = (
        loc["cpu_profile"] == "local-system"
        and loc["threads_per_model"] == 8
        and loc["parking_percent"] == 80
        and loc["modality"] == "rtr-full"
        and len(loc["models"]) == 2
    )
    checks["local_system_profile"] = 1.0 if loc_ok else 0.0
    evidence["local_system"] = {
        k: loc[k]
        for k in (
            "cpu_profile",
            "threads_per_model",
            "effective_threads_per_model",
            "parking_percent",
            "modality",
            "logical_processors",
            "parking_budget_threads",
            "planned_threads_per_engine",
        )
    }

    required = [f"{name}_bounds_exact" for name in presets] + [
        "parking_arithmetic_all_cells",
        "public_default_profile",
        "local_system_profile",
    ]
    return _verdict(
        checks,
        required,
        evidence,
        "preset-axis-full",
        "Full preset × thread × parking × profile matrix verifies the parking arithmetic",
    )


@register_case("production-scale-bounds")
def case_production_scale() -> Dict[str, Any]:
    """A production-scale window (single-user bound, many spans) plans within bounds."""
    # Single-user realistic windows sit around 40-200 messages (the keeper's
    # max_keep_messages is 40-50). 1000-message windows are datacenter scale
    # and only become relevant when models exceed ~1M context.
    count = 200
    messages = [_msg("assistant", _blob(4000)) for _ in range(count)]
    messages.append(_msg("user", "latest question"))
    cfg = {"trigger_tokens": 100000, "target_tokens": 40000, "max_keep_messages": 40}
    started = time.monotonic()
    plan = plan_compression(messages, config=cfg)
    elapsed_ms = (time.monotonic() - started) * 1000.0
    kept = plan.get("keep", [])
    evicted = plan.get("evict", [])
    checks = {
        "all_accounted": 1.0 if len(kept) + len(evicted) == len(messages) else 0.0,
        "keep_within_max": 1.0 if len(kept) <= 40 else 0.0,
        "compress_triggered": 1.0 if bool(plan.get("compress", False)) else 0.0,
    }
    return _verdict(
        checks,
        ["all_accounted", "keep_within_max", "compress_triggered"],
        {
            "messages": len(messages),
            "keep": len(kept),
            "evict": len(evicted),
            "total_tokens": plan.get("total_tokens"),
            "keep_tokens": plan.get("keep_tokens"),
            "plan_ms": round(elapsed_ms, 3),
        },
        "production-scale-bounds",
        "Production-scale window plans within bounds",
    )


@register_case("production-scale-extreme-protection-warning")
def case_production_scale_extreme_protection() -> Dict[str, Any]:
    """WARNING case: at datacenter scale (>1000k context), protection is recency-aware.

    This is the operator's design (TODO-45): a cumulative counter of all
    messages ever processed (including evicted) grows past 1000, and then
    protection is removed from really old todowrite so it yields to newer
    context. The intended contract:
      - cumulative <= 1000: old todowrite IS protected (full protection)
      - cumulative > 1000: OLD todowrite IS evicted (correct, makes space),
        while RECENT todowrite stays protected.
    If either side of this contract fails, the warning fires.
    """
    count = 1000
    messages = [_msg("assistant", _blob(4000)) for _ in range(count)]
    # Old todowrite buried early (index 5) — must be evicted past the threshold.
    messages[5] = _msg("assistant", _blob(12000), tool="todowrite")
    # Recent todowrite near the end (index count-1) — must stay protected.
    messages[count - 1] = _msg("assistant", _blob(12000), tool="todowrite")
    messages.append(_msg("user", "latest question"))
    cfg = {
        "trigger_tokens": 100000,
        "target_tokens": 40000,
        "max_keep_messages": 40,
        "cumulative_messages": 1001,
    }
    started = time.monotonic()
    plan = plan_compression(messages, config=cfg)
    elapsed_ms = (time.monotonic() - started) * 1000.0
    kept = {int(i) for i in plan.get("keep", [])}
    evicted = {int(i) for i in plan.get("evict", [])}
    old_todo_retained = 5 in kept and 5 not in evicted
    recent_todo_retained = (count - 1) in kept and (count - 1) not in evicted
    checks = {
        "old_todo_evicted_past_threshold": 1.0 if not old_todo_retained else 0.0,
        "recent_todo_retained": 1.0 if recent_todo_retained else 0.0,
        "all_accounted": 1.0 if len(kept) + len(evicted) == len(messages) else 0.0,
    }
    return _verdict(
        checks,
        ["old_todo_evicted_past_threshold", "recent_todo_retained", "all_accounted"],
        {
            "messages": len(messages),
            "keep": len(kept),
            "evict": len(evicted),
            "total_tokens": plan.get("total_tokens"),
            "keep_tokens": plan.get("keep_tokens"),
            "plan_ms": round(elapsed_ms, 3),
            "cumulative_messages": 1001,
            "old_todo_index": 5,
            "old_todo_retained": old_todo_retained,
            "recent_todo_index": count - 1,
            "recent_todo_retained": recent_todo_retained,
        },
        "production-scale-extreme-protection-warning",
        "Extreme scale (>1000k) removes protection from old todowrite, keeps recent",
    )


@register_case("compressor-fires-only-past-trigger")
def case_compressor_fires_only_past_trigger() -> Dict[str, Any]:
    """The Compressor fires only when total tokens exceed the trigger.

    Bounds come from the shipped preset registry (Symbiose-AH! public
    default), never from ad-hoc test numbers: the procedure verifies the
    actual shipped configuration.
    """
    _name, preset = keeper_preset("symbiose-ah")
    trigger = int(preset["triggerTokens"])
    target = int(preset["targetTokens"])
    max_keep = int(preset["maxKeepMessages"])
    cfg = {
        "trigger_tokens": trigger,
        "target_tokens": target,
        "max_keep_messages": max_keep,
    }
    below = [_msg("assistant", _blob(1000)) for _ in range(5)]
    # ~3000 tokens per _blob(12000); need > trigger messages.
    above = [_msg("assistant", _blob(12000)) for _ in range(trigger // 3000 + 5)]
    plan_below = plan_compression(below, config=cfg)
    plan_above = plan_compression(above, config=cfg)
    checks = {
        "no_compress_below_trigger": 1.0 if not plan_below["compress"] else 0.0,
        "compress_above_trigger": 1.0 if plan_above["compress"] else 0.0,
    }
    return _verdict(
        checks,
        ["no_compress_below_trigger", "compress_above_trigger"],
        {
            "preset": "symbiose-ah",
            "trigger_tokens": trigger,
            "below_total": plan_below["total_tokens"],
            "below_compress": plan_below["compress"],
            "above_total": plan_above["total_tokens"],
            "above_compress": plan_above["compress"],
        },
        "compressor-fires-only-past-trigger",
        "Compressor fires only past the shipped preset trigger",
    )


@register_case("compressor-reduces-live-window")
def case_compressor_reduces_live_window() -> Dict[str, Any]:
    """Compression measurably reduces the live window; evicted content is carried verbatim.

    Bounds come from the shipped preset registry (Symbiose-AH! public
    default), never from ad-hoc test numbers.
    """
    _name, preset = keeper_preset("symbiose-ah")
    trigger = int(preset["triggerTokens"])
    target = int(preset["targetTokens"])
    max_keep = int(preset["maxKeepMessages"])
    cfg = {
        "trigger_tokens": trigger,
        "target_tokens": target,
        "max_keep_messages": max_keep,
    }
    messages = [_msg("assistant", _blob(12000)) for _ in range(trigger // 3000 + 10)]
    messages.append(_msg("user", "latest question"))
    plan = plan_compression(messages, config=cfg)
    kept_tokens = int(plan["keep_tokens"])
    total = int(plan["total_tokens"])
    payload = plan.get("evict_payload", [])
    evict = plan.get("evict", [])
    # Verbatim check: every evicted span's index is present in the payload.
    evicted_indexes = {int(p["index"]) for p in payload}
    verbatim = evicted_indexes == {int(i) for i in evict}
    checks = {
        "window_measurably_smaller": 1.0 if kept_tokens < total else 0.0,
        "evict_payload_carries_all_evicted": 1.0 if verbatim else 0.0,
    }
    return _verdict(
        checks,
        ["window_measurably_smaller", "evict_payload_carries_all_evicted"],
        {
            "preset": "symbiose-ah",
            "trigger_tokens": trigger,
            "target_tokens": target,
            "total_tokens": total,
            "keep_tokens": kept_tokens,
            "reduction_ratio": round(kept_tokens / total, 4) if total else 0.0,
            "evicted_count": len(evict),
            "payload_count": len(payload),
        },
        "compressor-reduces-live-window",
        "Compressor measurably reduces the live window; evicted content survives verbatim",
    )


@register_case("compressor-never-compresses-protected")
def case_compressor_never_compresses_protected() -> Dict[str, Any]:
    """Protected todowrite never appears in the evict payload while protected.

    Below the cumulative threshold, every todowrite message is protected and
    must never be compressed away. At/above the threshold, only recent
    todowrite stays protected; old todowrite becomes evictable (the keeper's
    recency-aware contract, TODO-45).
    """
    _name, preset = keeper_preset("symbiose-ah")
    trigger = int(preset["triggerTokens"])
    target = int(preset["targetTokens"])
    max_keep = int(preset["maxKeepMessages"])
    messages = [_msg("assistant", _blob(12000)) for _ in range(trigger // 3000 + 20)]
    # Old todowrite buried early (outside the max_keep window); recent one
    # near the end (inside the window). With max_keep=40 and n>100, the old
    # region exists and the recency boundary is meaningful.
    messages[5]["tool"] = "todowrite"  # old
    messages[-2]["tool"] = "todowrite"  # recent
    messages.append(_msg("user", "latest question"))
    cfg = {
        "trigger_tokens": trigger,
        "target_tokens": target,
        "max_keep_messages": max_keep,
    }
    # Below threshold: both protected → neither evicted.
    plan_below = plan_compression(messages, config={**cfg, "cumulative_messages": 999})
    evicted_below = {int(i) for i in plan_below["evict"]}
    # Above threshold: old evicted, recent retained.
    plan_above = plan_compression(messages, config={**cfg, "cumulative_messages": 1001})
    evicted_above = {int(i) for i in plan_above["evict"]}
    checks = {
        "protected_never_compressed_below": 1.0
        if (5 not in evicted_below and (len(messages) - 2) not in evicted_below)
        else 0.0,
        "old_protected_evictable_above": 1.0 if 5 in evicted_above else 0.0,
        "recent_protected_retained_above": 1.0
        if (len(messages) - 2) not in evicted_above
        else 0.0,
    }
    return _verdict(
        checks,
        [
            "protected_never_compressed_below",
            "old_protected_evictable_above",
            "recent_protected_retained_above",
        ],
        {
            "below_evicted": sorted(evicted_below),
            "above_evicted": sorted(evicted_above),
        },
        "compressor-never-compresses-protected",
        "Protected todowrite is never compressed while protected",
    )


@register_case("live-engine-sink-roundtrip")
def case_live_engine_sink() -> Dict[str, Any]:
    """A real SessionSpanSink round-trips evicted spans to disk."""
    marker = "ENGINE-BENEATH-LIVE-SINK-902"
    messages = [
        _msg("assistant", marker + " " + _cdata_long(12000)),
        _msg("assistant", _cdata_long(12000)),
        _msg("user", "latest question"),
    ]
    with tempfile.TemporaryDirectory(prefix="rtrre-eb-live-") as temporary:
        result = evaluate_conversation(
            messages,
            config={"trigger_tokens": 100, "target_tokens": 30, "max_keep_messages": 2},
            markers=[marker],
            sink_directory=Path(temporary),
        )
        sink = result.get("sink", {})
        checks = {
            "verdict_pass": 1.0 if result.get("verdict") == "pass" else 0.0,
            "sink_exists": 1.0 if sink.get("exists") else 0.0,
            "sink_has_marker": 1.0 if sink.get("span_markers", 0) >= 1 else 0.0,
        }
    return _verdict(
        checks,
        ["verdict_pass", "sink_exists", "sink_has_marker"],
        {"sink": sink},
        "live-engine-sink-roundtrip",
        "Real sink round-trips evicted spans",
    )


@register_case("content-model-feature-in-header")
def case_content_model_feature() -> Dict[str, Any]:
    """DTD chunks carry a CONTENT MODELS inventory line, and a distinctive
    fragment query resolves to the declaring file (TODO-33)."""
    import os

    from memory_engine import MemoryEngine

    checks: Dict[str, float] = {}
    evidence: Dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="rtrre-eb-cm-") as temporary:
        root = Path(temporary)
        proj = root / "projects"
        (proj / "directives").mkdir(parents=True)
        (proj / "directives" / "alpha.dtd").write_text(
            "<!ELEMENT alpha (title, author*)>\n<!ELEMENT title (#PCDATA)>\n",
            encoding="utf-8",
        )
        (proj / "directives" / "beta.dtd").write_text(
            "<!ELEMENT beta (chapter, section?)>\n<!ELEMENT chapter (#PCDATA)>\n",
            encoding="utf-8",
        )
        old_db = os.environ.get("OPENCODE_MEMORY_DB_DIR")
        old_suffixes = os.environ.get("OPENCODE_MEMORY_FILE_SUFFIXES")
        old_models = os.environ.get("OPENCODE_MEMORY_EMBED_MODELS")
        old_roots = None
        try:
            os.environ["OPENCODE_MEMORY_DB_DIR"] = str(root / "db")
            os.environ["OPENCODE_MEMORY_FILE_SUFFIXES"] = (
                ".md,.nt,.yaml,.yml,.dita,.xml,.dtd,.mod,.ent"
            )
            os.environ["OPENCODE_MEMORY_EMBED_MODELS"] = "BAAI/bge-small-en-v1.5"
            import memory_engine as mem

            old_roots = mem.PROJECT_ROOTS
            old_registry = mem.REGISTRY_FILE
            old_extra = mem.EXTRA_ROOTS_FILE
            old_lex = mem.LEXIKON_GLOBAL_FILE
            mem.PROJECT_ROOTS = [root / "projects"]
            mem.PROJECTS_DIR = root / "projects"
            mem.REGISTRY_FILE = root / "registry.json"
            mem.EXTRA_ROOTS_FILE = root / "extra_roots.json"
            mem.LEXIKON_GLOBAL_FILE = root / "lexikon_global.json"
            engine = MemoryEngine()
            try:
                stats = engine.index_all(force=True)
                col = engine.chroma_client.get_collection(
                    "opencode_memory_baai_bge_small_en_v1_5"
                )
                docs = col.get(include=["documents"])["documents"]
                cm_lines = [d for d in docs if "CONTENT MODELS:" in d]
                checks["header_has_content_models"] = 1.0 if len(cm_lines) >= 2 else 0.0
                alpha_cm = any("CONTENT MODELS: (title, author*)" in d for d in docs)
                beta_cm = any("CONTENT MODELS: (chapter, section?)" in d for d in docs)
                checks["fragments_listed"] = 1.0 if alpha_cm and beta_cm else 0.0
                res = engine.search("(title, author*)", k=3, project=None, hybrid=False)
                top = [Path(r["metadata"]["source"]).name for r in res]
                checks["fragment_query_resolves"] = (
                    1.0 if top and top[0] == "alpha.dtd" else 0.0
                )
                evidence["top"] = top
                evidence["indexed"] = stats.get("new")
            finally:
                engine.close()
                mem.PROJECT_ROOTS = old_roots
                mem.PROJECTS_DIR = old_roots
                mem.REGISTRY_FILE = old_registry
                mem.EXTRA_ROOTS_FILE = old_extra
                mem.LEXIKON_GLOBAL_FILE = old_lex
        finally:
            if old_db is None:
                os.environ.pop("OPENCODE_MEMORY_DB_DIR", None)
            else:
                os.environ["OPENCODE_MEMORY_DB_DIR"] = old_db
            if old_suffixes is None:
                os.environ.pop("OPENCODE_MEMORY_FILE_SUFFIXES", None)
            else:
                os.environ["OPENCODE_MEMORY_FILE_SUFFIXES"] = old_suffixes
            if old_models is None:
                os.environ.pop("OPENCODE_MEMORY_EMBED_MODELS", None)
            else:
                os.environ["OPENCODE_MEMORY_EMBED_MODELS"] = old_models
    return _verdict(
        checks,
        ["header_has_content_models", "fragments_listed", "fragment_query_resolves"],
        evidence,
        "content-model-feature-in-header",
        "Content-model fragments are listed in the inventory and resolve",
    )


@register_case("parameter-entity-injection-blocked")
def case_parameter_entity_injection() -> Dict[str, Any]:
    """A hostile DTD cannot inject declarations into the indexed inventory:
    entity bodies are data, never expanded (LAW.AMP.13)."""
    import os

    from memory_engine import MemoryEngine

    checks: Dict[str, float] = {}
    evidence: Dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="rtrre-eb-pe-") as temporary:
        root = Path(temporary)
        proj = root / "projects"
        (proj / "directives").mkdir(parents=True)
        (proj / "directives" / "hostile.dtd").write_text(
            '<!ENTITY % evil "<!ATTLIST injected id ID #REQUIRED>">\n'
            "<!ENTITY % worse [ <!ELEMENT injected EMPTY> ]>\n"
            "<!ELEMENT safe EMPTY>\n",
            encoding="utf-8",
        )
        old_db = os.environ.get("OPENCODE_MEMORY_DB_DIR")
        old_suffixes = os.environ.get("OPENCODE_MEMORY_FILE_SUFFIXES")
        old_models = os.environ.get("OPENCODE_MEMORY_EMBED_MODELS")
        try:
            os.environ["OPENCODE_MEMORY_DB_DIR"] = str(root / "db")
            os.environ["OPENCODE_MEMORY_EMBED_MODELS"] = "BAAI/bge-small-en-v1.5"
            os.environ["OPENCODE_MEMORY_FILE_SUFFIXES"] = (
                ".md,.nt,.yaml,.yml,.dita,.xml,.dtd,.mod,.ent"
            )
            import memory_engine as mem

            old_roots = mem.PROJECT_ROOTS
            old_registry = mem.REGISTRY_FILE
            old_extra = mem.EXTRA_ROOTS_FILE
            old_lex = mem.LEXIKON_GLOBAL_FILE
            mem.PROJECT_ROOTS = [root / "projects"]
            mem.PROJECTS_DIR = root / "projects"
            mem.REGISTRY_FILE = root / "registry.json"
            mem.EXTRA_ROOTS_FILE = root / "extra_roots.json"
            mem.LEXIKON_GLOBAL_FILE = root / "lexikon_global.json"
            engine = MemoryEngine()
            try:
                engine.index_all(force=True)
                col = engine.chroma_client.get_collection(
                    "opencode_memory_baai_bge_small_en_v1_5"
                )
                docs = col.get(include=["documents"])["documents"]
                header = docs[0].split("Section: Full Document\n\n")[1].split("\n\n")[0]
                checks["root_is_safe"] = 1.0 if "ROOT: safe" in header else 0.0
                checks["no_injected_attributes"] = (
                    1.0 if "ATTRIBUTES:" not in header else 0.0
                )
                checks["no_injected_elements"] = (
                    1.0 if "injected" not in header else 0.0
                )
                checks["param_entities_reported_as_data"] = (
                    1.0 if "ENTITIES: evil, worse" in header else 0.0
                )
                evidence["header"] = header
            finally:
                engine.close()
                mem.PROJECT_ROOTS = old_roots
                mem.PROJECTS_DIR = old_roots
                mem.REGISTRY_FILE = old_registry
                mem.EXTRA_ROOTS_FILE = old_extra
                mem.LEXIKON_GLOBAL_FILE = old_lex
        finally:
            if old_db is None:
                os.environ.pop("OPENCODE_MEMORY_DB_DIR", None)
            else:
                os.environ["OPENCODE_MEMORY_DB_DIR"] = old_db
            if old_suffixes is None:
                os.environ.pop("OPENCODE_MEMORY_FILE_SUFFIXES", None)
            else:
                os.environ["OPENCODE_MEMORY_FILE_SUFFIXES"] = old_suffixes
            if old_models is None:
                os.environ.pop("OPENCODE_MEMORY_EMBED_MODELS", None)
            else:
                os.environ["OPENCODE_MEMORY_EMBED_MODELS"] = old_models
    return _verdict(
        checks,
        [
            "root_is_safe",
            "no_injected_attributes",
            "no_injected_elements",
            "param_entities_reported_as_data",
        ],
        evidence,
        "parameter-entity-injection-blocked",
        "Entity bodies are data, never expanded",
    )


_OPTIMIZER_ENV_KEYS = (
    "OPENCODE_MEMORY_EMBED_MODELS",
    "OPENCODE_MEMORY_EMBED_THREADS",
    "OPENCODE_MEMORY_RTR_PROFILE",
    "OPENCODE_MEMORY_RTR_PRESET_PROFILE",
    "OPENCODE_MEMORY_CPU_PARKING_PERCENT",
    "OPENCODE_MEMORY_RETRIEVAL_MODALITY",
)


def _save_optimizer_env() -> Dict[str, str | None]:
    return {key: os.environ.get(key) for key in _OPTIMIZER_ENV_KEYS}


def _restore_optimizer_env(saved: Dict[str, str | None]) -> None:
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@register_case("optimizer-profile-consumed-by-engine")
def case_optimizer_profile_consumed() -> Dict[str, Any]:
    """The engine consumes the Optimizer's resolved profile: models and
    threads come from the registry profile when env is unset (single source
    of truth), and the modality's hybrid/expansion flags resolve."""
    from context_budget import resolve_retrieval_profile
    from memory_engine import configured_embed_models, resolve_threads_for

    saved = _save_optimizer_env()
    try:
        profile = resolve_retrieval_profile({})
        models = configured_embed_models()
        threads = resolve_threads_for("Snowflake/snowflake-arctic-embed-m")
        hybrid = bool(profile["hybrid"])
        expansion = bool(profile["expansion"])
    finally:
        _restore_optimizer_env(saved)
    checks = {
        "models_match_profile": 1.0 if models == profile["models"] else 0.0,
        "threads_match_profile": 1.0
        if threads == int(profile["effective_threads_per_model"])
        else 0.0,
        "profile_hybrid_flag": 1.0 if hybrid else 0.0,
        "profile_expansion_flag": 1.0 if expansion else 0.0,
    }
    return _verdict(
        checks,
        [
            "models_match_profile",
            "threads_match_profile",
            "profile_hybrid_flag",
            "profile_expansion_flag",
        ],
        {
            "profile_models": profile["models"],
            "engine_models": models,
            "profile_effective_threads": profile["effective_threads_per_model"],
            "engine_threads": threads,
            "hybrid": hybrid,
            "expansion": expansion,
        },
        "optimizer-profile-consumed-by-engine",
        "Engine consumes the Optimizer's resolved profile (models, threads, hybrid, expansion)",
    )


@register_case("optimizer-cpu-profile-applies-threads")
def case_optimizer_cpu_profile_applies() -> Dict[str, Any]:
    """The CPU profile actually applies to engine threads: local-system gives
    8, public-default gives 4, and the legacy profile env still works."""
    from memory_engine import resolve_threads_for

    model = "Snowflake/snowflake-arctic-embed-m"
    saved = _save_optimizer_env()
    try:
        os.environ.pop("OPENCODE_MEMORY_RTR_PROFILE", None)
        os.environ.pop("OPENCODE_MEMORY_EMBED_THREADS", None)
        os.environ["OPENCODE_MEMORY_RTR_PRESET_PROFILE"] = "local-system"
        local_threads = resolve_threads_for(model)
        os.environ["OPENCODE_MEMORY_RTR_PRESET_PROFILE"] = "public-default"
        public_threads = resolve_threads_for(model)
        os.environ.pop("OPENCODE_MEMORY_RTR_PRESET_PROFILE", None)
        os.environ["OPENCODE_MEMORY_RTR_PROFILE"] = "performance"
        legacy_threads = resolve_threads_for(model)
    finally:
        _restore_optimizer_env(saved)
    checks = {
        "local_system_applies_8": 1.0 if local_threads == 8 else 0.0,
        "public_default_applies_4": 1.0 if public_threads == 4 else 0.0,
        "legacy_performance_still_works": 1.0 if legacy_threads == 8 else 0.0,
    }
    return _verdict(
        checks,
        [
            "local_system_applies_8",
            "public_default_applies_4",
            "legacy_performance_still_works",
        ],
        {
            "local_system_threads": local_threads,
            "public_default_threads": public_threads,
            "legacy_performance_threads": legacy_threads,
        },
        "optimizer-cpu-profile-applies-threads",
        "CPU profile selects the engine's real threads, not just the report",
    )


@register_case("optimizer-parking-applies")
def case_optimizer_parking_applies() -> Dict[str, Any]:
    """Parking percent shapes effective threads: P20 on 32 processors with 2
    models caps the T4 budget at 3."""
    from memory_engine import resolve_threads_for

    model = "Snowflake/snowflake-arctic-embed-m"
    saved = _save_optimizer_env()
    try:
        os.environ.pop("OPENCODE_MEMORY_RTR_PROFILE", None)
        os.environ.pop("OPENCODE_MEMORY_EMBED_THREADS", None)
        os.environ.pop("OPENCODE_MEMORY_RTR_PRESET_PROFILE", None)
        os.environ["OPENCODE_MEMORY_CPU_PARKING_PERCENT"] = "20"
        parked_threads = resolve_threads_for(model)
        os.environ["OPENCODE_MEMORY_CPU_PARKING_PERCENT"] = "80"
        wide_threads = resolve_threads_for(model)
    finally:
        _restore_optimizer_env(saved)
    checks = {
        "parking20_caps_to_3": 1.0 if parked_threads == 3 else 0.0,
        "parking80_keeps_4": 1.0 if wide_threads == 4 else 0.0,
    }
    return _verdict(
        checks,
        ["parking20_caps_to_3", "parking80_keeps_4"],
        {"parking20_threads": parked_threads, "parking80_threads": wide_threads},
        "optimizer-parking-applies",
        "Parking percent shapes the engine's effective threads",
    )


@register_case("optimizer-modality-controls-hybrid")
def case_optimizer_modality_controls_hybrid() -> Dict[str, Any]:
    """The modality's hybrid/expansion flags are the Optimizer's defaults:
    rag-dense is non-hybrid and non-expanding; rtr-full is both."""
    from context_budget import resolve_retrieval_profile

    dense = resolve_retrieval_profile(
        {"OPENCODE_MEMORY_RETRIEVAL_MODALITY": "rag-dense"}
    )
    full = resolve_retrieval_profile({"OPENCODE_MEMORY_RETRIEVAL_MODALITY": "rtr-full"})
    checks = {
        "rag_dense_hybrid_false": 1.0 if not dense["hybrid"] else 0.0,
        "rag_dense_expansion_false": 1.0 if not dense["expansion"] else 0.0,
        "rtr_full_hybrid_true": 1.0 if full["hybrid"] else 0.0,
        "rtr_full_expansion_true": 1.0 if full["expansion"] else 0.0,
    }
    return _verdict(
        checks,
        [
            "rag_dense_hybrid_false",
            "rag_dense_expansion_false",
            "rtr_full_hybrid_true",
            "rtr_full_expansion_true",
        ],
        {
            "rag_dense": {"hybrid": dense["hybrid"], "expansion": dense["expansion"]},
            "rtr_full": {"hybrid": full["hybrid"], "expansion": full["expansion"]},
        },
        "optimizer-modality-controls-hybrid",
        "Modality flags are the Optimizer's hybrid/expansion defaults",
    )


@register_case("optimizer-expansion-gated")
def case_optimizer_expansion_gated() -> Dict[str, Any]:
    """The lexikon lane is gated by the modality's expansion flag: on for
    rtr-full, off for rag-dense; the delta lane stays in both."""
    import os

    from memory_engine import MemoryEngine

    checks: Dict[str, float] = {}
    evidence: Dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="rtrre-eb-optx-") as temporary:
        root = Path(temporary)
        proj = root / "proj"
        (proj / "state").mkdir(parents=True)
        (proj / "state" / "lexikon.json").write_text(
            json.dumps(
                {
                    "terms": {
                        "alpha": {
                            "term": "alpha",
                            "definition": "alpha element",
                            "aliases": [],
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        old_db = os.environ.get("OPENCODE_MEMORY_DB_DIR")
        saved = _save_optimizer_env()
        try:
            os.environ["OPENCODE_MEMORY_DB_DIR"] = str(root / "db")
            engine = MemoryEngine()
            try:
                lex_on, _ = engine.build_expansions("alpha structure", str(proj))
                checks["expansion_on_uses_lexikon"] = 1.0 if len(lex_on) >= 1 else 0.0
                os.environ["OPENCODE_MEMORY_RETRIEVAL_MODALITY"] = "rag-dense"
                lex_off, delta_off = engine.build_expansions(
                    "alpha structure", str(proj)
                )
                checks["expansion_off_gates_lexikon"] = (
                    1.0 if len(lex_off) == 0 else 0.0
                )
                evidence["lex_on"] = lex_on
                evidence["lex_off"] = lex_off
                evidence["delta_off"] = delta_off
            finally:
                engine.close()
        finally:
            if old_db is None:
                os.environ.pop("OPENCODE_MEMORY_DB_DIR", None)
            else:
                os.environ["OPENCODE_MEMORY_DB_DIR"] = old_db
            _restore_optimizer_env(saved)
    return _verdict(
        checks,
        ["expansion_on_uses_lexikon", "expansion_off_gates_lexikon"],
        evidence,
        "optimizer-expansion-gated",
        "Lexikon expansion is gated by the modality's expansion flag",
    )


@register_case("optimizer-mjs-plan-context-aligned")
def case_optimizer_mjs_plan_context_aligned() -> Dict[str, Any]:
    """The mjs (non-MCP) context-plan defaults agree with the shared preset
    registry: symbiose-ah 250k/100k/40, never a hardcoded legacy value."""
    import subprocess

    core_js = Path(__file__).parent.parent / "mjs" / "hooks" / "rtr-core.js"
    probe = Path(tempfile.mkdtemp(prefix="rtrre-eb-mjs-")) / "probe.cjs"
    probe.write_text(
        "const c = require(" + json.dumps(str(core_js)) + ");\n"
        "const ctx = c.registryContextProfile();\n"
        "const plan = c.planContext(300000, 60);\n"
        "process.stdout.write(JSON.stringify({ctx, plan}));\n",
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            ["node", str(probe)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    finally:
        probe.unlink(missing_ok=True)
    parsed = {}
    if result.returncode == 0:
        try:
            parsed = json.loads(result.stdout)
        except Exception:  # noqa: BLE001
            parsed = {}
    ctx = parsed.get("ctx") or {}
    plan = parsed.get("plan") or {}
    checks = {
        "registry_preset_symbiose_ah": 1.0
        if ctx.get("preset") == "symbiose-ah"
        else 0.0,
        "plan_trigger_250k": 1.0 if plan.get("triggerTokens") == 250000 else 0.0,
        "plan_target_100k": 1.0 if plan.get("targetTokens") == 100000 else 0.0,
        "plan_maxkeep_40": 1.0 if plan.get("maxKeepMessages") == 40 else 0.0,
    }
    return _verdict(
        checks,
        [
            "registry_preset_symbiose_ah",
            "plan_trigger_250k",
            "plan_target_100k",
            "plan_maxkeep_40",
        ],
        {
            "node_exit": result.returncode,
            "registry": ctx,
            "plan": plan,
        },
        "optimizer-mjs-plan-context-aligned",
        "mjs context-plan defaults agree with the shared preset registry",
    )


@register_case("compressor-incremental-ten-plus-fires")
def case_compressor_incremental_ten_plus() -> Dict[str, Any]:
    """The Compressor fires repeatedly in one context: twelve incremental
    cycles, each growing the live window past the trigger, compressing, and
    verifying the plan is exact (partition, token report, verbatim payload).
    The kept tail is the next cycle's context — the compressor must keep
    succeeding on a context it already compressed, never degrading."""
    _name, preset = keeper_preset("symbiose-ah")
    trigger = int(preset["triggerTokens"])
    target = int(preset["targetTokens"])
    max_keep = int(preset["maxKeepMessages"])
    cfg = {
        "trigger_tokens": trigger,
        "target_tokens": target,
        "max_keep_messages": max_keep,
    }
    messages: List[Dict[str, Any]] = []
    cycles: List[Dict[str, Any]] = []
    for cycle in range(12):
        while sum(estimate_tokens(m.get("text") or "") for m in messages) <= trigger:
            if len(messages) % 7 == 0:
                messages.append(_msg("user", "continue the work"))
            else:
                messages.append(_msg("assistant", _blob(12000)))
        plan = plan_compression(messages, config=cfg)
        n = len(messages)
        keep_set = set(plan["keep"])
        evict_set = set(plan["evict"])
        partition_ok = keep_set.isdisjoint(evict_set) and (keep_set | evict_set) == set(
            range(n)
        )
        recomputed = sum(
            estimate_tokens(messages[i].get("text") or "") for i in plan["keep"]
        )
        tokens_ok = recomputed == plan["keep_tokens"]
        verbatim_ok = all(
            mask_ndata(messages[p["index"]].get("text")) == p["text"]
            for p in plan["evict_payload"]
        )
        ndata_masked = all(
            not re.search(r"[A-Za-z0-9+/]{64,}={0,2}", p["text"])
            for p in plan["evict_payload"]
        )
        slack_ok = plan["keep_tokens"] <= target + 8000
        cycle_ok = (
            bool(plan["compress"])
            and partition_ok
            and tokens_ok
            and verbatim_ok
            and ndata_masked
            and slack_ok
        )
        cycles.append(
            {
                "cycle": cycle + 1,
                "messages": n,
                "total_tokens": plan["total_tokens"],
                "keep_tokens": plan["keep_tokens"],
                "evicted_tokens": plan["total_tokens"] - plan["keep_tokens"],
                "keep_ratio": round(plan["keep_tokens"] / plan["total_tokens"], 6),
                "evicted": len(plan["evict"]),
                "compress": plan["compress"],
                "partition_ok": partition_ok,
                "tokens_ok": tokens_ok,
                "verbatim_ok": verbatim_ok,
                "ndata_masked": ndata_masked,
                "slack_ok": slack_ok,
            }
        )
        messages = [messages[i] for i in plan["keep"]]
    checks = {
        "all_twelve_cycles_fired": 1.0 if all(c["compress"] for c in cycles) else 0.0,
        "all_partitions_exact": 1.0 if all(c["partition_ok"] for c in cycles) else 0.0,
        "all_token_reports_exact": 1.0 if all(c["tokens_ok"] for c in cycles) else 0.0,
        "all_payloads_verbatim": 1.0 if all(c["verbatim_ok"] for c in cycles) else 0.0,
        "all_ndata_masked": 1.0 if all(c["ndata_masked"] for c in cycles) else 0.0,
        "all_within_budget_slack": 1.0 if all(c["slack_ok"] for c in cycles) else 0.0,
    }
    return _verdict(
        checks,
        [
            "all_twelve_cycles_fired",
            "all_partitions_exact",
            "all_token_reports_exact",
            "all_payloads_verbatim",
            "all_ndata_masked",
            "all_within_budget_slack",
        ],
        {"cycles": cycles},
        "compressor-incremental-ten-plus-fires",
        "Compressor fires 12 incremental times in one context, exact each time",
    )


@register_case("compressor-session-resume-cumulative")
def case_compressor_session_resume_cumulative() -> Dict[str, Any]:
    """The Compressor survives session resumes: the cumulative counter
    persists atomically across worker instances (never reset), and
    compression fires in every resumed session."""
    cfg = {"trigger_tokens": 100, "target_tokens": 30, "max_keep_messages": 2}
    with tempfile.TemporaryDirectory(prefix="rtrre-eb-resume-") as temporary:
        root = Path(temporary)
        cumulative_path = root / "cumulative.json"
        sink = SessionSpanSink(root / "sessions")
        worker1 = SymbioseWorker(
            sink=sink, config=cfg, cumulative_path=str(cumulative_path)
        )
        try:
            t1 = worker1.submit([_msg("assistant", _blob(12000)) for _ in range(6)])
            r1 = worker1.wait(t1["id"], timeout=30)
        finally:
            worker1.close()
        state1 = json.loads(cumulative_path.read_text(encoding="utf-8"))
        cum1 = int(state1.get("cumulative_messages", 0))
        worker2 = SymbioseWorker(
            sink=sink, config=cfg, cumulative_path=str(cumulative_path)
        )
        try:
            t2 = worker2.submit([_msg("assistant", _blob(12000)) for _ in range(6)])
            r2 = worker2.wait(t2["id"], timeout=30)
        finally:
            worker2.close()
        state2 = json.loads(cumulative_path.read_text(encoding="utf-8"))
        cum2 = int(state2.get("cumulative_messages", 0))
        tmp_leftovers = list((root).glob("cumulative.json.tmp"))
        checks = {
            "session1_compressed": 1.0
            if r1.get("status") == "ready" and r1.get("evicted", 0) > 0
            else 0.0,
            "cumulative_persisted_session1": 1.0 if cum1 == 6 else 0.0,
            "session2_resumed_compressed": 1.0
            if r2.get("status") == "ready" and r2.get("evicted", 0) > 0
            else 0.0,
            "cumulative_grew_across_resume": 1.0 if cum2 == 12 else 0.0,
            "atomic_write_no_tmp_leftovers": 1.0 if not tmp_leftovers else 0.0,
        }
        return _verdict(
            checks,
            [
                "session1_compressed",
                "cumulative_persisted_session1",
                "session2_resumed_compressed",
                "cumulative_grew_across_resume",
                "atomic_write_no_tmp_leftovers",
            ],
            {
                "cumulative_after_session1": cum1,
                "cumulative_after_session2": cum2,
                "session1_ticket": r1,
                "session2_ticket": r2,
                "tmp_leftovers": [str(p) for p in tmp_leftovers],
            },
            "compressor-session-resume-cumulative",
            "Compressor survives session resumes; cumulative persists atomically",
        )


@register_case("compressor-double-duty-after-keeper-trim")
def case_compressor_double_duty_after_keeper_trim() -> Dict[str, Any]:
    """The Compressor acts where the keeper stops: when the keeper has
    already trimmed by message count (small max_keep_messages) but the kept
    window still exceeds the token trigger, the Compressor must still fire
    and reduce tokens — the second line of defense."""
    _name, preset = keeper_preset("symbiose-ah")
    trigger = int(preset["triggerTokens"])
    target = int(preset["targetTokens"])
    cfg = {
        "trigger_tokens": trigger,
        "target_tokens": target,
        "max_keep_messages": 10,
    }
    messages = [_msg("assistant", _blob(12000)) for _ in range(90)]
    plan = plan_compression(messages, config=cfg)
    checks = {
        "fires_over_trigger": 1.0 if plan["compress"] else 0.0,
        "kept_within_keeper_cap": 1.0 if len(plan["keep"]) <= 10 else 0.0,
        "kept_tokens_reduced": 1.0
        if plan["keep_tokens"] < plan["total_tokens"]
        else 0.0,
        "evict_nonempty": 1.0 if plan["evict"] else 0.0,
    }
    return _verdict(
        checks,
        [
            "fires_over_trigger",
            "kept_within_keeper_cap",
            "kept_tokens_reduced",
            "evict_nonempty",
        ],
        {
            "total_tokens": plan["total_tokens"],
            "keep_tokens": plan["keep_tokens"],
            "kept_messages": len(plan["keep"]),
            "evicted_messages": len(plan["evict"]),
            "keep_ratio": round(plan["keep_tokens"] / plan["total_tokens"], 6),
        },
        "compressor-double-duty-after-keeper-trim",
        "Compressor acts on tokens after the keeper has trimmed by count",
    )


def _index_evicted_sessions(
    root: Path, messages: List[Dict[str, Any]], cfg: Dict[str, Any], digest: str
) -> Dict[str, Any]:
    """Shared setup for the retrievability and lexikon cases: compress,
    sink evicted spans, index the project, return the engine + facts."""
    import memory_engine as mem

    proj = root / "projects"
    sessions = proj / ".opencode" / "memory"
    sessions.mkdir(parents=True)
    sink = SessionSpanSink(sessions)
    plan = plan_compression(messages, config=cfg)
    sink_path = sink(plan["evict_payload"], digest=digest)
    old_db = os.environ.get("OPENCODE_MEMORY_DB_DIR")
    old_suffixes = os.environ.get("OPENCODE_MEMORY_FILE_SUFFIXES")
    old_models = os.environ.get("OPENCODE_MEMORY_EMBED_MODELS")
    old_roots = mem.PROJECT_ROOTS
    old_projects = mem.PROJECTS_DIR
    old_registry = mem.REGISTRY_FILE
    old_extra = mem.EXTRA_ROOTS_FILE
    old_lex = mem.LEXIKON_GLOBAL_FILE
    os.environ["OPENCODE_MEMORY_DB_DIR"] = str(root / "db")
    os.environ["OPENCODE_MEMORY_FILE_SUFFIXES"] = (
        ".md,.nt,.yaml,.yml,.dita,.xml,.dtd,.mod,.ent"
    )
    os.environ["OPENCODE_MEMORY_EMBED_MODELS"] = "BAAI/bge-small-en-v1.5"
    mem.PROJECT_ROOTS = [proj]
    mem.PROJECTS_DIR = proj
    mem.REGISTRY_FILE = root / "registry.json"
    mem.EXTRA_ROOTS_FILE = root / "extra_roots.json"
    mem.LEXIKON_GLOBAL_FILE = root / "lexikon_global.json"
    engine = mem.MemoryEngine()
    stats = engine.index_all(force=True)
    return {
        "engine": engine,
        "plan": plan,
        "sink_path": Path(sink_path),
        "stats": stats,
        "restore": {
            "old_db": old_db,
            "old_suffixes": old_suffixes,
            "old_models": old_models,
            "old_roots": old_roots,
            "old_projects": old_projects,
            "old_registry": old_registry,
            "old_extra": old_extra,
            "old_lex": old_lex,
        },
    }


def _restore_index_env(root: Path, facts: Dict[str, Any]) -> None:
    import memory_engine as mem

    rest = facts["restore"]
    if rest["old_db"] is None:
        os.environ.pop("OPENCODE_MEMORY_DB_DIR", None)
    else:
        os.environ["OPENCODE_MEMORY_DB_DIR"] = rest["old_db"]
    if rest["old_suffixes"] is None:
        os.environ.pop("OPENCODE_MEMORY_FILE_SUFFIXES", None)
    else:
        os.environ["OPENCODE_MEMORY_FILE_SUFFIXES"] = rest["old_suffixes"]
    if rest["old_models"] is None:
        os.environ.pop("OPENCODE_MEMORY_EMBED_MODELS", None)
    else:
        os.environ["OPENCODE_MEMORY_EMBED_MODELS"] = rest["old_models"]
    mem.PROJECT_ROOTS = rest["old_roots"]
    mem.PROJECTS_DIR = rest["old_projects"]
    mem.REGISTRY_FILE = rest["old_registry"]
    mem.EXTRA_ROOTS_FILE = rest["old_extra"]
    mem.LEXIKON_GLOBAL_FILE = rest["old_lex"]


@register_case("compressor-evicted-retrievable-via-memory-search")
def case_compressor_evicted_retrievable() -> Dict[str, Any]:
    """Evicted spans are retrievable: after compression sinks them and the
    project is indexed, memory_search finds the distinctive evicted content
    in the session file."""
    _name, preset = keeper_preset("symbiose-ah")
    cfg = {
        "trigger_tokens": int(preset["triggerTokens"]),
        "target_tokens": int(preset["targetTokens"]),
        "max_keep_messages": int(preset["maxKeepMessages"]),
    }
    marker = "quasar-nebula-x7"
    messages = [_msg("assistant", f"{marker} {_cdata_long(12000)}") for _ in range(90)]
    with tempfile.TemporaryDirectory(prefix="rtrre-eb-retr-") as temporary:
        root = Path(temporary)
        facts = _index_evicted_sessions(root, messages, cfg, "retr-test")
        engine = facts["engine"]
        try:
            results = engine.search(marker, k=3, project=None)
            top = [Path(r["metadata"]["source"]).name for r in results]
            found = any(name.startswith("rtrre-retr-test.dtd") for name in top)
            checks = {
                "compressed": 1.0 if facts["plan"]["compress"] else 0.0,
                "sink_wrote_file": 1.0 if facts["sink_path"].exists() else 0.0,
                "memory_search_finds_evicted": 1.0 if found else 0.0,
            }
            return _verdict(
                checks,
                ["compressed", "sink_wrote_file", "memory_search_finds_evicted"],
                {
                    "sink_file": facts["sink_path"].name,
                    "indexed_new": facts["stats"].get("new"),
                    "top": top,
                },
                "compressor-evicted-retrievable-via-memory-search",
                "Evicted spans are retrievable via memory_search after indexing",
            )
        finally:
            engine.close()
            _restore_index_env(root, facts)


@register_case("compressor-lexikon-interplay")
def case_compressor_lexikon_interplay() -> Dict[str, Any]:
    """The lexikon lane reaches evicted content: after compression sinks and
    indexes it, a lexikon alias seeded from the evicted vocabulary expands a
    short query into the full compound, and the session file is retrieved."""
    _name, preset = keeper_preset("symbiose-ah")
    cfg = {
        "trigger_tokens": int(preset["triggerTokens"]),
        "target_tokens": int(preset["targetTokens"]),
        "max_keep_messages": int(preset["maxKeepMessages"]),
    }
    compound = "quasarnebularx7"
    messages = [
        _msg("assistant", f"{compound} {_cdata_long(12000)}") for _ in range(90)
    ]
    with tempfile.TemporaryDirectory(prefix="rtrre-eb-lex-") as temporary:
        root = Path(temporary)
        facts = _index_evicted_sessions(root, messages, cfg, "lex-test")
        engine = facts["engine"]
        try:
            proj = str(root / "projects")
            engine.add_lexikon_term(
                proj,
                compound,
                definition=f"{compound} evicted test compound",
                aliases=["nebula"],
            )
            lex, _ = engine.build_expansions("nebula", proj)
            expanded = any(compound in str(x) for x in lex)
            results = engine.search("nebula", k=3, project=None)
            top = [Path(r["metadata"]["source"]).name for r in results]
            found = any(name.startswith("rtrre-lex-test.dtd") for name in top)
            checks = {
                "compressed": 1.0 if facts["plan"]["compress"] else 0.0,
                "lexikon_expands_to_evicted_term": 1.0 if expanded else 0.0,
                "alias_query_retrieves_evicted": 1.0 if found else 0.0,
            }
            return _verdict(
                checks,
                [
                    "compressed",
                    "lexikon_expands_to_evicted_term",
                    "alias_query_retrieves_evicted",
                ],
                {
                    "sink_file": facts["sink_path"].name,
                    "expansions": [str(x) for x in lex],
                    "top": top,
                },
                "compressor-lexikon-interplay",
                "Lexikon lane reaches evicted content",
            )
        finally:
            engine.close()
            _restore_index_env(root, facts)


def run_all() -> Dict[str, Any]:
    """Run every registered case and aggregate into a scoreboard that can go red."""
    case_results: List[Dict[str, Any]] = []
    for name in all_cases():
        try:
            case_results.append(_CASES[name]())
        except Exception as exc:  # noqa: BLE001
            case_results.append(
                {
                    "case": name,
                    "description": "case raised",
                    "checks": {},
                    "required": [],
                    "verdict": "fail",
                    "failed_required": ["case-raise"],
                    "evidence": {"error": str(exc)},
                }
            )
    passed = sum(1 for r in case_results if r["verdict"] == "pass")
    failed = len(case_results) - passed
    return {
        "schema": "rtr-re.engine-beneath.cases/v1",
        "scope": "RE edition: full architecture case registry",
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": {
            "cases": len(case_results),
            "passed": passed,
            "failed": failed,
            "pass": passed == len(case_results),
        },
        "cases": case_results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    out_dir = Path(__file__).parent.parent / "eval" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    result = run_all()
    json_path = out_dir / "engine-beneath-cases.json"
    json_path.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    md_path = out_dir / "engine-beneath-cases.md"
    lines = [
        "# Engine Beneath — case scoreboard (RE edition)",
        "",
        f"- Run: {result['run_at']}",
        f"- Cases: {result['summary']['cases']} — passed {result['summary']['passed']}, failed {result['summary']['failed']}",
        f"- Verdict: **{('PASS' if result['summary']['pass'] else 'FAIL')}**",
        "",
        "| Case | Verdict | Required checks |",
        "|---|---|---|",
    ]
    for case in result["cases"]:
        required = ", ".join(case["required"]) or "(none)"
        lines.append(f"| {case['case']} | {case['verdict']} | {required} |")
    lines.append("")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"WROTE {json_path}")
    print(f"WROTE {md_path}")
    print(f"VERDICT {result['summary']['pass']}")
    return 0 if result["summary"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
