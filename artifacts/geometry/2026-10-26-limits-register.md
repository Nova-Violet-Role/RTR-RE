<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->
<!-- Copyright 2026 Saimonokuma. -->
# Limits register: real, stale, look-off, or unproven

Date: 2026-10-26. Method: source audit (AST + targeted reads), instruments
already run this session, and claim-by-claim comparison against current
code. "Look-off" means a limit produced by shallow inspection, stale text,
wrong layer attribution, or an instrument that was not measuring the named
thing. Nothing is deleted from this register when fixed; its verdict
changes with evidence.

Revised 2026-10-27 (TODO-1 closure): every row re-verified against current
code and the frozen bench artifacts (`eval/results/graded.json` dataset
`gold-v2-2026-10-26`, `eval/results/versus.json` intense). Fixed rows name
the fixing code and test; remaining real limits each carry an owner todo
or an explicit boundary statement owed to TODO-11 documentation.

## A. Look-offs and stale statements (not real limits)

| ID | Stated limit | Verdict | Evidence / disposition |
|---|---|---|---|
| L-01 | Host preserve 2k-15k conflicts with TARGET 100k | Look-off: different layers | Host compaction is emergency-only (`compaction.ts` preserve budget); Keeper window contract is separate. Docs must name layers, not compare unlike budgets. |
| L-02 | ACP percent limits conflict with 200k input cap | Fixed look-off | Percent resolves against 1M window; absolute tokens now used in all three configs. |
| L-03 | Dummy LLM turn untested / no auth | Stale | dummy2 turns 1-12 passed on muse-code with isolated state. |
| L-04 | Engine env override matrix untested | Stale | ENV-MATRIX PASS 14/14 including subprocess state isolation. |
| L-05 | Quality gate firing untested | Misframed under Keeper-only | With `permission: deny`, ACP registers no compress tool and quality gate has no call to judge. Dead config removed in this audit round; gate belongs to compressor history, not Keeper. |
| L-06 | Precedent versus lead (0.738/0.854/0.785) | Look-off: contaminated measurement | Live roots/lexikon leaked into precedent runs (36 staged -> 66 indexed). Superseded twice: isolated intense table, then the 2026-10-27 post-fortification frozen `versus.json` (manifest sha256 re-verified byte-identical to sources). |
| L-07 | RTR latency "~30-55ms" as one number | Closed: now measured per system/corpus | Final binary p50 in `versus.json`: dense arms 3.5-9.4 ms, hybrid 4.8-12.2 ms, rtr-full 25.5-30.3 ms; graded rows carry `p50_ms` per system. Any single-number latency in copy is a look-off; cite the JSON. |
| L-10 | "RTR-RE:Rolling" name fragment in `symbiose_config` docstring and `TestRollingConfig` | Fixed look-off (naming) | Renamed 2026-10-27 to RE:Symbiose / `TestSymbioseConfig`; public name carries no Rolling (vendored upstream names stay only in `VENDORED.md`). |
| L-08 | Tickets lost across MCP runs look like compression failure | API scope, not compression limit | Tickets are process-scoped by design; content-hash resubmit is cheap. Persistence is a possible feature, not correctness of eviction. |
| L-09 | Rollout summarizer can exceed summary cap | Fixed | `cap_summary` and planner summary budget enforce char caps; summary emission itself is outside RE:Symbiose worker. |

## B. Real limits (measured, must be engineered or stated as boundaries)

