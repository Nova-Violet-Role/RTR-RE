# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""RE:Symbiose compression-time calibration on generated real text loads.

Measures the background compressor as users experience it:

* submit latency — the caller-visible pause (must stay near zero);
* queue, planning and sink stages returned on the completed ticket;
* total background completion time at several context sizes.

By default each workload is compressed to one half of its context size.
Use --trigger and --target to mirror a deployment profile instead, for
example the live-survey calibration profile of 40k -> 20k tokens.

This measures the stdlib planner/worker/file-sink pipeline. It does not
load ONNX models and does not claim to time later vector indexing.
"""

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

sys.path.insert(0, str(Path(__file__).parent.parent / "execution"))

from symbiose_worker import SessionSpanSink, SymbioseWorker, format_duration_ms


def parse_token_count(raw: str) -> int:
    """Parse an integer token count, accepting a decimal k suffix."""
    value = raw.strip().lower()
    multiplier = 1000 if value.endswith("k") else 1
    if multiplier == 1000:
        value = value[:-1]
    try:
        parsed = int(float(value) * multiplier)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid token count: {raw!r}") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("token counts must be positive")
    return parsed


def generate_messages(
    total_tokens: int,
    *,
    message_count: int = 40,
    salt: str = "run",
) -> List[Dict[str, Any]]:
    """Generate deterministic text whose planner estimate is total_tokens.

    The planner estimates four characters per token. The final message is
    the latest user turn; earlier lanes alternate read and written context.
    """
    if total_tokens <= 0:
        raise ValueError("total_tokens must be positive")
    if message_count <= 0:
        raise ValueError("message_count must be positive")

    total_chars = total_tokens * 4
    base_chars, remainder = divmod(total_chars, message_count)
    # Varied prose/code/path text is a less flattering and more credible CPU
    # workload than one repeated character. Tokens/s remains an upper bound
    # for this synthetic pipeline and excludes model indexing entirely.
    block = (
        "The keeper protects the newest instructions while the compressor "
        "moves older spans to C:/work/project/directives/sessions. Run "
        "`memory_search` for router6834, inspect the DTD type histogram, "
        "compare BM25 with dense ranks, and preserve exact identifiers, "
        "paths, decisions, errors, and rationale across both read and "
        "written context. "
    )
    messages: List[Dict[str, Any]] = []
    for index in range(message_count):
        chars = base_chars + (1 if index < remainder else 0)
        marker = f"[{salt}:{index}] "
        repeats = (chars // len(block)) + 2
        text = (marker + (block * repeats))[:chars]
        role = (
            "user"
            if index == message_count - 1
            else ("assistant" if index % 2 else "user")
        )
        messages.append({"role": role, "text": text})
    return messages


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(
        0,
        min(
            len(ordered) - 1, int(round((percentile / 100.0) * len(ordered) + 0.5) - 1)
        ),
    )
    return float(ordered[rank])


def summarize(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(int(record["context_tokens"]), []).append(record)

    summary: List[Dict[str, Any]] = []
    fields = ("submit_ms", "queue_ms", "plan_ms", "sink_ms", "elapsed_ms")
    for context_tokens in sorted(grouped):
        rows = grouped[context_tokens]
        item: Dict[str, Any] = {
            "context_tokens": context_tokens,
            "repetitions": len(rows),
            "ready": sum(1 for r in rows if r["status"] == "ready"),
        }
        for field in fields:
            values = [float(r.get(field) or 0.0) for r in rows]
            item[field] = {
                "min": round(min(values), 3),
                "median": round(statistics.median(values), 3),
                "mean": round(statistics.fmean(values), 3),
                "p95": round(_percentile(values, 95), 3),
                "max": round(max(values), 3),
                "median_human": format_duration_ms(statistics.median(values)),
            }
        elapsed_median = float(item["elapsed_ms"]["median"])
        item["tokens_per_second_median"] = (
            round(context_tokens / (elapsed_median / 1000.0), 3)
            if elapsed_median > 0
            else 0.0
        )
        summary.append(item)
    return summary


def write_markdown(path: Path, payload: Dict[str, Any]) -> None:
    lines = [
        "<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->",
        "<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->",
        "# RE:Symbiose compression calibration (generated, do not edit)",
        "",
        "Background compression never pauses the caller: submit latency is the",
        "caller-visible pause; elapsed time completes on the worker thread.",
        "",
        "| Context | Reps ready | Submit median | Queue median | Plan median | Sink median | Complete median | Complete p95 | Tokens/s |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["summary"]:
        lines.append(
            "| {ctx} | {ready}/{reps} | {submit} | {queue} | {plan} | {sink} | "
            "{elapsed} | {p95} | {tps:.1f} |".format(
                ctx=row["context_tokens"],
                ready=row["ready"],
                reps=row["repetitions"],
                submit=row["submit_ms"]["median_human"],
                queue=row["queue_ms"]["median_human"],
                plan=row["plan_ms"]["median_human"],
                sink=row["sink_ms"]["median_human"],
                elapsed=row["elapsed_ms"]["median_human"],
                p95=format_duration_ms(row["elapsed_ms"]["p95"]),
                tps=row["tokens_per_second_median"],
            )
        )
    lines.extend(
        [
            "",
            f"Profile: trigger={payload['profile']['trigger']}, "
            f"target={payload['profile']['target']}, sink={payload['profile']['sink']}.",
            "Workloads use deterministic varied synthetic text. Tokens/s is a",
            "pipeline upper bound, not a model or retrieval-quality claim.",
            "ONNX indexing is intentionally excluded; this tool times planning,",
            "background eviction and the verbatim span sink only.",
            "",
        ]
    )
    path.write_bytes("\n".join(lines).encode("utf-8"))


def calibrate(args: argparse.Namespace) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="rtrre-calibration-") as td:
        root = Path(td)
        for context_tokens in args.sizes:
            trigger = args.trigger if args.trigger is not None else context_tokens - 1
            target = args.target if args.target is not None else context_tokens // 2
            if target >= trigger:
                raise ValueError("target must be below trigger for every workload")
            config = {
                "trigger_tokens": trigger,
                "target_tokens": target,
                "max_keep_messages": 10_000,
            }
            for repetition in range(1, args.repetitions + 1):
                salt = f"ctx{context_tokens}-rep{repetition}"
                messages = generate_messages(
                    context_tokens,
                    message_count=args.messages,
                    salt=salt,
                )
                sink_dir = root / salt
                sink = (
                    SessionSpanSink(sink_dir)
                    if args.sink == "file"
                    else (lambda spans: "memory")
                )
                worker = SymbioseWorker(sink, config=config)
                try:
                    external_started = time.perf_counter()
                    ticket = worker.submit(messages)
                    external_submit_ms = (
                        time.perf_counter() - external_started
                    ) * 1000.0
                    started_wait = time.perf_counter()
                    done = worker.wait(ticket["id"], timeout=args.timeout)
                    external_wait_ms = (time.perf_counter() - started_wait) * 1000.0
                finally:
                    worker.close()
                record = {
                    "context_tokens": context_tokens,
                    "repetition": repetition,
                    "status": done.get("status", "unknown"),
                    "external_submit_ms": round(external_submit_ms, 3),
                    "external_wait_ms": round(external_wait_ms, 3),
                    **{
                        key: done.get(key)
                        for key in (
                            "hash",
                            "submit_ms",
                            "hash_ms",
                            "queue_ms",
                            "plan_ms",
                            "sink_ms",
                            "elapsed_ms",
                            "duration",
                            "total_tokens",
                            "keep_tokens",
                            "evicted_tokens",
                            "keep_ratio",
                            "input_messages",
                            "input_chars",
                            "kept_chars",
                            "evict_chars",
                            "sink_bytes",
                            "tokens_per_second",
                            "evicted",
                            "error",
                        )
                        if key in done
                    },
                }
                records.append(record)
                print(
                    f"[calibration] ctx={context_tokens} rep={repetition} "
                    f"status={record['status']} submit={format_duration_ms(external_submit_ms)} "
                    f"complete={done.get('duration', 'unknown')}"
                )
    payload = {
        "tool": "RE:Symbiose compression calibration v1",
        "profile": {
            "trigger": args.trigger if args.trigger is not None else "context-1",
            "target": args.target if args.target is not None else "context/2",
            "sink": args.sink,
            "messages_per_workload": args.messages,
        },
        "records": records,
        "summary": summarize(records),
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="calibrate_symbiose",
        description="Official RE:Symbiose compression-time calibration tool.",
    )
    parser.add_argument(
        "--sizes",
        default="40k,100k,200k,400k",
        help="comma-separated context token sizes (k suffix allowed)",
    )
    parser.add_argument("--repetitions", type=int, default=4)
    parser.add_argument("--messages", type=int, default=40)
    parser.add_argument("--trigger", type=parse_token_count, default=None)
    parser.add_argument("--target", type=parse_token_count, default=None)
    parser.add_argument("--sink", choices=("file", "memory"), default="file")
    parser.add_argument(
        "--timeout", type=float, default=600.0, help="seconds per workload"
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path(__file__).parent / "results" / "calibration.json",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=Path(__file__).parent / "results" / "calibration.md",
    )
    args = parser.parse_args()
    args.sizes = [
        parse_token_count(part) for part in args.sizes.split(",") if part.strip()
    ]
    if not args.sizes or args.repetitions <= 0 or args.messages <= 0:
        parser.error("sizes, repetitions and messages must be positive")

    payload = calibrate(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_bytes(json.dumps(payload, indent=2).encode("utf-8"))
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    write_markdown(args.out_md, payload)
    failures = [r for r in payload["records"] if r["status"] != "ready"]
    print(f"wrote {args.out_json} + {args.out_md}")
    print(f"CALIBRATION {'FAIL' if failures else 'PASS'}: {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
