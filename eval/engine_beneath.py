# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Read-only message lineage for the Engine Beneath evaluation.

The record identifies where each original message goes under the
existing context planner. It stores hashes and measurements, never the
message text, so an evaluation record cannot quietly become a second copy
of the conversation.
"""

import hashlib
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).parent.parent / "execution"))

from context_budget import (  # noqa: E402
    PROTECTED_TOOLS,
    estimate_tokens,
    mask_ndata,
    plan_compression,
    span_dtype,
    span_lane,
)
from symbiose_worker import SessionSpanSink, SymbioseWorker  # noqa: E402


def _message_text(message: Mapping[str, Any]) -> str:
    value = message.get("text") or message.get("content") or ""
    if isinstance(value, str):
        return value
    parts = message.get("parts")
    if isinstance(parts, list):
        chunks: List[str] = []
        for part in parts:
            if not isinstance(part, Mapping):
                continue
            text = part.get("text")
            if isinstance(text, str):
                chunks.append(text)
                continue
            state = part.get("state")
            if isinstance(state, Mapping) and isinstance(state.get("output"), str):
                chunks.append(state["output"])
        return "\n".join(chunks)
    return str(value)


def _message_id(message: Mapping[str, Any]) -> str | None:
    raw = message.get("id")
    if raw is not None:
        return str(raw)
    info = message.get("info")
    if isinstance(info, Mapping) and info.get("id") is not None:
        return str(info["id"])
    return None


def _message_role(message: Mapping[str, Any]) -> str:
    raw = message.get("role")
    if raw is not None:
        return str(raw)
    info = message.get("info")
    if isinstance(info, Mapping) and info.get("role") is not None:
        return str(info["role"])
    return "unknown"


def _message_tool(message: Mapping[str, Any]) -> str | None:
    raw = message.get("tool")
    if raw is not None:
        return str(raw)
    parts = message.get("parts")
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, Mapping) and part.get("tool") is not None:
                return str(part["tool"])
    return None


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _dispositions(plan: Mapping[str, Any], count: int) -> Dict[int, str]:
    kept = {int(i) for i in plan.get("keep", [])}
    evicted = {int(i) for i in plan.get("evict", [])}
    result: Dict[int, str] = {}
    for index in range(count):
        if index in kept and index not in evicted:
            result[index] = "retained"
        elif index in evicted and index not in kept:
            result[index] = "evicted"
        else:
            result[index] = "unaccounted"
    return result


def build_lineage(
    messages: Iterable[Mapping[str, Any]],
    *,
    config: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Return a deterministic, text-free lineage record for *messages*.

    ``plan_compression`` remains the only keeper planner. This function
    only measures and labels its decision; it does not copy, reorder, or
    mutate the input messages.
    """

    originals = list(messages)
    effective_config = dict(config or {})
    plan = plan_compression(
        originals,  # type: ignore[arg-type] - planner accepts mappings.
        config=effective_config or None,
    )
    dispositions = _dispositions(plan, len(originals))
    payload_by_index = {
        int(item["index"]): item for item in plan.get("evict_payload", [])
    }

    records: List[Dict[str, Any]] = []
    for index, message in enumerate(originals):
        text = _message_text(message)
        masked = mask_ndata(text)
        tool = _message_tool(message)
        payload = payload_by_index.get(index)
        records.append(
            {
                "index": index,
                "id": _message_id(message),
                "role": _message_role(message),
                "tool": tool,
                "protected": tool in PROTECTED_TOOLS,
                "lane": span_lane(dict(message)),
                "dtype": span_dtype(text),
                "chars": len(text),
                "estimated_tokens": estimate_tokens(text),
                "sha256": _sha256(text),
                "evicted_text_sha256": (
                    _sha256(str(payload.get("text", "")))
                    if payload is not None
                    else None
                ),
                "evicted_text_chars": (
                    len(str(payload.get("text", ""))) if payload is not None else None
                ),
                "verbatim_after_masking": (
                    str(payload.get("text", "")) == masked
                    if payload is not None
                    else None
                ),
                "disposition": dispositions[index],
            }
        )

    kept = [int(i) for i in plan.get("keep", [])]
    evicted = [int(i) for i in plan.get("evict", [])]
    total_tokens = int(plan.get("total_tokens", 0))
    keep_tokens = int(plan.get("keep_tokens", 0))
    summary = {
        "total_messages": len(records),
        "retained_messages": sum(
            1 for record in records if record["disposition"] == "retained"
        ),
        "evicted_messages": sum(
            1 for record in records if record["disposition"] == "evicted"
        ),
        "unaccounted_messages": sum(
            1 for record in records if record["disposition"] == "unaccounted"
        ),
        "total_tokens_estimate": total_tokens,
        "kept_tokens_estimate": keep_tokens,
        "evicted_tokens_estimate": max(0, total_tokens - keep_tokens),
        "kept_token_ratio": (keep_tokens / total_tokens if total_tokens else 1.0),
        "retained_tail_start": min(kept) if kept else None,
        "compress": bool(plan.get("compress", False)),
    }
    return {
        "schema": "rtr-re.engine-beneath.lineage/v1",
        "config": effective_config,
        "plan": {
            "compress": bool(plan.get("compress", False)),
            "keep": kept,
            "evict": evicted,
            "total_tokens": total_tokens,
            "keep_tokens": keep_tokens,
        },
        "summary": summary,
        "messages": records,
    }


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def _sink_span_count(sink_text: str) -> int:
    """Count spans in the sink file, both standards.

    Primary (TODO-70): DTD-shaped spans — one ``<span id="...">`` element
    per evicted record. Legacy fallback: the pre-2.0 markdown marker
    ``## span ``. The count must equal the expected evicted-span count for
    the sink checks to pass.
    """
    dtd_spans = sink_text.count("<span id=")
    if dtd_spans:
        return dtd_spans
    return sink_text.count("## span ")


