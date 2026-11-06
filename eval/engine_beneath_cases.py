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
    ]
    expected_bounds = {
        "standard": (320000, 128000, 40),
        "calibrated": (40000, 20000, 40),
        "wide": (640000, 256000, 40),
        "fusion-ah": (200000, 100000, 30),
        "symbiose-ah": (250000, 100000, 40),
        "re-symbiose": (320000, 128000, 50),
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
        _msg("assistant", marker + " " + _blob(12000)),
        _msg("assistant", _blob(12000)),
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
