# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""RTR-RE:Symbiose (RE:Symbiose) background worker: no paused context.

The compressor works in the background and applies its result on the next
turn: submit() returns a ticket immediately, a daemon thread plans
keep/evict and sinks evicted spans (read + written lanes, verbatim,
DTD-typed) for the RTR dual-ONNX index, and poll() reports
pending/ready/failed/cooldown/cached.

Three offices (plan 2026-10-26): the Keeper selects the window, this
worker compresses, RTR manages retrieval. The worker never mutates live
messages. Standard library only.
"""

import hashlib
import json
import queue
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

import context_budget


def format_duration_ms(milliseconds: float) -> str:
    """Format one measured duration for ticket/status surfaces."""
    ms = max(0.0, float(milliseconds))
    if ms < 1000:
        return f"{ms:.1f} ms"
    seconds = ms / 1000.0
    if seconds < 60:
        return f"{seconds:.3f} s"
    minutes = int(seconds // 60)
    return f"{minutes} min {seconds - (minutes * 60):.3f} s"


def _text_of(message: Dict[str, Any]) -> str:
    text = message.get("text") or message.get("content") or ""
    return text if isinstance(text, str) else str(text)


def content_hash(messages: List[Dict[str, Any]]) -> str:
    """Canonical identity of the whole message list.

    Every field participates (role, text/content, tool, tokens, flags):
    role+text alone let unlike budgets/tools cache-hit an unlike plan.
    """
    canonical = json.dumps(
        messages,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class SessionSpanSink:
    """Write evicted spans as one session file the RTR indexer discovers.

    Files land under <project>/directives/sessions/ (is_directive in
    discover_wikis), so the next index_all embeds both lanes with the
    dual ONNX ensemble and DTD typing — no engine change needed.
    """

    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def __call__(self, spans: List[Dict[str, Any]], digest: str = "") -> str:
        self.directory.mkdir(parents=True, exist_ok=True)
        name = f"rtrre-{digest or 'spans'}.md"
        path = self.directory / name
        lines = [
            f"# RE:Symbiose evicted spans {digest}".rstrip(),
            "",
            "Verbatim substance evicted from the live window. "
            "PCDATA/CDATA byte-exact; NDATA masked, never embedded.",
            "",
        ]
        for s in spans:
            lines.append(f"## span {s.get('index', '?')}")
            lines.append(f"role: {s.get('role', 'unknown')}")
            lines.append(f"lane: {s.get('lane', 'read')}")
            lines.append(f"dtype: {s.get('dtype', 'PCDATA')}")
            lines.append("")
            lines.append(str(s.get("text") or ""))
            lines.append("")
        # Bytes, not text mode: Windows text translation would rewrite LF
        # as CRLF. Session spans are UTF-8 with LF endings, byte-exact.
        path.write_bytes(("\n".join(lines)).encode("utf-8"))
        return str(path)


class SymbioseWorker:
    def __init__(
        self,
        sink: Callable[..., Any],
        cooldown_seconds: float = 300,
        max_queue: int = 8,
        max_retained_tickets: int = 512,
        config: Dict[str, Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        if int(max_retained_tickets) < 1:
            raise ValueError(
                f"max_retained_tickets must be positive, got {max_retained_tickets}"
            )
        self._sink = sink
        self._cooldown = float(cooldown_seconds)
        self._max_retained = int(max_retained_tickets)
        self._config = config
        self._clock = clock
        self._q: queue.Queue = queue.Queue(maxsize=max_queue)
        self._tickets: Dict[int, Dict[str, Any]] = {}
        self._submitted_at: Dict[int, float] = {}
        self._cache: Dict[str, int] = {}
        self._next_id = 1
        self._cooldown_until = 0.0
        self._lock = threading.Lock()
        self._closed = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _evict_locked(self) -> None:
        """Bound the completed-ticket store (Lean retainBounded contract).

        Oldest completed tickets go first, with their cache entries;
        pending tickets are never evicted. Caller holds the lock.
        """
        completed = [
            tid
            for tid, t in sorted(self._tickets.items())
            if t.get("status") in ("ready", "failed", "overflow")
        ]
        while len(completed) > self._max_retained:
            tid = completed.pop(0)
            self._tickets.pop(tid, None)
            for digest in [d for d, owner in self._cache.items() if owner == tid]:
                del self._cache[digest]

    def _store_failed_locked(
        self, tid: int, digest: str, error: str, submitted_at: float
    ) -> Dict[str, Any]:
        elapsed_ms = max(0.0, (self._clock() - submitted_at) * 1000.0)
        previous = self._tickets.get(tid, {})
        ticket = {
            **previous,
            "id": tid,
            "hash": digest,
            "status": "failed",
            "error": error,
            "elapsed_ms": round(elapsed_ms, 3),
            "duration": format_duration_ms(elapsed_ms),
        }
        self._tickets[tid] = ticket
        self._evict_locked()
        return dict(ticket)

    def submit(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        submitted_at = self._clock()
        digest = content_hash(messages)
        hash_ms = max(0.0, (self._clock() - submitted_at) * 1000.0)
        input_chars = sum(len(_text_of(m)) for m in messages)
        with self._lock:
            submit_ms = max(0.0, (self._clock() - submitted_at) * 1000.0)
            if self._closed:
                tid = self._next_id
                self._next_id += 1
                self._tickets[tid] = {
                    "id": tid,
                    "hash": digest,
                    "status": "pending",
                    "input_messages": len(messages),
                    "input_chars": input_chars,
                    "hash_ms": round(hash_ms, 3),
                    "submit_ms": round(submit_ms, 3),
                }
                return self._store_failed_locked(
                    tid, digest, "worker is closed", submitted_at
                )
            if digest in self._cache:
                cached = dict(self._tickets.get(self._cache[digest], {}))
                cached.update(
                    {
                        "id": self._cache[digest],
                        "hash": digest,
                        "status": "cached",
                        "cache_hit": True,
                        "hash_ms": round(hash_ms, 3),
                        "submit_ms": round(submit_ms, 3),
                    }
                )
                return cached
            now = self._clock()
            if now < self._cooldown_until:
                retry_after_ms = max(0.0, (self._cooldown_until - now) * 1000.0)
                return {
                    "id": 0,
                    "hash": digest,
                    "status": "cooldown",
                    "retry_after_ms": round(retry_after_ms, 3),
                    "hash_ms": round(hash_ms, 3),
                    "submit_ms": round(submit_ms, 3),
                }
            tid = self._next_id
            self._next_id += 1
            ticket: Dict[str, Any] = {
                "id": tid,
                "hash": digest,
                "status": "pending",
                "input_messages": len(messages),
                "input_chars": input_chars,
                "hash_ms": round(hash_ms, 3),
            }
            try:
                self._q.put_nowait((tid, digest, list(messages), submitted_at))
            except queue.Full:
                ticket["status"] = "overflow"
                ticket["submit_ms"] = round(
                    max(0.0, (self._clock() - submitted_at) * 1000.0), 3
                )
                self._tickets[tid] = ticket
                self._evict_locked()
                return dict(ticket)
            ticket["submit_ms"] = round(
                max(0.0, (self._clock() - submitted_at) * 1000.0), 3
            )
            self._submitted_at[tid] = submitted_at
            self._tickets[tid] = ticket
            return dict(ticket)

    def poll(self, ticket_id: int) -> Dict[str, Any]:
        with self._lock:
            t = self._tickets.get(ticket_id)
            if not t:
                return {"id": ticket_id, "status": "unknown"}
            out = dict(t)
            if out["status"] == "pending" and ticket_id in self._submitted_at:
                elapsed_ms = max(
                    0.0, (self._clock() - self._submitted_at[ticket_id]) * 1000.0
                )
                out["elapsed_ms"] = round(elapsed_ms, 3)
                out["duration"] = format_duration_ms(elapsed_ms)
            return out

    def wait(self, ticket_id: int, timeout: float = 10) -> Dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            t = self.poll(ticket_id)
            if t["status"] in ("ready", "failed"):
                return t
            time.sleep(0.01)
        return self.poll(ticket_id)

    def _run(self) -> None:
        while True:
            if self._closed and self._q.empty():
                return
            try:
                tid, digest, messages, submitted_at = self._q.get(timeout=0.05)
            except queue.Empty:
                continue
            if self._closed:
                # Close semantics: queued work is failed by name, never
                # left pending for a poll that would wait forever.
                with self._lock:
                    self._submitted_at.pop(tid, None)
                    self._store_failed_locked(
                        tid,
                        digest,
                        "worker closed before processing",
                        submitted_at,
                    )
                self._q.task_done()
                continue
            plan: Dict[str, Any] | None = None
            plan_ms = 0.0
            sink_ms = 0.0
            queue_ms = 0.0
            try:
                dequeued_at = self._clock()
                queue_ms = max(0.0, (dequeued_at - submitted_at) * 1000.0)
                plan_started = self._clock()
                plan = context_budget.plan_compression(messages, config=self._config)
                plan_ended = self._clock()
                plan_ms = max(0.0, (plan_ended - plan_started) * 1000.0)
                result = None
                if plan["evict_payload"]:
                    try:
                        result = self._sink(plan["evict_payload"], digest)
                    except TypeError:
                        result = self._sink(plan["evict_payload"])
                completed_at = self._clock()
                sink_ms = max(0.0, (completed_at - plan_ended) * 1000.0)
                elapsed_ms = max(0.0, (completed_at - submitted_at) * 1000.0)
                total_tokens = int(plan["total_tokens"])
                keep_tokens = int(plan["keep_tokens"])
                kept = set(plan["keep"])
                sink_bytes = None
                if isinstance(result, (str, Path)):
                    try:
                        sink_bytes = Path(result).stat().st_size
                    except OSError:
                        sink_bytes = None
                with self._lock:
                    self._cache[digest] = tid
                    previous = self._tickets.get(tid, {})
                    self._tickets[tid] = {
                        **previous,
                        "id": tid,
                        "hash": digest,
                        "status": "ready",
                        "keep": plan["keep"],
                        "evicted": len(plan["evict"]),
                        "sink": result,
                        "queue_ms": round(queue_ms, 3),
                        "plan_ms": round(plan_ms, 3),
                        "sink_ms": round(sink_ms, 3),
                        "elapsed_ms": round(elapsed_ms, 3),
                        "duration": format_duration_ms(elapsed_ms),
                        "total_tokens": total_tokens,
                        "keep_tokens": keep_tokens,
                        "evicted_tokens": max(0, total_tokens - keep_tokens),
                        "keep_ratio": round(keep_tokens / total_tokens, 6)
                        if total_tokens
                        else 1.0,
                        "input_chars": sum(len(_text_of(m)) for m in messages),
                        "kept_chars": sum(
                            len(_text_of(messages[i]))
                            for i in kept
                            if 0 <= i < len(messages)
                        ),
                        "evict_chars": sum(
                            len(str(s.get("text") or "")) for s in plan["evict_payload"]
                        ),
                        "sink_bytes": sink_bytes,
                        "tokens_per_second": round(
                            total_tokens / (elapsed_ms / 1000.0), 3
                        )
                        if elapsed_ms > 0
                        else 0.0,
                    }
                    self._evict_locked()
            except Exception as e:
                failed_at = self._clock()
                elapsed_ms = max(0.0, (failed_at - submitted_at) * 1000.0)
                with self._lock:
                    self._cooldown_until = failed_at + self._cooldown
                    previous = self._tickets.get(tid, {})
                    self._tickets[tid] = {
                        **previous,
                        "id": tid,
                        "hash": digest,
                        "status": "failed",
                        "error": str(e),
                        "queue_ms": round(queue_ms, 3),
                        "plan_ms": round(plan_ms, 3),
                        "sink_ms": round(sink_ms, 3),
                        "elapsed_ms": round(elapsed_ms, 3),
                        "duration": format_duration_ms(elapsed_ms),
                    }
                    self._evict_locked()
            finally:
                with self._lock:
                    self._submitted_at.pop(tid, None)
                self._q.task_done()

    def stats(self) -> Dict[str, Any]:
        """Point-in-time worker health for the MCP status viewport."""
        with self._lock:
            by_status: Dict[str, int] = {}
            for t in self._tickets.values():
                by_status[t.get("status", "unknown")] = (
                    by_status.get(t.get("status", "unknown"), 0) + 1
                )
            return {
                "tickets": len(self._tickets),
                "by_status": by_status,
                "queued": self._q.qsize(),
                "cached_hashes": len(self._cache),
                "max_retained": self._max_retained,
                "closed": self._closed,
            }

    def close(self) -> None:
        with self._lock:
            self._closed = True
        self._thread.join(timeout=2)


def submit_json(worker: "SymbioseWorker", messages_json: str) -> Dict[str, Any]:
    """Tool-core for memory_symbiose_submit: JSON data in, ticket out.

    Refuses by ValueError: invalid JSON, non-array top level, non-object
    entries, non-string role/text/tool. Nothing is ever evaluated.
    """
    try:
        data = json.loads(messages_json or "")
    except Exception as e:
        raise ValueError(f"messages_json is not valid JSON: {e}")
    if not isinstance(data, list):
        raise ValueError("messages_json must be a JSON array of message objects")
    msgs: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"messages_json[{i}] must be an object")
        for key in ("role", "text", "content", "tool"):
            if key in item and not isinstance(item[key], str):
                raise ValueError(f"messages_json[{i}].{key} must be a string")
        msgs.append(dict(item))
    return worker.submit(msgs)