| ID | Limit | Cause in code | Severity / next action |
|---|---|---|---|
| R-01 | Single-writer engine; second process becomes read-only and concurrent native Chroma access can crash a gate | `_acquire_writer_lock`, shared persistent HNSW; live-DB gate crash `0xC0000374` | Real boundary. One server per DB; benches/tools isolate `OPENCODE_MEMORY_DB_DIR`. Owner: TODO-11 boundary statement in docs. |
| R-02 | Search latency scales with corpus and subqueries | `_fused_multi` queries all candidates per model/subquery, BM25 tokenizes every candidate per query; expansion and PRF can add passes | Real, measured: rtr-full p50 25.5-30.3 ms vs dense 3.5-9.4 ms on 30-48-file corpora (final binary). Candidate/BM25 caching is future work (TODO-12 scope). |
| R-03 | Planner TARGET is not a hard cap | protected + tool-pair + last-user additions after the tail walk (`context_budget.py:165-186`); oversized newest message kept | Real contract limit, now stated in the `plan_compression` docstring as a soft target; overflow is exactly the protected/tool-pair additions and is reported via `keep_tokens`. Lean counterpart: `protected_message_can_exceed_any_smaller_target`. Owner: TODO-11 docs. |
| R-04 | Tool-pair repair was one predecessor step over a snapshot | `plan_compression` iterated a sorted snapshot | **Fixed**: fixpoint repair (`context_budget.py:165-177`), red-first chain regression; Lean `fixpoint_repairs_chain_to_call` / `one_pass_leaves_chain_gap` pin the model. |
| R-05 | Content hash ignored tokens/tool before the audit | `content_hash` used role+text only | **Fixed**: canonical whole-message JSON hash (`symbiose_worker.py:44-57`); Lean `legacy_hash_ignores_tokens` vs `canonical_key_distinguishes_tokens`; matrix tests green. |
| R-06 | Worker ticket/cache memory was unbounded in a long MCP process | `_tickets` and `_cache` never evicted | **Fixed 2026-10-27**: `max_retained_tickets=512` bound with oldest-completed eviction incl. cache entries, realizing the Lean `retainBounded` contract; `test_completed_ticket_store_is_bounded`. |
| R-07 | Worker close left queued tickets pending forever | `close()` set a flag and joined 2s; queued tickets never transitioned (red-proven: poll returned `pending` after close) | **Fixed 2026-10-27**: queued tickets are failed by name ("worker closed before processing"), submit-after-close returns a failed ticket; `test_close_fails_queued_tickets_instead_of_leaving_pending`, `test_submit_after_close_reports_failed_not_pending`. |
| R-08 | File-level relevance only in benches | both benches map chunk hits to source filename; no chunk IDs/offsets in rows | Real evaluation limit. Owner: TODO-5 telemetry (chunk provenance belongs in the graded artifact chain). |
| R-09 | Graded qrels v1 sparse (155 judgments) | curated lists only | **Fixed**: gold v2 pooled adjudication, 773 judgments, histogram 0:633 1:51 2:48 3:41, validation errors empty (TODO-4). |
| R-10 | No cross-encoder rerank; paraphrase depth limited | bi-encoder + BM25 + lexikon only | Real capability boundary; future work, stated as such (TODO-11). |
| R-11 | Sync index/search in engine process | index_all and search perform ONNX/Chroma work on caller path | Real product boundary today; worker async covers eviction, not vector indexing. Owner: TODO-12 overhaul decision. |
| R-12 | Arctic collapse on dtd-commands | final binary R@1 0.1596 (bge arms ~0.50); final graded nDCG@10 0.5817 vs dense-base 0.8031 | Model/corpus mismatch is real; vote truncation + standout weights mitigate fusion drag but do not make Arctic good there. Boundary: Arctic is a diversity arm, never the sole model for term-dense corpora. |
| R-13 | Upstream ACP suite failures | first full run 1387/1390; earlier sample timeouts did not recur | **Fixed at the test layer**: the 3 stable failures were POSIX test assumptions on Windows (separators, `/tmp`, mode bits); tests made platform-correct (VENDORED.md), full suite now 1390/1390 exit 0 (`2026-10-27-acp-bun-suite.md`). The vendored tree still leaves the published architecture entirely (TODO-16). |
| R-14 | `bench_graded` hardcoded the dataset label `gold-v1` regardless of the queries file | `results["dataset"]` literal in `bench_graded.py` | **Fixed 2026-10-27**: label read from the queries-file `version`; final frozen run reports `gold-v2-2026-10-26`. Provenance defects are release blockers by this row. |
| R-15 | Cross-run bench noise: unchanged arms move between runs | embedding/index nondeterminism (rag-dense-base nt-studies 0.7656 -> 0.7187 across post-fix runs with untouched dense code) | Real methodology limit: publish within-run comparisons only; absolute cross-run deltas under ~0.05/corpus are not evidence. Owner: TODO-11/TAXONOMY note. |

