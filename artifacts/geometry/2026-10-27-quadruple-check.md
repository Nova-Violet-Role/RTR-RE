<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# Quadruple check: whole RTR-RE:Symbiose (2026-10-27, pre-restart)

Standing lessons (operator-pinned, do not soften):
1. The Keeper eviction note was invisible to the model in dummy4 (sink +
   search are the proof, note is best-effort).
2. The live CLI still runs the old world (ACP stable + cached old
   rtr-mcp.exe, native Keeper absent) until cutover + restart.

## Pass 1 — Keeper (native plugin, host window)
- File: `opencode-plugin/rtr-re-keeper.js` (single default export; helpers
  on `server._test` — loader contract miss fixed after opencode.log proof).
- Rules mirrored from `context_budget.py`: newest-first tail to target,
  tool-pair fixpoint, protected (`skill`) + last-user always kept, sink
  before prune, fail-open, internal agents skipped. Bounds 320k/128k/40
  with env-knob override, refusal by name.
- Tests: 9/9 node green in both trees. Proven: dummy4 host eviction sank
  10 spans (110.46 KB); dummy5 T1 ACP-ABSENT.
- Open: note visibility unproven (see lesson 1); watched-config reload +
  Ctrl+P controls pending (TODO-17).

## Pass 2 — Compressor (Rolling-derived planner + worker)
- Files: `execution/context_budget.py`, `execution/symbiose_worker.py`.
  Rolling Context lineage = compression policy port, NOT ACP (ACP was
  only ever Keeper). Vendored `rolling-context/` never ships.
- Contracts: bounded retention 512 with cache eviction, close fails
  queued by name, submit-after-close fails, canonical whole-message hash,
  verbatim typed sink (NDATA masked, LF bytes).
- Latency (synthetic, ONNX excluded): 40k profile submit 0.2ms/complete
  4.8ms; 320k profile submit 3–6ms, complete ≤41ms at 640k.
- Proven: dummy3 T4 + dummy5 T2 full loops (evict 21/42000, search
  0.9700/0.9650 on evicted marker). Suites green.

## Pass 3 — Manager + MCP viewport (retrieval + status glass)
- Files: `execution/memory_engine.py` (`_fused_multi`, standout
  `hybrid_lane_weights`, STRUCT lane default-off), `execution/memory_mcp_server.py`
  (25 tools incl. symbiose submit/poll + context plan).
- Frozen claims: binary intense rtr-full R@3 0.7557 best, R@1/MRR parity;
  graded gold-v2 dense-base leads 0.8167 vs 0.7798 (published, not smoothed).
- MCP is viewport only: reports collections/index/bounds/tickets; never
  drives Keeper/Compressor. Unified health surface pending (TODO-17).
- Live MCP today: old cached exe (22 tools, no Symbiose), connection
  closed 13:09:37 — stale, cutover pending.

## Pass 4 — Ship tree, sync, publish gates
- Standalone `C:/RTR-RE` (display RTR-RE:Symbiose; colon folder impossible,
  WinError 123 measured): 268 files manifest sha256, no ACP/Rolling
  folders, no acp.jsonc, Keeper + installer in wheel, 4 Tessersects +
  sidecar SRTs, READMEs carry final numbers.
- Sync guard: media + dist/ preserved (previous mp4 wipe fronted, fixed,
  tested). Lab stays evidence bench until cutover.
- Blockers: operator version act, credential transport proofs, PyPI
  upstream-licence note, live cutover + TODO-14 survey, TODO-10 media
  embeds done, TODO-17 live controls.

Restart scope: operator restarts now; post-restart survey (TODO-14) must
re-measure live wiring and NOT assume the new world is active.