def evaluate_conversation(
    messages: Iterable[Mapping[str, Any]],
    *,
    config: Mapping[str, Any] | None = None,
    markers: Iterable[str] = (),
    sink_directory: Path | None = None,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """Evaluate one conversation through planner, worker, and file sink.

    The worker receives plain message mappings. Host-shaped messages with
    nested ``info``/``parts`` are normalized only for this evaluation; the
    caller's objects are never changed.
    """

    originals = list(messages)
    lineage = build_lineage(originals, config=config)
    worker_messages: List[Dict[str, Any]] = []
    for message in originals:
        normalized: Dict[str, Any] = {
            "role": _message_role(message),
            "text": _message_text(message),
        }
        tool = _message_tool(message)
        if tool:
            normalized["tool"] = tool
        if message.get("tool_call"):
            normalized["tool_call"] = True
        token_value = message.get("tokens")
        if isinstance(token_value, (int, float)) and token_value > 0:
            normalized["tokens"] = token_value
        worker_messages.append(normalized)

    with tempfile.TemporaryDirectory(prefix="rtrre-engine-beneath-") as temporary:
        sink_root = Path(sink_directory) if sink_directory else Path(temporary)
        worker = SymbioseWorker(
            SessionSpanSink(sink_root),
            cooldown_seconds=0,
            config=dict(config or {}) or None,
        )
        try:
            ticket = worker.submit(worker_messages)
            completed = worker.wait(int(ticket["id"]), timeout=timeout)
        finally:
            worker.close()

        sink_value = completed.get("sink")
        sink_path = Path(sink_value) if isinstance(sink_value, (str, Path)) else None
        sink_bytes = sink_path.read_bytes() if sink_path and sink_path.exists() else b""
        sink_text = sink_bytes.decode("utf-8", errors="replace")
        sink_info = {
            "path": str(sink_path) if sink_path else None,
            "exists": bool(sink_path and sink_path.exists()),
            "bytes": len(sink_bytes),
            "sha256": hashlib.sha256(sink_bytes).hexdigest() if sink_bytes else None,
            "span_markers": _sink_span_count(sink_text),
        }

    records = lineage["messages"]
    evicted_records = [r for r in records if r["disposition"] == "evicted"]
    protected_records = [r for r in records if r["protected"]]
    sink_span_count = int(sink_info["span_markers"])
    expected_sink_spans = len(evicted_records)
    sink_matches = sink_span_count == expected_sink_spans and (
        expected_sink_spans == 0 or bool(sink_info["exists"])
    )

    kept_text = "\n".join(
        _message_text(originals[int(record["index"])])
        for record in records
        if record["disposition"] == "retained"
    )
    marker_values = [str(marker) for marker in markers if str(marker)]
    marker_in_sink = sum(1 for marker in marker_values if marker in sink_text)
    marker_absent_from_kept = sum(
        1 for marker in marker_values if marker not in kept_text
    )
    verbatim_records = [
        record for record in evicted_records if record["verbatim_after_masking"] is True
    ]

    checks = {
        "all_messages_accounted": _ratio(
            len(records) - int(lineage["summary"]["unaccounted_messages"]),
            len(records),
        ),
        "protected_retained": _ratio(
            sum(1 for r in protected_records if r["disposition"] == "retained"),
            len(protected_records),
        ),
        "worker_ready": 1.0 if completed.get("status") == "ready" else 0.0,
        "sink_contains_evicted_spans": 1.0 if sink_matches else 0.0,
        "evicted_verbatim_after_ndata_masking": _ratio(
            len(verbatim_records), len(evicted_records)
        ),
        "marker_in_evicted_sink": _ratio(marker_in_sink, len(marker_values)),
        "marker_absent_from_kept_tail": _ratio(
            marker_absent_from_kept, len(marker_values)
        ),
        "context_reduction": 1.0 - float(lineage["summary"]["kept_token_ratio"]),
    }
    required = [
        "all_messages_accounted",
        "protected_retained",
        "worker_ready",
        "sink_contains_evicted_spans",
        "evicted_verbatim_after_ndata_masking",
        "marker_in_evicted_sink",
        "marker_absent_from_kept_tail",
    ]
    return {
        "schema": "rtr-re.engine-beneath/v1",
        "scope": "planner + background compressor + verbatim file sink",
        "config": dict(config or {}),
        "lineage": lineage,
        "worker": {
            key: completed.get(key)
            for key in (
                "id",
                "hash",
                "status",
                "submit_ms",
                "queue_ms",
                "plan_ms",
                "sink_ms",
                "elapsed_ms",
                "duration",
                "total_tokens",
                "keep_tokens",
                "evicted_tokens",
                "keep_ratio",
                "evicted",
                "sink_bytes",
                "error",
            )
            if key in completed
        },
        "sink": sink_info,
        "checks": checks,
        "verdict": "pass" if all(checks[key] == 1.0 for key in required) else "fail",
    }


SearchFunction = Callable[[str, int], Sequence[Mapping[str, Any]]]


def _result_id(result: Mapping[str, Any], rank: int) -> str:
    raw = result.get("id")
    if raw is not None:
        return str(raw)
    metadata = result.get("metadata")
    if isinstance(metadata, Mapping):
        for key in ("chunk_id", "id", "source", "rel_path"):
            if metadata.get(key) is not None:
                return str(metadata[key])
    return f"rank-{rank}"


def _result_matches(result: Mapping[str, Any], expected_terms: Sequence[str]) -> bool:
    if not expected_terms:
        return False
    values: List[str] = []
    for key in ("id", "document", "text", "content"):
        if result.get(key) is not None:
            values.append(str(result[key]))
    metadata = result.get("metadata")
    if isinstance(metadata, Mapping):
        for key in ("chunk_id", "id", "source", "rel_path", "title"):
            if metadata.get(key) is not None:
                values.append(str(metadata[key]))
    haystack = "\n".join(values).casefold()
    return all(str(term).casefold() in haystack for term in expected_terms if str(term))


def evaluate_retrieval(
    search: SearchFunction,
    queries: Iterable[Mapping[str, Any]],
    *,
    depths: Iterable[int] = (1, 3, 5),
) -> Dict[str, Any]:
    """Measure returned rank and recall without retaining result text.

    ``search`` is any callable accepting ``(query, k)`` and returning
    mapping-shaped results. Keeping this boundary small lets the same
    instrument measure MemoryEngine, the native CLI adapter, MCP, or a
    deterministic test double without confusing their evidence.
    """

    depth_values = sorted({int(depth) for depth in depths if int(depth) > 0})
    if not depth_values:
        raise ValueError("at least one positive retrieval depth is required")
    max_depth = max(depth_values)

    query_records: List[Dict[str, Any]] = []
    for position, query in enumerate(queries):
        query_id = str(query.get("id") or f"query-{position}")
        query_text = str(query.get("text") or query.get("query") or "")
        expected_terms = [
            str(term) for term in query.get("expected_terms", []) if str(term)
        ]
        results = list(search(query_text, max_depth))[:max_depth]
        returned_ids = [
            _result_id(result, rank) for rank, result in enumerate(results, start=1)
        ]
        returned_paths: List[str | None] = []
        returned_scores: List[float | None] = []
        matches: List[bool] = []
        for result in results:
            metadata = result.get("metadata")
            path = None
            if isinstance(metadata, Mapping):
                raw_path = metadata.get("rel_path") or metadata.get("source")
                path = str(raw_path) if raw_path is not None else None
            returned_paths.append(path)
            raw_score = result.get("score")
            returned_scores.append(
                float(raw_score) if isinstance(raw_score, (int, float)) else None
            )
            matches.append(_result_matches(result, expected_terms))

        hit_ranks = [rank for rank, matched in enumerate(matches, start=1) if matched]
        first_hit_rank = hit_ranks[0] if hit_ranks else None
        query_records.append(
            {
                "id": query_id,
                "expected_terms": expected_terms,
                "returned_ids": returned_ids,
                "returned_paths": returned_paths,
                "returned_scores": returned_scores,
                "returned_count": len(results),
                "first_hit_rank": first_hit_rank,
                "reciprocal_rank": (1.0 / first_hit_rank if first_hit_rank else 0.0),
                "hit_at": {depth: any(matches[:depth]) for depth in depth_values},
            }
        )

    total = len(query_records)
    return {
        "schema": "rtr-re.engine-beneath.retrieval/v1",
        "depths": depth_values,
        "summary": {
            "queries": total,
            "recall_at": {
                depth: _ratio(
                    sum(1 for record in query_records if record["hit_at"][depth]),
                    total,
                )
                if total
                else 0.0
                for depth in depth_values
            },
            "mean_reciprocal_rank": (
                sum(float(record["reciprocal_rank"]) for record in query_records)
                / total
                if total
                else 0.0
            ),
        },
        "queries": query_records,
    }
