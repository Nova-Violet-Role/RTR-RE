<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->
<!-- Copyright 2026 Saimonokuma. -->
# Renovation 2: RTR-RE:Rolling amplified (configurable, no-pause, both lanes)

- survey: artifacts/geometry/2026-10-26-survey.md
- plan: artifacts/geometry/2026-10-26-plan.md (operator-amended)
- amplify study: artifacts/amplify-codebase/ (ledger, state, roadmap, handoff, 4 layer docs)
- date: 2026-10-26

## Changes (before -> after)

| verb | file | before | after |
|---|---|---|---|
| 4 amplification | execution/context_budget.py | fixed constants only | rolling_config() env knobs + named refusals; span lane/dtype on every evicted span; config-aware plan |
| 5 magnify | execution/rolling_worker.py (new, 6168 B) | compression planning synchronous only | background worker: submit <0.25s vs 0.6s sink (test), hash cache, bounded queue, cooldown, poll/wait |
| 4 amplification | SessionSpanSink (in rolling_worker.py) | evicted spans had no index path | verbatim typed span files for directives/sessions/, both lanes |
| 2 enrich | execution/memory_mcp_server.py | plan tool printed constants | prints effective config + source; refuses invalid config by name |
| 1 tweak | execution/memory_mcp_server.py | 7 ruff F541 | fixed, ruff clean |
| 3 ameliorate | rolling-context/1.8.0/proxy/compressor.py | summarizer host could be None | guarded default host |
| 2 enrich | VENDORED.md (new) | vendored trees unpinned | commits + local changes recorded |

## Certification (measured, feature phase)

- test_rolling_worker.py: Ran 8 tests OK (config, no-pause timing, cache, cooldown, no-mutation, sink).
- test_context_budget.py: Ran 11 tests OK. ruff: All checks passed. py_compile clean. CR false.
- Release named: minor 0.3.0 -> 0.3.1, taken no (recognizer; kept verbs 1-5).
- Next verb: 6 heighten via /enhance-codebase-dtd. Open gap: args-search-optional (ledger, exposed).

Full evaluation (configurable-unit matrix, dummy opencode-dev session, A-Z report) follows per operator order — features first, then tests.
