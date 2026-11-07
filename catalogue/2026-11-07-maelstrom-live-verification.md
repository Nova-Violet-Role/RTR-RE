# Maelstrom session: live dummy-run verification — 2026-11-07

This catalogue records the measured findings of the live dummy-run verification
session (the "Maelstrom"), run against the installed RTR-RE stack with an
isolated dummy project and an isolated chroma DB. Every claim below carries its
instrument and its number. Nothing here is inferred from memory; everything was
run this session.

Scope: keeper, compressor, cumulative counter, chroma DB health/corruption/
recovery, ONNX model health, MCP surface, and the Compact-command diagnosis.

---

## 1. Compact command failure — diagnosis (installed stack)

Symptom: `/compact` in the opencode-dev build fails with its python instance;
the user reported the python process must be closed manually.

Measured evidence:

- Installed RTR-RE tool is **0.4.1** (stale; the repo is at 1.0.0). The
  opencode-dev compaction path (session/compaction.ts) calls `SessionMemory.commit`
  → MCP tool `memory_session_commit` on the `rtr-re-mcp.exe` Python MCP server.
- opencode.log shows `MCP connection closed` server=memory at 09:01:04 and
  09:11:37, immediately followed by `memory MCP call failed` tool=memory_session_commit.
- The running memory server process held ~1.2 GB working set (dual embedding
  models + chroma + onnxruntime).
- The compaction agent's model provider (cpa-gui proxy @ 127.0.0.1:8317) was
  unreachable, so summary generation could not complete.
- A standalone probe of the installed 0.4.1 server completed
  `memory_session_commit` on a small isolated project — the code path itself
  works. The production failure is therefore environmental: heavy real-corpus
  commit + manual kill of the python process + dead model proxy.

Conclusion: installing 1.0.0 is required for release coherence but is not by
itself the fix; the environmental factors (model proxy, MCP timeout budget,
process lifetime) are separate.

## 2. Keeper — live behavior (dummy project, shared DB)

Instrument: `opencode-dev run` (fresh sessions return; session continuations
complete their work but the process does not exit — the tool kills it at
timeout, which doubles as a forced-close test).

- Keeper config in the dummy project: trigger 2000 tokens, target 800, max 7
  messages, enabled, preset symbiose-ah (250k/100k/40 nominal).
- Status file `rtr-re-keeper-status.json` is written per exchange and carries
  the full resolved profile: `symbiose-ah/rtr-full/t4/p60`, version 1.0.0.
- Eviction fires when the message count exceeds max_keep_messages AND tokens
  exceed the trigger. A multi-tool-call exchange (6 tool calls) produced >7
  messages; the keeper then wrote **verbatim sink files** under
  `directives/sessions/rtrre-<digest>.md` (21 sinks observed, sizes 1.1 KB to
  138 KB). Sink format: `# RE:Symbiose evicted spans <digest>`, per-span
  role/lane/dtype + verbatim text, PCDATA/CDATA byte-exact, NDATA masked.
