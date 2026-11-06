<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# Renewed functions listing: everything this cycle built or changed

Purpose (operator-ordered): one checklist so nothing renewed is forgotten
at cutover, publish, or the next audit. Each entry names the file, the
renewal, and its proof. Nothing here is claimed from memory — proofs are
the cited instruments.

## Keeper (native plugin, replaces ACP)
| # | File | Renewal | Proof |
|---|---|---|---|
| K1 | `opencode-plugin/rtr-re-keeper.js` | Rewrote transform: newest-first tail, tool-pair fixpoint, protected + last-user, sink-before-evict, fail-open | 19/19 node tests, dummy4 T3 sink 110 KB, dummy5 T5 eviction |
| K2 | same | Watched project config file (mtime reload, no restart) + `enabled` flag | live-reload test green; dummy5 T5 bounds from file not env |
| K3 | same | Status file every exchange (bounds, last decision/sink/error) | status-file test; T5 quoted 100/40, evicted, 27 spans |
| K4 | same | `/rtr` commands: status/hold/trigger/target/max/preset/enable/disable/help; `config` hook registers `rtr` command | command tests green (incl. refusal path); registration-once test |
| K5 | same | Async sink (awaited), single default export (loader contract) | loader miss fronted in opencode.log, fixed, 19/19 |
| K6 | same | NDATA masking, CDATA lane, estimator mirrors Python chars/4 | parity tests + sink-shape test |
| K7 | same | Watched project config + `/rtr` commands (status/hold/trigger/target/max/preset/enable/disable) + per-exchange status file + `config` hook registration; no abort-error hack (parts replaced, normal return) | 10 new red-first tests (reload, invalid, enable/disable, status file, 5 command tests, hook registration); dummy5 T5 live-reload proof 100/40 from file |
| C11 | `execution/memory_mcp_server.py` + `SymbioseWorker.stats()` | `memory_rtr_status` viewport (keeper file freshness, compressor bounds + ticket health, manager index; absent reads absent) | 4 red-first viewport tests; clean-venv tools/list 26 tools |

## Compressor (Rolling-derived planner + worker)
| # | File | Renewal | Proof |
|---|---|---|---|
| C1 | `execution/context_budget.py` | 320k/128k defaults, soft-target docstring, refused-by-name knobs | 12 context tests + matrix, bounds witnesses |
| C2 | `execution/context_budget.py` | Tool-pair fixpoint, canonical full-message hash (was role+text) | chain regression, Lean counterparts |
| C3 | `execution/symbiose_worker.py` | Bounded retention 512 + cache eviction | red-first retention test |
| C4 | same | Close fails queued tickets by name; submit-after-close failed ticket | red-first close tests |
| C5 | same | Ticket timing telemetry + `stats()` for MCP viewport | calibration tables, status tests |
| C6 | `execution/memory_engine.py` | `hybrid_lane_weights` standout statistic | 4 red-first tests, NT-G1C 12→4 |
| C7 | same | `project_filter_key` root-ref coherence; `PROJECTS_DIR` follows first root | red-first tests, dummy3 T2/T4 |
| C8 | same | STRUCT lane (rg --json default, ccc for patterns), shared 0.15 cap, fallback identity | 5 routing + engine tests, lane-off/on freeze |
| C9 | `execution/memory_mcp_server.py` | `memory_rtr_status` viewport (keeper/compressor/manager) | 4 red-first status tests |
| C10 | `execution/install_opencode.py` | Keeper installer (refuse-to-clobber, snippet, no-ACP config) | 5 installer tests |

## Manager benches + supervision
| # | File | Renewal | Proof |
|---|---|---|---|
| M1 | `eval/graded/build_gold.py --v2` | 773 pooled judgments, blind worksheet | validation errors empty |
| M2 | `eval/bench_graded.py` | Gold-v2 dataset label fix | final freeze run |
| M3 | `eval/plates_graded.py` + `eval/plates_versus.py` | Data-driven plates + doctor invariants | forgery controls refused |
| M4 | `eval/results/` | Frozen lane-off claim basis + lane-on archives | final-freeze record |

## Formal battery
| # | File | Renewal | Proof |
|---|---|---|---|
| F1 | `formal/Symbiose/Lane.lean` | STRUCT lane contract (total/disjoint, cap, fallback) | part of 9-job build, 0 sorry |
| F2 | `formal/Symbiose/Control.lean` + full-Mathlib battery | Live-control contract (precedence, reload identity, verb totality, presence honesty); require mathlib v4.33.0, every module imports it, norm_num/linarith idioms | clean build exit 0, **8713 jobs both trees**, 20 standard axiom records, 0 sorry; -Ddiagnostics clean on all modules; records `2026-10-27-lean-control.md` + `formal/MATHLIB_POLICY.md` |

## Ship + docs + media
| # | Artifact | Renewal | Proof |
|---|---|---|---|
| S1 | `C:/RTR-RE` tree | 275 synced files, manifest sha256, no ACP/Rolling/acp.jsonc | sync 275/removed 0 |
| S2 | wheel+sdist | Keeper asset inside, console scripts, 26 MCP tools | clean-venv smoke |
| S3 | `media/` | 4 Tessersects 135 s 480p + sidecar SRTs + TECHSPEC | ffprobe records |
| S4 | READMEs | Final numbers, keeper commands, adaptation Issue form | CR-free, cross-checked |
| S5 | `tools/sync_standalone.py` | Preserves dist/lake/venvs, media included, covered by test | sync-preservation test |

## Cut off at cutover (do NOT ship, do NOT load live)
- `opencode-acp@stable` plugin entry (live plugin list) → replaced by `./plugin/rtr-re-keeper.js`
- `acp.jsonc` (live + project template) → replaced by watched `rtr-re-keeper.json` + `memory_rtr_status`
- Cached `rtr-mcp.exe` (uv cache, 22 tools, no Symbiose) → replaced by standalone `rtr-re-mcp` (26 tools)
- `rolling-context/` + `opencode-acp/` checkouts → lab-only references, never shipped