## C. Unproven statements (cannot publish as limits or wins yet)

| ID | Statement | Missing evidence |
|---|---|---|
| U-01 | Live model "won't notice" compression after restart | Host-applied eviction cycle in a real long session. Dummy proves tools/retrieval, not host window mutation. Owner: TODO-9 fresh dummy + TODO-14 live survey. |
| U-02 | RAG is completely eradicated | **Refuted as a universal** (2026-10-27): same-size dense RAG leads the frozen gold-v2 graded combined (0.8057 vs 0.7823). Publish only the scoped verdict in `2026-10-27-graded-fortification.md`. |
| U-03 | Compression completes in milliseconds at production scale | Calibration excludes summarizer/LLM and ONNX indexing; synthetic pipeline upper bound only. Publish with that label or not at all. |
| U-04 | Dual ensemble is always superior | **Refuted as an "always"**: ablations are corpus-shaped (Arctic drag on dtd-commands; fusion wins dita/NT binary lanes). Claim measured per-corpus outcomes only. |
| U-05 | Quality gate protects summaries | No live compress calls exist under Keeper-only; gate is dormant/dead in current architecture. Do not publish as a feature. |

## D. Code inflation findings (AST baseline)

2026-10-26 baseline: 22 files · 8,892 lines · 298 functions · 21 over 80
lines · 116 broad handlers · 0 exact duplicate bodies.
2026-10-27 re-derivation (TODO-2, same instrument): 22 files · 9,199
lines · 316 functions · 22 over 80 · 116 broad · 0 duplicates. Growth is
the graded/lane/test surface added since (bench_graded, build_gold v2,
hybrid_lane_weights, worker retention), not accretion in old code.

Dispositions (TODO-2 closure):

- Ruff judgment items fixed: unused `entry`/`directives_dir`, ambiguous
  `l` in `memory_engine.py` — Ruff now clean on the engine.
- Verbatim extractions landed: `index_all` 220 -> 182 lines
  (`_purge_deleted_paths`, `_empty_index_stats` refusal shape);
  `hybrid_lane_weights` out of `_fused_multi`; worker `_evict_locked` /
  `_store_failed_locked` out of `_run`.
- Remaining >80-line functions kept with reasons: session/concept
  orchestrators in `memory_engine.py` (`reflect_session`,
  `materialize_concepts`, `update_concept_graph`, `init_project`,
  `restore_session_state`, `consolidate_wiki`, `write_wiki`) are single
  lifecycle transactions over registry+filesystem state — splitting them
  is TODO-12 overhaul scope, not audit scope; bench/CLI `main` and
  `render` functions are entrypoint orchestration; `search`/`_fused_multi`
  stay whole while bench numbers are frozen against them.
- Broad handlers (116: engine 73, MCP 20, CLI 12, rest <=3/file) are
  failure-isolation boundaries around Chroma/fastembed/filesystem IO —
  per-file/per-chunk work must not abort whole index/search passes.
  Justified as a class; the standing rule is no new broad handler without
  an IO boundary reason. Narrowing them one by one is TODO-12 scope.
- `memory_engine.py` responsibility concentration (2,948 lines) remains
  the named inflation source; it is concentration, not duplication
  (0 duplicate bodies both audits). Owner: TODO-12.
- Intent data still lives inside `build_gold.py`; extracting intents to
  JSON remains a recorded non-goal for this cycle (builder + validator
  read them in one place; dataset is frozen).
- Generated evidence stays uncommitted-by-default or under
  `eval/results/`; the pool worksheet (643,512 B) is generated, never
  source.

## E. Publication rule

No release while an A-item remains in public copy, a B-item lacks an owner
or explicit boundary statement, or a U-item is phrased as a measured win.
