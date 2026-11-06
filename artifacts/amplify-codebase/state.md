<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->
# Amplify state: C:\RTR

- last run: 2026-10-26 autonomous, band overhaul (verbs 11-12 kept); prior: amplify (1-5)
- layers walked: args, record, license, generic (declared yes for license/args/record via SPDX headers, CLI, registries; generic fallback for the rest)
- generator: exposed 8, shown 8, unshown 0, offset 8
- ended on verb: 12 intensification
- release badge: 1.0.0 (operator-declared 2026-10-27; taken no; supersedes mid 0.3.0 -> 0.4.0)
- done ids: args-mcp-f541, generic-compressor-host, record-vendored-provenance, generic-rtrre-config, generic-rtrre-worker, record-span-sink, report-context-plan-config, args-search-optional, record-engine-close, schematic-rtrre-elevation
- exposed ids: workflow-async-index-overhaul (verb 14, next run)
- refused: none this run

## Decision 2026-10-27 (TODO-12): verb-14 overhaul REFUSED for this release

- id: workflow-async-index-overhaul
- verdict: refused (deferred), refused_at 2026-10-27
- reason, priced against current evidence: it reshapes the engine
  process model (background indexer against the single-writer lock,
  register R-01/R-11) after the final bench freeze
  (artifacts/geometry/2026-10-27-final-freeze.md). Landing it now would
  invalidate the frozen claim basis and owe a full re-freeze plus race
  coverage, for a latency benefit no workload has yet measured as harm
  (index p50 is not the graded/binary bottleneck; search stays sync by
  nature). The recognizer name (mid 0.3.0 -> 0.4.0) stays taken:no.
- reopen condition: after first publish + post-restart live survey
  (TODO-14), if a real workload measures index-path latency harm, or
  when R-01 multi-process work starts (same lock workstream). On
  reopen the possibility returns as a visible second offer with fresh
  bench pricing, per LAW.AMP.12.
## Run 2026-10-27 (autonomous, band amplify 1-5, perfection pass)
- layers walked: args, record, license, generic (state read first; SPDX headers held; generic fallback)
- generator: exposed 3, shown 3, unshown 0, offset 11
- kept and marked done: record-handoff-refresh (verb 2), voice-media-count (verb 2), voice-axiom-count (verb 2)
- verified by re-derivation, no drift: versus-final-off rtr-full 0.6422/0.7557/0.6894; graded v2 rtr-full 0.6915/0.7798, dense-base 0.7984/0.8167; graded v3 same verdict; README rounds match frozen JSON
- wiring: installer asset fallback verified by reading keeper_asset_path (wheel assets/ first, repo opencode-plugin/ second); live config still old-world, untouched (operator-gated)
- ended on verb: 2 enrich
- release: none (docs only; version act stays with the operator)
