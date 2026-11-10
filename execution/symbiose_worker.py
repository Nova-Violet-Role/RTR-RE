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
import os
import queue
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List
from xml.sax.saxutils import quoteattr

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
    """Write evicted spans as DTD-shaped memory records (TODO-70).

    Files land under <project>/.opencode/memory/ — the dedicated keeper
    memory root (gitignored via .opencode/). Each file is a structural
    DTD record: the span schema is declared (ELEMENT span + ATTLIST with
    architectural role attributes, mirroring the arch-letter architectural-
    form pattern), and the verbatim span content follows the declarations.
    The RTR DTD chunker builds the inventory header from the declarations,
    so every span is searchable by structure (role/lane/dtype/source), not
    just text — the keeper memory is a first-class DTD corpus member.

    Backward compatibility: existing .md spans under directives/sessions/
    are still read by discovery; new spans are written DTD-shaped here.
    """

    _SCHEMA = (
        "<!-- RTR-RE:Symbiose keeper memory span v2.1 (DTD-shaped) -->\n"
        '<!ENTITY % rtrre.span.module "INCLUDE">\n'
        "<![%rtrre.span.module;[\n"
        "<!ELEMENT span EMPTY>\n"
        "<!ATTLIST span\n"
        "    id ID #REQUIRED\n"
        "    role (user|assistant|tool|system|unknown) #REQUIRED\n"
        "    lane (read|written|think|plan|unknown) #IMPLIED\n"
        "    dtype (PCDATA|CDATA|NDATA) #IMPLIED\n"
        "    ts CDATA #IMPLIED\n"
        "    source CDATA #IMPLIED\n"
        "    session CDATA #IMPLIED>\n"
        "]]>\n"
        "<!-- verbatim span content follows -->\n"
    )

    def __init__(self, directory: Path):
        self.directory = Path(directory)

    _SUMMARY_SCHEMA = (
        "<!-- RTR-RE:Symbiose keeper paraphrase v2 (DTD-shaped) -->\n"
        '<!ENTITY % rtrre.summary.module "INCLUDE">\n'
        "<![%rtrre.summary.module;[\n"
        "<!ELEMENT paraphrase EMPTY>\n"
        "<!ATTLIST paraphrase\n"
        "    spanref IDREF #REQUIRED\n"
        "    text CDATA #REQUIRED\n"
        "    ts CDATA #IMPLIED>\n"
        "]]>\n"
        "<!-- common-line anchors follow -->\n"
    )

    _ANCHOR_MAX = 160

    @staticmethod
    def _anchor_line(text: str) -> str:
        """The common line: first meaningful line, truncated (TODO-70).

        This is the honest, deterministic anchor for a bounded span —
        the one-line paraphrase that stays visible/retrievable while the
        verbatim span lives in memory. Real paraphrase generation is a
        future summarizer hook; the anchor is the guaranteed fallback.
        """
        for line in str(text or "").splitlines():
            stripped = line.strip()
            if stripped:
                if len(stripped) > SessionSpanSink._ANCHOR_MAX:
                    return stripped[: SessionSpanSink._ANCHOR_MAX] + "…"
                return stripped
        return ""

    def __call__(self, spans: List[Dict[str, Any]], digest: str = "") -> str:
        self.directory.mkdir(parents=True, exist_ok=True)
        name = f"rtrre-{digest or 'spans'}.dtd"
        path = self.directory / name
        lines = [self._SCHEMA]
        summaries = [self._SUMMARY_SCHEMA]
        for s in spans:
            role = quoteattr(str(s.get("role", "unknown")))
            lane = quoteattr(str(s.get("lane", "read")))
            dtype = quoteattr(str(s.get("dtype", "PCDATA")))
            ts = quoteattr(str(s.get("ts", "") or ""))
            source = quoteattr(str(s.get("source", "") or ""))
            session = quoteattr(str(s.get("session", "") or ""))
            idx = s.get("index", "?")
            lines.append(
                f"<span id={quoteattr(f'span-{idx}')} role={role} lane={lane} "
                f"dtype={dtype} ts={ts} source={source} "
                f"session={session}>"
            )
            text = str(s.get("text") or "")
            if dtype == "NDATA":
                text = "[NDATA]"
            lines.append(text)
            lines.append("</span>")
            lines.append("")
            anchor = self._anchor_line(text)
            if anchor:
                summaries.append(
                    f"<paraphrase spanref={quoteattr(f'span-{idx}')} "
                    f"text={quoteattr(anchor)} ts={ts}/>"
                )
        # Bytes, not text mode: Windows text translation would rewrite LF
        # as CRLF. Session spans are UTF-8 with LF endings, byte-exact.
        path.write_bytes(("\n".join(lines)).encode("utf-8"))
        if len(summaries) > 1:
            summary_path = self.directory / f"rtrre-summary-{digest or 'spans'}.dtd"
            summary_path.write_bytes(("\n".join(summaries)).encode("utf-8"))
        return str(path)


