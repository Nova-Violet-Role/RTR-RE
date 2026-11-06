<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->
<!-- Copyright 2026 Saimonokuma. -->
# A-Z evaluation: RTR-RE:Rolling fusion (2026-10-26)

Every verdict measured unless marked reasoned/untested. Instruments named per line.

- A ACP config (25 compress keys + qualityGate): PASS. check_acp ACP-OK bytes=1788 keys=25; values equal plan (200000/100000/40). Vendored config suites: 91 pass.
- B ACP upstream defects: FAIL (upstream, recorded). preserve-recent 2/18 reproducible timeouts 8.9s/12.5s vs 5s limit (bun test, twice).
- C Collision safety: PASS. Planner/worker no-mutation tests; one mutator per transport by design; dummy plugins list shows single ACP.
- D DTD typing: PASS. span_dtype + engine dtype_hist/notations; NDATA masked in payload test.
- E Encoding: PASS. CR=false on all written files (nu str contains); compressor converted CRLF->LF.
- F Full RTR suite: PASS. test_memory 14/14 in 4.634s (dual ONNX real). First 900s timeout root-caused: extra-roots isolation leak (236 files), fixed in test harness.
- G Geometry chain: PASS. survey/plan/renovation/production + renovation-2 on disk, date-ordered, bytes counted (cells 415, svg 1041, png 7234).
- H Host bridge: PASS (read). compaction.ts RTR commit/restore at :389-396; memory.ts caps 4000/64000. Live compaction cycle UNTESTED (needs restart + long session).
- I Isolation (dummy): PASS with peculiarities. XDG_CONFIG_HOME isolates config; XDG_DATA_HOME isolates data/db/log; OPENCODE_MEMORY_DB_DIR isolates vector DB (dummy .writer.lock). Peculiar: launch-dir project .opencode always merges (moviola appeared); ACP daily log is homedir-based, not XDG-isolated.
- J JSONC validity: PASS via ACP jsonc-parser semantics (comments legal); plain-JSON LSP flags comments — instrument disagreement recorded, ACP parser is authority.
- K Knobs (configurability): PASS for RTR-RE 5 env knobs (defaults/override/refusals, 3 tests). Rolling caps env PASS (cap check). Engine envs (models/profile/RRF/suffixes) exercised at defaults only — override matrix UNTESTED.
- L Lanes (read+written): PASS. Lane assertions + SPAN-INGEST-OK: sink file indexed (scanned 1 new 1), search hit contains marker, real ONNX.
- M MCP surface: PASS. Dummy mcp list: memory connected (repo server via uv). memory_context_plan present in repo code (py_compile + tool registration read); live-call through dummy LLM UNTESTED (no provider auth in dummy).
- N No-pause: PASS. submit <0.25s vs 0.6s sink; suite 8 tests 0.843s.
- O ONNX dual ensemble: PASS. Both models load threads=4 (balanced) in every heavy run; search/explain green.
- P Peculiar details: (1) ACP % limits resolve against 1M window — absolute tokens required at 200k input cap. (2) Host preserve 2k-15k vs TARGET 100k: host compaction (emergency) keeps far less than Rolling target — by design, different layers. (3) Rolling summarizer max_tokens 16000 can still emit >20000 chars in theory; cap_summary now bounds it. (4) Writer-lock fd leak fixed: ResourceWarnings 14+ -> 0.
- Q Quality gate: PASS config (200/5.0/0.05/0.2 = upstream defaults in config.ts:430-433). Live gate firing UNTESTED until restart.
- R Release recognizer: PASS. Amplify named minor 0.3.1; Overhaul (elevation kept) names mid 0.4.0; taken no both. Manifest still 0.3.0 — operator's bump (LAW.AMP.8/14: manifest must equal recognizer when taken).
- S Summary bound: PASS. cap_summary 108889 -> 19997 chars; enforce_summary_budget tests green.
- T Trigger/Target: PASS. 200000/100000 in code, ACP config, plan, tests — four witnesses agree.
- U Upstream vendored state: PASS with record. VENDORED.md pins 6fc6407 / 98a16d5b; bun install added node_modules + dist (518.26 KB) in vendored ACP — build artifacts, noted.
- V Verbatim substance: PASS. UNIQUE marker survives evict payload byte-exact (test) and retrieval (span ingest).
- W Worker failure modes: PASS. Cooldown, cache, overflow statuses unit-proven; sink exception never crashes submitter.
- X eXit codes: PASS. All runs foreground via uv/bun with output read; timeouts treated as findings (900s suite, 120s serve-expected).
- Y Yield (next verbs): Enhance 6 heighten = live percentile measure after restart; Overhaul 14 = async index pipeline replacing synchronous index_all (exposed, not kept).
- Z Zero-regression gate: PARTIAL. rtr_eval golden bench NOT run this session (needs full corpus index time); unit suites are the gate evidence here. Marked untested, not passed.

Open risks: live ACP behavior after restart (reasoned), rtr_eval (untested), engine env override matrix (untested), ACP preserve-recent upstream timeouts (measured fail).

Addendum (same day, dummy long session): opencode-dev + muse-code (muse-spark-1.3-contributor), isolated dummy2, 6 turns --continue. T1 memory_context_plan (new tool, decision compress) + stats TURN1-OK; T2 rolling submit ticket 1 hash 6dff81565f521ef3 -> ready evicted 0 TURN2-OK; T3 acp absent (bundle externals @anthropic-ai/tokenizer + tiktoken missing beside bare file plugin — root-caused by direct bun import, fixed by copying deps); T4 acp_status live 49.1K TURN4-OK; T5 two whole-file reads -> 96K TURN5-OK; T6 config.ts read + memory_session_start restore + 115K TURN6-OK. One provider stream error self-recovered on retry. Peculiar: memory_stats registry reads live 236 files while vector DB isolated (registry path is MEMORY_DIR-bound, not DB-bound) — read-only leak, recorded. Line M dummy LLM turn: PASS (supersedes untested).
Next band: 1 planimetry — fresh /codebase-surveyor-dtd after restart.

Addendum 2 (three offices): ACP rewired Keeper-only (permission deny in live/project/dummy acp.jsonc, ACP-OK 1835 B, inject.ts:98,1065 deny guards). Dummy T7: tool list holds memory_symbiose_submit/poll and zero ACP tools; ACP-KEEPER-ONLY-CONFIRMED, TURN7-OK. Peculiar: symbiose tickets are MCP-process-scoped (cross-run poll = unknown; resubmit hash-cheap). Offices: Keeper selects, Compressor compresses, RTR manages. Product renamed RTR-RE:Symbiose (short RE:Symbiose); 55 stdlib tests green after rename.

Addendum 3 (gate + versus): rtr_eval GATE PASS 25/25 exit 0 isolated; against live DB it crashes 0xC0000374 (concurrent Chroma open) — gate must run isolated, extra_roots pollution cleaned 38->13 (backup kept). Versus tool v2 (full isolation, sha256 manifest, same-size bge-base RAG controls, 164 queries real corpora): combined rag-hybrid 0.7378/0.8537/0.7866 vs rtr-full 0.7256/0.8232/0.7673 — RAG NOT eradicated on overall today. Per-taxon RTR wins T2 rare-term (0.875), T6 ident (0.958), T5 R@3 (0.667); loses T1/T3/T4. Suspect: global lexikon not yet isolated in tool (expansion noise) + fusion dilution on title queries. Fix queued before any eradication claim ships.
