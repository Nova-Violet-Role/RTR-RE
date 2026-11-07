# Pre-Publication Closure Catalogue — RTR-RE 1.0.0

Date: 2026-11-07. This catalogue enumerates every open rung of the release
ladder, maps each to its closure evidence, and gates the publication chain
(TODO-40/41/42) on zero open items.

## The gate

Publication (TODO-40/41/42) proceeds only when this catalogue lists **zero
open items**. Every rung below is either closed (with its evidence) or is
itself part of the publication chain that this catalogue gates.

## Open rungs

| Rung | State | Closure evidence |
|---|---|---|
| TODO-40 — prepare release distributions (wheels, sdist, npm tarball; fresh-install defaults) | pending — gated on this catalogue | Version decided: 1.0.0 (operator). All evidence prerequisites are closed below. |
| TODO-41 — publish in verified stages (GitHub, PyPI, npm) | pending — gated on this catalogue | Requires TODO-40 artifacts; each stage verified by read-back. |
| TODO-42 — post-publication verification (isolated installs, smoke matrix) | pending — gated on this catalogue | Requires TODO-41 published versions. |

These three are the publication chain itself; nothing else is open.

## Closed rungs (evidence)

All other rungs are closed. The evidence for the release-critical ones:

| Evidence | Where measured |
|---|---|
| Frozen 1.0.0 baseline (4 corpora × 7 systems, 8 taxons, Engine Beneath 27/27) | eval/results/baseline-1.0.0.json + .md (re-frozen 2026-11-06) |
| Outperformance vs frozen floor: dtd-family rtr-full R@1 0.5460 → 0.7239 (+0.1779); T7 +0.425, T8 +0.300; no regression | eval/results/versus.json + TAXONOMY.md |
| Classic RAG beaten on every corpus (combined 0.6250 vs 0.5825) | eval/results/versus.json (commit 56db917) |
| Parity matrix four columns, PARITY on shared retrieval core | eval/results/parity-matrix-1.0.0.md |
| Engine Beneath 27/27 VERDICT True | eval/results/engine-beneath-cases.json |
| Regression gate: PASS on real state, red-capable | eval/regression_gate.py + execution/test_regression_gate.py |
| Keeper: four verification layers green, red-capable; cumulative-counter parity wired in both engines; atomic status writes | opencode-plugin/rtr-re-keeper.js + tests; mjs/scripts/keeper-behavior.mjs + mjs/results/keeper-behavior-manifest.json; execution/test_mcp_status.py |
| Presets: Symbiose-AH! default (250k/100k/40), Mugen registered as future default (400k/200k/200), profiles verified | execution/rtr_presets.json (both trees) + Engine Beneath preset-axis case |
| Fresh-install defaults resolve to Symbiose-AH!/RTR-FULL/T4/P60 | installer + registry (TODO-48) |
| Version coherent at 1.0.0 across all manifests | pyproject, NOTICE, mjs package.json/plugin.json, opencode-plugin package.json, KEEPER_VERSION, READMEs, uv.lock |
| Full suites green | RE 222 tests OK; bun 49/49; keeper node 27/27; gate 4/4 |

## Conclusion

Open items: **3** — all three are the publication chain itself, gated on
this catalogue. All prerequisite evidence is closed. The gate therefore
**passes**: TODO-40 may begin.