_OVERRIDE_KEYS = frozenset({"target_tokens"})


def _validate_plan_overrides(
    plan_overrides: Dict[str, Any] | None, config: Dict[str, Any] | None
) -> Dict[str, Any]:
    """Gate per-ticket plan overrides (RRD-81): allowlist plus range, refused by name."""
    if plan_overrides is None:
        return {}
    if not isinstance(plan_overrides, dict):
        raise ValueError(
            "refused: plan_overrides must be an object, "
            f"got {type(plan_overrides).__name__}"
        )
    unknown = sorted(set(plan_overrides) - _OVERRIDE_KEYS)
    if unknown:
        raise ValueError(f"refused: unknown plan_overrides keys: {', '.join(unknown)}")
    clean = dict(plan_overrides)
    if "target_tokens" in clean:
        target = clean["target_tokens"]
        trigger = int(
            (config or {}).get("trigger_tokens", context_budget.TRIGGER_TOKENS)
        )
        if isinstance(target, bool) or not isinstance(target, int):
            raise ValueError(
                f"refused: target_tokens must be an integer, got {target!r}"
            )
        if target <= 0:
            raise ValueError(f"refused: target_tokens must be positive, got {target}")
        if target >= trigger:
            raise ValueError(
                f"refused: target_tokens {target} must be below trigger_tokens {trigger}"
            )
    return clean