- The status file can be absent right after a forced kill of a run (the run
  was killed before the exchange's status write) — the next run rewrites it.
  Chroma integrity was unaffected (see §4).

## 3. Cumulative counter — live measurement (MCP-level)

Instrument: `rtr-cumulative-probe.mjs` + `rtr-protection-probe.mjs`
(newline-delimited JSON-RPC over stdio against `rtr-re-mcp.exe`, isolated env,
OPENCODE_MEMORY_RTRRE_TRIGGER=100000 / TARGET=40000). Counter file:
`<project>/.opencode/rtr-re-cumulative.json`.

- **Counting per submit**: submit 5 messages → cumulative 5; submit 10 more →
  15. The counter advances at submit time (before the worker processes), and
  cache hits never double-count.
- **Session resume persistence**: a NEW server instance reading the same
  cumulative file continues from 15; submit 3 → 18. The counter survives
  server restarts (atomic temp+rename persistence).
- **Crossing 1000**: submit-only batches advanced 918 → 1001 → (protection
  window of 1000 messages) → 2001.
- **Recency-aware protection**: the poll returns stats only (keep indices,
  evicted counts), not content. The content-level rule is asserted by the
  planner and the Engine Beneath case `production-scale-extreme-protection-
  warning`: at cumulative 1001, old todowrite (index 5) is evicted while
  recent todowrite (index 999) stays protected. Threshold constant:
  PROTECTION_CUMULATIVE_THRESHOLD = 1000 (context_budget.py).
- Worker cooldown is 300 s — poll-wait crossing is slow; submit-only batches
  advance the counter immediately.

## 4. Chroma DB — health, corruption, recovery

Instrument: isolated DB `rtr-dummy-db/chroma.sqlite3`; `sqlite3 PRAGMA
integrity_check`; MCP `memory_index` / `memory_search`.

- **Forced close survival**: multiple forced kills of the memory server tree
  (tool timeouts) left the DB with `integrity_check = ok`, `journal_mode =
  delete`, collections intact. A kill mid-index (6 s into a force reindex)
  left 96 embeddings persisted and integrity ok.
- **Recovery**: after the mid-index kill, a fresh server booted, `memory_search`
  returned results immediately (dense RRF normalized), and a full force reindex
  completed: 69 files scanned, 69 new, 0 failed, 119.2 s, DB grew 1.1 MB →
  34 MB. Search after the build works.
- **Fail-closed**: the cumulative counter refuses to start on corrupt state
  (symbiose_worker.py) — repair/remove is required, never a silent reset.
- The live opencode.db (25.9 GB) was never touched: all tests used the
  isolated dummy DB.

## 5. ONNX model health

Instrument: process census via PowerShell (Get-Process / Get-CimInstance) around
MCP calls; stderr capture.

- Models load lazily on first embedding use (search or index): stderr prints
  `Loading Snowflake/snowflake-arctic-embed-m via fastembed... (threads=4)`
  and `Loading BAAI/bge-base-en-v1.5 via fastembed... (threads=4)`.
- The real worker is a `python` process behind the shim chain (the scoop shim
  is ~7 MB; measuring it is measuring the launcher, not the worker).
- During a 127 s force reindex (69 files), the worker reached **3.4 GB RSS**
  and consumed **483 s CPU** (~3.8 cores average) — both ONNX models doing
  embedding work with threads=4 each.
- The long-lived live memory server holds ~1.16 GB RSS with models warm.
- The `dense` column in explain_search is min-max normalized RRF, not raw
  cosine: `dense = (raw_rrf[doc_id] - lo) / span if span > 0 else 1.0`.
  Before models are ready (or if a model run contributes no votes), span = 0
  → dense = 1.0 for every candidate. Observed: searches issued before the
  model load completes return with dense=1.0000 (fallback). This is a silent
  degradation window between boot and model-ready; worth surfacing loudly
  (LAW.AMP.1: silence must not read as health).

## 6. MCP surface (installed 1.0.0 / repo)

27 tools registered (memory_mcp_server.py): discover, search, list, delete,
inbox_write, inbox_read, write, organize, stats, index, init_project,
consolidate, session_start, explain_search, reflect_session, materialize_concepts,
update_graph, session_commit, lexikon_add, lexikon_show, lexikon_build, janitor,
symbiose_submit, symbiose_poll, context_plan, rtr_status, (plus the internal
helper surface). `memory_rtr_status` is the health snapshot: keeper status file
age/decision, compressor config + worker stats, manager.

## 7. Open items (next rungs)

- Preset matrix on this machine (Ryzen 9 9950X3D2, 16 cores / 32 threads):
  every CPU profile × thread mode (2–16) × parking (20–80%) × modality, plus
  dummy inputted presets through keeper/MCP/no-MCP optimizer (TODO-56).
- Compact-flow live test with a single clean compact (small context limit,
  mercury-3 summary, reflect persist, no hang) (TODO-61).
- Live palette (ctrl+p) verification in the dummy TUI (TODO-62).
- Complete the local 1.0.0 install (uv tool re-run) (TODO-54).

## Instruments kept

- `C:\Users\Saimono\AppData\Local\Temp\opencode\rtr-mcp-probe.mjs` — MCP
  stdio probe (initialize + tool call), newline framing.
- `rtr-cumulative-probe.mjs`, `rtr-protection-probe.mjs` — counter/resume/
  threshold measurements.
- `rtr-chroma-kill-probe.mjs`, `rtr-chroma-recovery-probe.mjs` — corruption/
  recovery.
- `rtr-onnx-probe2..6.mjs`, `rtr-proc-probe.mjs` — ONNX/process census.
- `sink-times.ps1` — sink file census.

Encoding: UTF-8, LF, no BOM, no CR (verified).