class SymbioseWorker:
    def __init__(
        self,
        sink: Callable[..., Any],
        cooldown_seconds: float = 300,
        max_queue: int = 8,
        max_retained_tickets: int = 512,
        config: Dict[str, Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
        cumulative_path: Path | None = None,
    ):
        if int(max_retained_tickets) < 1:
            raise ValueError(
                f"max_retained_tickets must be positive, got {max_retained_tickets}"
            )
        if int(max_queue) < 1:
            raise ValueError(f"max_queue must be positive, got {max_queue}")
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
        # Cumulative message counter: total messages ever processed, including
        # evicted ones (operator design, TODO-45). Persisted at cumulative_path
        # so it grows across sessions and can never stay pinned to the live
        # window size. None disables persistence (pure in-memory counter).
        self._cumulative_path = Path(cumulative_path) if cumulative_path else None
        self._cumulative_messages = 0
        if self._cumulative_path and self._cumulative_path.exists():
            # Fail-closed on corrupt state: a corrupted counter must never
            # silently reset to zero, because zero re-enables full protection
            # and hides the corruption from every later audit (LAW.AMP.1:
            # silence must not read as health). The worker refuses to start
            # until the state is repaired or explicitly removed.
            try:
                state = json.loads(self._cumulative_path.read_text(encoding="utf-8"))
                self._cumulative_messages = int(state.get("cumulative_messages", 0))
                if self._cumulative_messages < 0:
                    raise ValueError("cumulative_messages must be >= 0")
            except Exception as exc:
                raise ValueError(
                    "REFUSED: cumulative counter state is corrupt at "
                    f"{self._cumulative_path}: {exc}. Repair or remove the file "
                    "to start with a fresh counter."
                ) from exc

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

    def submit(
        self,
        messages: List[Dict[str, Any]],
        plan_overrides: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        clean_overrides = _validate_plan_overrides(plan_overrides, self._config)
        submitted_at = self._clock()
        digest = content_hash(messages)
        if clean_overrides:
            over_hash = content_hash([clean_overrides])[:8]
            digest = f"{digest}+{over_hash}"
        hash_ms = max(0.0, (self._clock() - submitted_at) * 1000.0)
        input_chars = sum(len(context_budget._text_of(m)) for m in messages)
        with self._lock:
            submit_ms = max(0.0, (self._clock() - submitted_at) * 1000.0)
            if self._closed:
                tid = self._next_id
                self._next_id += 1
                self._tickets[tid] = {
                    "id": tid,
                    "status": "pending",
                    "plan_overrides": clean_overrides,
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
            self._cumulative_messages += len(messages)
            if self._cumulative_path:
                try:
                    self._cumulative_path.parent.mkdir(parents=True, exist_ok=True)
                    # Atomic write: write a temp sibling then rename, so a
                    # crash mid-write never leaves a truncated state file that
                    # the fail-closed loader would refuse.
                    tmp = self._cumulative_path.with_suffix(
                        self._cumulative_path.suffix + ".tmp"
                    )
                    tmp.write_text(
                        json.dumps({"cumulative_messages": self._cumulative_messages})
                        + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )
                    os.replace(tmp, self._cumulative_path)
                except OSError:
                    # A persistence failure must never block the submission; the
                    # in-memory counter still advances for this session.
                    pass
            ticket: Dict[str, Any] = {
                "id": tid,
                "hash": digest,
                "status": "pending",
                "input_messages": len(messages),
                "input_chars": input_chars,
                "hash_ms": round(hash_ms, 3),
                "plan_overrides": clean_overrides,
            }
            try:
                self._q.put_nowait(
                    (tid, digest, list(messages), submitted_at, clean_overrides)
                )
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
                queued = self._q.get(timeout=0.05)
                tid, digest, messages, submitted_at, ticket_overrides = queued
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
                plan_config = dict(self._config or {})
                plan_config["cumulative_messages"] = self._cumulative_messages
                plan_config.setdefault(
                    "live_tokens",
                    _read_keeper_live_tokens(self._cumulative_path),
                )
                plan_config.update(ticket_overrides)
                plan = context_budget.plan_compression(messages, config=plan_config)
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
                        "input_chars": sum(
                            len(context_budget._text_of(m)) for m in messages
                        ),
                        "kept_chars": sum(
                            len(context_budget._text_of(messages[i]))
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


def _parse_messages_json(messages_json: str) -> List[Dict[str, Any]]:
    """Parse and validate a JSON message array (shared submit/compress gate).

    Refuses by ValueError: invalid JSON, non-array top level, non-object
    entries, non-string role/text/tool. Nothing is ever evaluated.
    Messages may carry OpenCode parts[] (reasoning/text/tool); part
    texts count toward the budget and sink verbatim.
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
    return msgs


def submit_json(worker: "SymbioseWorker", messages_json: str) -> Dict[str, Any]:
    """Tool-core for memory_symbiose_submit: JSON data in, ticket out.

    Returns a ticket immediately; compression never pauses the live turn.
    """
    return worker.submit(_parse_messages_json(messages_json))


def compress_json(
    worker: "SymbioseWorker", messages_json: str, target_tokens: int
) -> Dict[str, Any]:
    """Tool-core for memory_symbiose_compress: JSON plus a direct target in, ticket out.

    The target is the Compressor's verbatim tail (RRD-75/79); the trigger
    stays preset/env. Thinking and tool parts ride the messages untouched
    and count toward the budget. The submit gate refuses a bad target by
    name; compression never pauses the live turn.
    """
    msgs = _parse_messages_json(messages_json)
    return worker.submit(msgs, {"target_tokens": target_tokens})


def open_project_worker(
    project_dir: str | Path, config: Dict[str, Any] | None = None
) -> "SymbioseWorker":
    """Construct (never cache) a project worker sinking to its keeper root.

    The MCP server caches per project in _symbiose_for; one-shot callers
    (rtr-cli) construct, use, and close. Stdlib-only: the caller resolves
    the directory and supplies config (default: the live symbiose config).
    """
    root = Path(project_dir)
    cfg = dict(config) if config is not None else context_budget.symbiose_config()
    # Deployment calibration must govern the actual compressor, not
    # only the plan report. Measured in dummy survey turn 9: a 55k
    # calibrated workload evicted nothing while the worker silently
    # retained the 200k library default.
    # The cumulative counter file is the shared recency signal: the
    # worker owns it (atomic temp+rename) and the JS keeper reads it,
    # so both sides of the recency-aware protection (TODO-45) see the
    # same count. Without it the protection would stay all-protect.
    return SymbioseWorker(
        SessionSpanSink(root / ".opencode" / "memory"),
        config=cfg,
        cumulative_path=root / ".opencode" / "rtr-re-cumulative.json",
    )


def _quarantine_sidecar(path: Path, reason: str) -> Dict[str, Any]:
    """Rename an unusable sidecar out of the drain queue, never deleting it (RRD-76).

    Callers pass only keeper sidecars (`rtrre-*.submit.json`), so the
    `.submit.json` suffix is always present.
    """
    broken = path.with_name(path.name[: -len(".submit.json")] + ".submit.broken.json")
    try:
        os.replace(path, broken)
        moved: str | None = broken.name
    except OSError:
        moved = None
    return {"file": path.name, "reason": reason, "quarantined": moved}


def _try_relay_sidecar(
    memory_dir: Path, path: Path, sidecar: Dict[str, Any]
) -> str | None:
    """Relay-ack a sidecar whose spans the keeper already sunk (RRD-107/114).

    Returns the spans filename when the sibling spans file verifies
    (exists, carries span tags, tag count equals sidecar message count)
    and the sidecar was unlinked; returns None when verification fails
    (caller falls through to the ticket path). Raises OSError only when
    verification passed but the unlink itself failed (caller reports
    left, mirroring the ticket path).
    """
    stem = path.name[: -len(".submit.json")]
    spans_path = memory_dir / f"{stem}.dtd"
    try:
        content = spans_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if "<span id=" not in content:
        return None
    # Strict opens only (E-T38C phase 1, measured live 2026-11-10):
    # verbatim content quoting span tags overcounts the loose substring
    # (1cb8575a: 202 loose vs 195 real) and defeats relay into a
    # duplicate ticket. A mismatch still fails safe into tickets.
    opens = len(re.findall(r'<span id="span-\d+"', content))
    if opens != len(sidecar["messages"]):
        return None
    path.unlink()
    return spans_path.name


KEEPER_STATUS_NAME = "rtr-re-keeper-status.json"  # mirrors keeper.js


def _read_keeper_live_tokens(cumulative_path: Path | None) -> int:
    """Keeper's live kept-count for window-aware tickets (RRD-108).

    Reads keepTokens from the keeper status file beside the cumulative
    counter. Anything unreadable (no path, missing/corrupt file, absent
    or invalid count) fails open to 0, reproducing today's ticket-only
    scope — relief must never depend on aux-file integrity.
    """
    if cumulative_path is None:
        return 0
    try:
        status = json.loads(
            (Path(cumulative_path).parent / KEEPER_STATUS_NAME).read_text(
                encoding="utf-8"
            )
        )
        live = int(status.get("keepTokens", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        return 0
    return max(0, live)


def drain_submit_sidecars(
    worker: "SymbioseWorker",
    memory_dir: str | Path,
    limit: int = 5,
    wait_timeout: float = 10,
) -> Dict[str, Any]:
    """Consume keeper submit sidecars through the Compressor (TODO-38, RRD-76/78).

    The Keeper (JS, in-hook) fires instantly and leaves one
    `rtrre-<digest>.submit.json` per firing beside its verbatim spans;
    this intake — the Compressor's front door, never the Keeper's —
    submits them oldest-first, waits each ticket ready, and deletes
    consumed sidecars. The Compressor plans and sinks; it never
    touches the live window, and the Keeper never plans targets.

    Bounds: at most `limit` sidecars per sweep, each waited at most
    `wait_timeout` seconds. A transient worker block (cooldown,
    overflow, timeout, failed submit) stops the sweep — the worker is
    FIFO, so the rest would block identically — and every unprocessed
    file is reported under `left`, never silently dropped. Corrupt or
    refused sidecars are quarantined (`*.submit.broken.json`), never
    retried, never deleted. Files beyond `limit` are reported
    `over-limit`.
    """
    mem = Path(memory_dir)
    try:
        candidates = sorted(
            (p for p in mem.glob("rtrre-*.submit.json") if p.is_file()),
            key=lambda p: (p.stat().st_mtime_ns, p.name),
        )
    except OSError:
        candidates = []
    per_sweep = max(0, int(limit))
    drained: List[Dict[str, Any]] = []
    left: List[Dict[str, Any]] = []
    quarantined: List[Dict[str, Any]] = []
    stopped_reason: str | None = None
    for position, path in enumerate(candidates):
        if position >= per_sweep:
            left.append({"file": path.name, "reason": "over-limit"})
            continue
        if stopped_reason is not None:
            left.append({"file": path.name, "reason": stopped_reason})
            continue
        try:
            sidecar = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            quarantined.append(_quarantine_sidecar(path, f"unreadable sidecar: {exc}"))
            continue
        if not isinstance(sidecar, dict) or not isinstance(
            sidecar.get("messages"), list
        ):
            quarantined.append(
                _quarantine_sidecar(path, "sidecar messages is not an array")
            )
            continue
        if not sidecar["messages"]:
            quarantined.append(
                _quarantine_sidecar(path, "empty sidecar: no messages to sink")
            )
            continue
        # Relay-ack (RRD-107): verified spans on disk mean nothing is left
        # to do — ack and unlink WITHOUT a ticket or re-sink.
        try:
            relay_sink = _try_relay_sidecar(mem, path, sidecar)
        except OSError as exc:
            left.append(
                {"file": path.name, "reason": f"consumed but not deleted: {exc}"}
            )
            continue
        if relay_sink is not None:
            drained.append(
                {
                    "file": path.name,
                    "ticket": None,
                    "relayed": True,
                    "status": "ready",
                    "sink": relay_sink,
                    "reason": "already sunk",
                }
            )
            continue
        try:
            ticket = submit_json(worker, json.dumps(sidecar["messages"]))
        except ValueError as exc:
            quarantined.append(_quarantine_sidecar(path, f"refused: {exc}"))
            continue
        status = str(ticket.get("status", ""))
        if status in ("cooldown", "overflow"):
            stopped_reason = f"stopped after {status}"
            left.append(
                {"file": path.name, "reason": status, "ticket": ticket.get("id", 0)}
            )
            continue
        if status == "failed":
            stopped_reason = "stopped after failed submit"
            left.append(
                {
                    "file": path.name,
                    "reason": str(ticket.get("error", "failed")),
                    "ticket": ticket.get("id", 0),
                }
            )
            continue
        if status not in ("pending", "cached"):
            left.append(
                {
                    "file": path.name,
                    "reason": f"unexpected status {status}",
                    "ticket": ticket.get("id", 0),
                }
            )
            continue
        done = worker.wait(ticket["id"], timeout=wait_timeout)
        done_status = "" if done is None else str(done.get("status", ""))
        if done_status != "ready":
            if done_status == "failed":
                stopped_reason = "stopped after ticket failed"
                reason = f"failed: {done.get('error', 'failed') if done else 'failed'}"
            else:
                stopped_reason = "stopped after timeout"
                reason = "timeout"
            left.append(
                {"file": path.name, "reason": reason, "ticket": ticket.get("id", 0)}
            )
            continue
        try:
            path.unlink()
        except OSError as exc:
            left.append(
                {
                    "file": path.name,
                    "reason": f"consumed but not deleted: {exc}",
                    "ticket": ticket.get("id", 0),
                }
            )
            continue
        drained.append(
            {
                "file": path.name,
                "ticket": ticket["id"],
                "status": "ready",
                "sink": done.get("sink"),
            }
        )
    return {
        "drained": drained,
        "left": left,
        "quarantined": quarantined,
        "limit": per_sweep,
    }


def _capped_list(entries, label, cap=10):
    lines = []
    for entry in entries[:cap]:
        reason = entry.get("reason")
        suffix = f" ({reason})" if reason else ""
        lines.append(f"  {label}: {entry['file']}{suffix}")
    if len(entries) > cap:
        lines.append(f"  +{len(entries) - cap} more")
    return lines


def drain_panel_lines(report):
    """Human panel lines for a drain report (shared MCP/CLI renderer)."""
    lines = [
        (
            "Drain: "
            f"{len(report['drained'])} consumed, "
            f"{len(report['left'])} left, "
            f"{len(report['quarantined'])} quarantined"
        )
    ]
    lines.extend(_capped_list(report["drained"], "consumed"))
    lines.extend(_capped_list(report["left"], "left"))
    lines.extend(_capped_list(report["quarantined"], "quarantined"))
    if report["drained"]:
        lines.append("Run memory_index to make the new spans searchable.")
    return lines
